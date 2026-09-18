"""One bounded JSON line per Unix socket connection; no automatic service starts."""

import hashlib
import fcntl
import json
import math
import os
from pathlib import Path
import time
import uuid

from .compatibility import check_herdr_compatibility
from .config import Config, HERMES_SHA, PLUGIN_ID, private_bytes
from .errors import GatewayError
from .identity import capture, hermes_start_matches, same_process
from .paths import json_object as decode_object
from .state import check_private
from .transport import check_peer, check_socket, exchange


class RemoteError(GatewayError):
    def __init__(self, remote_code: str):
        self.remote_code = remote_code
        super().__init__("HERDR_ERROR", "Herdr rejected the request")


class Herdr:
    def __init__(self, config: Config, timeout: float = 2):
        self.config, self.timeout = config, timeout
        self.deadline = None

    def call(self, method: str, params: dict | None = None, *, request_id: str | None = None) -> dict:
        timeout = self.timeout if self.deadline is None else min(self.timeout, self.deadline - time.monotonic())
        if timeout <= 0:
            raise GatewayError("RPC_UNAVAILABLE", "Controller deadline exhausted")
        response = exchange(self.config.owner_socket,
                            {"id": request_id or uuid.uuid4().hex, "method": method, "params": params or {}},
                            timeout=timeout)
        if "error" in response:
            error = response["error"]
            if not isinstance(error, dict) or not isinstance(error.get("code"), str):
                raise GatewayError("PROTOCOL_ERROR")
            raise RemoteError(error["code"])
        result = response.get("result")
        if not isinstance(result, dict):
            raise GatewayError("PROTOCOL_ERROR", "Herdr omitted a result object")
        return result

    def available(self) -> dict:
        return check_herdr_compatibility(self.call("ping"))

    def enabled(self) -> bool:
        plugins = self.call("plugin.list", {"plugin_id": PLUGIN_ID}).get("plugins")
        if not isinstance(plugins, list):
            raise GatewayError("PROTOCOL_ERROR")
        matching = [plugin for plugin in plugins if isinstance(plugin, dict) and plugin.get("plugin_id") == PLUGIN_ID]
        if not matching:
            return False
        if len(matching) != 1 or type(matching[0].get("enabled")) is not bool:
            raise GatewayError("PROTOCOL_ERROR")
        root = matching[0].get("plugin_root")
        if not isinstance(root, str) or not Path(root).is_absolute() or any(ord(char) < 32 for char in root):
            raise GatewayError("PROTOCOL_ERROR", "Registered plugin must provide an absolute code path")
        if Path(root).resolve() != self.config.plugin_root.resolve():
            raise GatewayError("OWNERSHIP_CONFLICT", "Registered plugin points to different code")
        return matching[0]["enabled"]

    def membership(self, expected: dict, supervisor: dict) -> dict:
        pane = self.call("pane.get", {"pane_id": expected["pane_id"]}).get("pane")
        processes = self.call("pane.process_info", {"pane_id": expected["pane_id"]}).get("process_info")
        if not isinstance(pane, dict) or not isinstance(processes, dict):
            raise GatewayError("PROTOCOL_ERROR")
        if any(pane.get(key) != expected.get(key) for key in ("workspace_id", "tab_id", "pane_id")):
            raise GatewayError("ENV_STALE", "Pane moved outside its inherited environment")
        if (processes.get("pane_id") != expected["pane_id"] or processes.get("shell_pid") != supervisor["pid"]
                or not same_process(supervisor)):
            raise GatewayError("PANE_MISMATCH", "Pane no longer owns this supervisor")
        if not isinstance(pane.get("terminal_id"), str) or not pane["terminal_id"]:
            raise GatewayError("PROTOCOL_ERROR")
        # terminal_id is allocated anew during live handoff. The process fingerprint is stable.
        return {key: pane[key] for key in ("workspace_id", "tab_id", "pane_id", "terminal_id")}


def supervisor_socket(config: Config) -> Path:
    direct = config.state_dir / "supervisor.sock"
    if len(os.fsencode(direct)) <= 100:
        return direct
    return Path("/tmp") / f"hgh-{os.getuid()}-{config.key[:20]}" / "supervisor.sock"


def hermes_socket(config: Config) -> Path:
    direct = config.profile_home / "gateway.sock"
    if len(os.fsencode(direct)) <= 100:
        return direct
    suffix = hashlib.sha256(os.path.normcase(str(config.profile_home.resolve())).encode()).hexdigest()[:16]
    expected = Path("/tmp") / f"hermes-gw-{suffix}.sock"
    pointer = private_bytes(config.profile_home / "gateway.sock.path", 4096).decode().strip()
    if Path(pointer) != expected:
        raise GatewayError("UNSAFE_PATH", "Gateway socket pointer is outside its expected location")
    return expected


def profile_in_use(config: Config, *, timeout: float = 2, probe_socket: bool = True) -> bool:
    """Inspect Hermes' own fences without deleting, replacing or claiming its state."""
    lock = config.profile_home / "gateway.lock"
    try:
        fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise GatewayError("UNKNOWN", "Cannot inspect Hermes runtime lock") from exc
    else:
        try:
            check_private(os.fstat(fd))
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
        finally:
            os.close(fd)
    pid_path = config.profile_home / "gateway.pid"
    if pid_path.exists() or pid_path.is_symlink():
        # Hermes creates PID metadata with os.open's 0777 default (0700 under our umask).
        record = decode_object(private_bytes(pid_path, 64 * 1024, allow_owner_execute=True))
        pid = record.get("pid")
        if type(pid) is not int or pid <= 0:
            raise GatewayError("UNKNOWN", "Hermes PID record is not verifiable")
        actual = capture(pid)
        if actual is not None:
            if "start_time" not in record:
                raise GatewayError("UNKNOWN", "Live legacy PID record requires inspection")
            if hermes_start_matches(actual, record["start_time"]):
                return True
    if not probe_socket:
        return False
    try:
        path = hermes_socket(config)
    except GatewayError as exc:
        # A missing long-path pointer is normal before the very first Gateway launch.
        if exc.code == "CONFIG_ERROR" and not (config.profile_home / "gateway.sock.path").exists():
            return False
        raise
    if not path.exists() and not path.is_symlink():
        return False
    try:
        control_query(path, "identify", timeout=timeout)
        return True
    except GatewayError as exc:
        if exc.code == "RPC_UNAVAILABLE" and isinstance(exc.__cause__, (ConnectionRefusedError, FileNotFoundError)):
            return False
        raise GatewayError("UNKNOWN", "Existing Gateway socket cannot be identified") from exc


def control_query(path: Path, verb: str, *, timeout: float = 2, request_id: str | None = None, **fields) -> dict:
    response = exchange(path, {"protocol": 1, "id": request_id or uuid.uuid4().hex, "verb": verb, **fields}, timeout=timeout)
    if type(response.get("protocol")) is not int or response["protocol"] != 1:
        raise GatewayError("PROTOCOL_ERROR", "Control protocol was rejected")
    if response.get("ok") is not True:
        code = response.get("code")
        # Only expose locally defined rejection codes, never arbitrary peer text.
        if code not in ("STALE_REQUEST", "UNSUPPORTED_VERB", "PROTOCOL_ERROR", "BUSY", "IO_ERROR", "STATE_SCHEMA"):
            code = "PROTOCOL_ERROR"
        raise GatewayError(code, "Control request was rejected")
    result = response.get("result")
    if not isinstance(result, dict):
        raise GatewayError("PROTOCOL_ERROR", "Control result must be an object")
    return result


def evaluate_gateway(config: Config, child: dict, identity: dict, status: dict) -> dict:
    def identity_matches(payload):
        return (payload.get("kind") == "hermes-gateway" and type(payload.get("pid")) is int
                and payload["pid"] == child["pid"] and hermes_start_matches(child, payload.get("start_time"))
                and payload.get("code_sha") == HERMES_SHA and type(payload.get("protocol")) is int
                and payload["protocol"] == 1)

    def home_matches(payload):
        home = payload.get("hermes_home")
        return isinstance(home, str) and Path(home).is_absolute() and Path(home).resolve() == config.profile_home

    if (not identity_matches(identity) or not identity_matches(status)
            or identity.get("profile") != config.profile_id or identity.get("supervisor") != "external"
            or not home_matches(identity) or not home_matches(status)
            or type(status.get("answering_pid")) is not int or status["answering_pid"] != child["pid"]
            or type(status.get("answered_at")) not in (int, float) or not math.isfinite(status["answered_at"])):
        raise GatewayError("GATEWAY_IDENTITY", "Gateway does not match the expected child and profile")
    for payload in (identity, status):
        served = payload.get("served_profiles", [])
        if not isinstance(served, list) or any(profile != config.profile_id for profile in served):
            raise GatewayError("GATEWAY_IDENTITY", "Gateway serves additional profiles")
    platforms = status.get("platforms")
    if not isinstance(platforms, dict):
        raise GatewayError("PROTOCOL_ERROR")
    summary = {}
    operational = bool(config.expected_platforms) and status.get("gateway_state") == "running"
    for platform in config.expected_platforms:
        entry = platforms.get(platform, {})
        if not isinstance(entry, dict):
            raise GatewayError("PROTOCOL_ERROR")
        connected = (entry.get("state") == "connected" and not entry.get("error_code")
                     and entry.get("needs_attention") in (None, False)
                     and type(entry.get("writer_pid")) is int and entry["writer_pid"] == child["pid"]
                     and hermes_start_matches(child, entry.get("writer_start_time")))
        summary[platform] = {"connected": connected}
        operational = operational and connected
    return {"level": 1, "operational": bool(operational), "platforms": summary,
            "state": "STARTING" if operational else "DEGRADED"}


class GatewayProbe:
    def __init__(self, config: Config, *, interval: float = 1, timeout: float = 2):
        self.config, self.interval, self.timeout = config, interval, timeout
        self.first_good = None
        self.child_key = None

    def observe(self, child: dict, identity: dict, status: dict, now: float) -> dict:
        key = (child["pid"], child["start_fingerprint"]["value"])
        if key != self.child_key:
            self.first_good, self.child_key = None, key
        try:
            result = evaluate_gateway(self.config, child, identity, status)
        except GatewayError:
            self.first_good = None
            raise
        if not result["operational"]:
            self.first_good = None
        elif self.first_good is None:
            self.first_good = now
        elif now - self.first_good >= self.interval:
            result.update(level=2, state="READY")
        return result

    def inspect(self, child: dict) -> dict:
        try:
            path = hermes_socket(self.config)
            identity = control_query(path, "identify", timeout=self.timeout)
            status = control_query(path, "status", timeout=self.timeout)
            if not same_process(child):
                raise GatewayError("GATEWAY_IDENTITY", "Gateway process exited during its probe")
            return self.observe(child, identity, status, time.monotonic())
        except GatewayError:
            self.first_good = None
            raise
