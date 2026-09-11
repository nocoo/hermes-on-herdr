"""Read-only, bounded telemetry for local Hermes gateways. Never import Hermes."""

from collections import deque
from dataclasses import dataclass, replace
import math
import os
from pathlib import Path
import re
import stat
import time

import psutil

from .config import Config
from .controller import Controller
from .errors import GatewayError
from .identity import capture, hermes_start_matches, same_process
from .paths import json_object
from .rpc import control_query, hermes_socket

PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
STATES = {"READY", "RUNNING", "STARTING", "DEGRADED", "DRAINING", "BACKOFF", "FUSED",
          "PAUSED", "ABSENT", "UNKNOWN", "ORPHAN", "PENDING", "DISABLED", "STOPPED", "SHARED"}
PLATFORM_STATES = {"connected", "connecting", "disconnected", "retrying", "error", "fatal", "stopped", "disabled"}
HISTORY = 90
DISCOVERY_INTERVAL = 30
PROBE_BATCH = 4
PROBE_TIMEOUT = 0.15


def text(value, limit=100):
    """Only printable text reaches the terminal, including from local metadata."""
    return "".join(c for c in str(value) if c.isprintable())[:limit]


def metadata(path: Path):
    """Native metadata may be 0644/0700. No links, writable peers or special files."""
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise GatewayError("UNSAFE_PATH")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o022 or info.st_size > 65536):
            raise GatewayError("UNSAFE_PATH")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise GatewayError("STATE_SCHEMA")
        return json_object(raw)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class Profile:
    name: str
    home: Path
    managed: bool = False
    state: str = "UNKNOWN"
    pid: int | None = None
    started: float | None = None
    supervision: str = "unknown"
    cpu: float | None = None
    rss: int | None = None
    active: int | None = None
    platforms: tuple = ()
    observed: float = 0
    error: str = ""
    served: tuple = ()
    shared_from: str = ""
    cpu_history: tuple = ()
    memory_history: tuple = ()
    pane: str = ""


@dataclass(frozen=True)
class Snapshot:
    profiles: tuple = ()
    updated: float = 0
    host_cpu: float | None = None
    host_used: int | None = None
    host_total: int | None = None
    host_history: tuple = ()
    events: tuple = ()
    error: str = ""


def discover(config: Config):
    """Default home + named profiles in this installation, without reading config/.env."""
    root = config.profile_home.parent.parent
    candidates = [(config.profile_id, config.profile_home), ("default", root)]
    directory = root / "profiles"
    if not directory.is_symlink():
        try:
            candidates.extend((p.name, p) for p in sorted(directory.iterdir())
                              if p.name not in {"default", config.profile_id} and PROFILE_ID.fullmatch(p.name)
                              and not (directory / ".deleted" / p.name).exists())
        except OSError:
            pass
    result = []
    for name, home in candidates:
        try:
            info = home.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                continue
        except OSError:
            continue
        result.append(Profile(name, home, name == config.profile_id))
    return result


def process_metrics(record):
    process = psutil.Process(record["pid"])
    with process.oneshot():
        if process.create_time() != record["create_time"] or process.uids().real != os.getuid():
            raise GatewayError("GATEWAY_IDENTITY")
        cpu = process.cpu_times()
        return cpu.user + cpu.system, process.memory_info().rss


def _identity_matches(payload, profile, record):
    home = payload.get("hermes_home")
    return (payload.get("kind") == "hermes-gateway" and type(payload.get("protocol")) is int and payload["protocol"] == 1
            and type(payload.get("pid")) is int and payload["pid"] == record["pid"]
            and isinstance(home, str) and Path(home).is_absolute() and Path(home).resolve() == profile.home
            and hermes_start_matches(record, payload.get("start_time")))


def inspect_profile(config, profile, *, query=control_query, process=capture, metrics=process_metrics):
    """The socket proves the live scope. A PID file alone never grants a healthy state."""
    base = replace(profile, cpu=None, rss=None, active=None, platforms=(), pid=None, started=None,
                   served=(), shared_from="", error="", supervision="unknown", pane="")
    try:
        scoped = replace(config, profile_id=profile.name, profile_home=profile.home)
        pointer = profile.home / "gateway.sock.path"
        direct = profile.home / "gateway.sock"
        path = direct if len(os.fsencode(direct)) > 100 and not os.path.lexists(pointer) else hermes_socket(scoped)
        hint = metadata(profile.home / "gateway.pid")
        if hint is None and not path.exists():
            # Some native launchers retain only gateway_state.json while starting.
            hint = metadata(profile.home / "gateway_state.json")
        if not path.exists():
            pid = hint.get("pid") if isinstance(hint, dict) else None
            record = process(pid) if type(pid) is int and pid > 0 else None
            if record is not None:
                return replace(base, state="UNKNOWN", error="CONTROL_UNAVAILABLE"), None
            return replace(base, state="STOPPED"), None
        identity = query(path, "identify", timeout=PROBE_TIMEOUT)
        pid = identity.get("pid")
        record = process(pid) if type(pid) is int and pid > 0 else None
        if (record is None or record["uid"] != os.getuid() or not _identity_matches(identity, profile, record)
                or identity.get("profile") != profile.name):
            raise GatewayError("GATEWAY_IDENTITY")
        status = query(path, "status", timeout=PROBE_TIMEOUT)
        answered = status.get("answered_at")
        if (not _identity_matches(status, profile, record) or type(status.get("answering_pid")) is not int
                or status["answering_pid"] != pid
                or type(answered) not in (int, float) or not math.isfinite(answered)
                or abs(time.time() - answered) > 10 or not same_process(record, process(pid))):
            raise GatewayError("GATEWAY_IDENTITY")
        platforms = status.get("platforms", {})
        if not isinstance(platforms, dict):
            raise GatewayError("PROTOCOL_ERROR")
        summary = []
        for name, entry in list(platforms.items())[:32]:
            if not isinstance(name, str) or not PROFILE_ID.fullmatch(name) or not isinstance(entry, dict):
                continue
            state = entry.get("state")
            if (entry.get("writer_pid") != pid or not hermes_start_matches(record, entry.get("writer_start_time"))):
                state = "unverified"
            elif entry.get("error_code") or entry.get("needs_attention"):
                state = "error"
            elif state not in PLATFORM_STATES:
                state = "unknown"
            summary.append((name, state))
        state = "RUNNING" if status.get("gateway_state") == "running" else "STARTING"
        if any(value != "connected" for _, value in summary):
            state = "DEGRADED"
        active = status.get("active_agents")
        active = active if type(active) is int and active >= 0 else None
        served = identity.get("served_profiles", [])
        served = tuple(name for name in served[:4096] if isinstance(name, str) and PROFILE_ID.fullmatch(name)) if isinstance(served, list) else ()
        supervision = identity.get("supervisor", "unknown")
        if supervision not in {"external", "manual", "launchd", "systemd", "windows-service"}:
            supervision = "native"
        cpu_seconds, rss = metrics(record)
        return replace(base, state=state, pid=pid, started=record["create_time"], supervision=supervision,
                       rss=rss, active=active, platforms=tuple(sorted(summary)), served=served), cpu_seconds
    except (GatewayError, OSError, ValueError, TypeError, psutil.Error) as exc:
        return replace(base, state="UNKNOWN", error=exc.code if isinstance(exc, GatewayError) else "UNAVAILABLE"), None


class Monitor:
    """One worker samples the bound/selected profiles, then a fair bounded background batch."""

    def __init__(self, config, *, inspect=inspect_profile, managed_status=None, host=True):
        self.config, self.inspect = config, inspect
        self.managed_status = managed_status or (lambda: Controller(config, budget=0.5).status())
        self.host = host
        self.selected = config.profile_id
        self.snapshot = Snapshot()
        self._profiles = {}
        self._next_discovery = 0
        self._cursor = 0
        self._cpu = {}
        self._histories = {}
        self._host_history = deque(maxlen=HISTORY)
        self._host_primed = False
        self._events = deque(maxlen=24)

    def collect(self, *, now=None, managed_only=False):
        now = time.monotonic() if now is None else now
        wall = time.time()
        if managed_only:
            self._profiles.setdefault(self.config.profile_id, Profile(self.config.profile_id, self.config.profile_home, managed=True))
        elif now >= self._next_discovery:
            discovered = discover(self.config)
            self._profiles = {p.name: self._profiles.get(p.name, p) for p in discovered}
            self._cpu = {k: v for k, v in self._cpu.items() if k in self._profiles}
            self._histories = {k: v for k, v in self._histories.items() if k in self._profiles}
            self._next_discovery = now + DISCOVERY_INTERVAL
        names = [self.config.profile_id] if managed_only else list(self._profiles)
        priority = list(dict.fromkeys(n for n in (self.config.profile_id, self.selected) if n in names))
        others = [n for n in names if n not in priority]
        batch = priority[:]
        if others:
            count = min(len(others), PROBE_BATCH - len(batch))
            batch.extend(others[(self._cursor + i) % len(others)] for i in range(count))
            self._cursor = (self._cursor + count) % len(others)
        for name in batch:
            previous = self._profiles[name]
            try:
                current, cpu_seconds = self.inspect(self.config, previous)
            except Exception:
                # One inaccessible/corrupt profile must not blank every other profile.
                current, cpu_seconds = replace(previous, state="UNKNOWN", error="INSPECTION_FAILED",
                                               cpu=None, rss=None, active=None, platforms=(), served=()), None
            key = (current.pid, current.started)
            old = self._cpu.get(name)
            histories = self._histories.setdefault(name, (deque(maxlen=HISTORY), deque(maxlen=HISTORY)))
            if old is None or old[:2] != key:
                histories[0].clear()
                histories[1].clear()
            if cpu_seconds is not None:
                cpu = max(0.0, (cpu_seconds - old[3]) / (now - old[2]) * 100) if old and old[:2] == key and now > old[2] else None
                self._cpu[name] = (*key, now, cpu_seconds)
                if cpu is not None:
                    histories[0].append(cpu)
                histories[1].append(current.rss / 1048576)
                current = replace(current, cpu=cpu)
            else:
                self._cpu.pop(name, None)
            if current.managed:
                try:
                    owned = self.managed_status()
                    state = owned.get("state", "UNKNOWN")
                    # A cached owner probe cannot hide a newer disconnect or a different child.
                    gateway = owned.get("gateway") or {}
                    if state == "READY" and (current.pid is None or gateway.get("pid") != current.pid):
                        current = replace(current, state="UNKNOWN", error="OWNERSHIP_MISMATCH")
                    elif state != "READY" or current.state == "RUNNING":
                        current = replace(current, state=state if state in STATES else "UNKNOWN",
                                          pane=text((owned.get("pane") or {}).get("pane_id", ""), 80))
                except (GatewayError, OSError, ValueError, TypeError):
                    current = replace(current, state="UNKNOWN", error="OWNER_UNAVAILABLE")
            current = replace(current, observed=wall, cpu_history=tuple(histories[0]), memory_history=tuple(histories[1]))
            if current.state != previous.state or current.pid != previous.pid:
                self._events.append((wall, name, current.state, current.error))
            self._profiles[name] = current
        rows = [self._profiles[name] for name in names]
        # Multiplexed profiles share one process; do not invent per-profile resource/connection data.
        served = {name: p for p in rows if p.pid and not p.error and wall - p.observed < max(10, len(rows) * 2)
                  for name in p.served if name != p.name}
        rows = [replace(p, state="SHARED", pid=served[p.name].pid, started=served[p.name].started,
                        observed=served[p.name].observed, shared_from=served[p.name].name,
                        cpu=None, rss=None, active=None, platforms=())
                if not p.managed and p.pid is None and p.name in served and p.state == "STOPPED" else p for p in rows]
        cpu = used = total = None
        if self.host and not managed_only:
            try:
                value = psutil.cpu_percent(interval=None)
                if self._host_primed:
                    cpu = value
                    self._host_history.append(value)
                self._host_primed = True
                memory = psutil.virtual_memory()
                used, total = memory.total - memory.available, memory.total
            except (OSError, psutil.Error):
                pass
        self.snapshot = Snapshot(tuple(rows), wall, cpu, used, total, tuple(self._host_history), tuple(self._events))
        return self.snapshot
