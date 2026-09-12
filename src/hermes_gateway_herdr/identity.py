"""OS identity is checked again immediately before every destructive action."""

import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

import psutil

from .errors import GatewayError


def owner_key(profile_home: Path, owner_socket: Path) -> str:
    socket_path = Path(owner_socket).parent.resolve(strict=True) / Path(owner_socket).name
    fields = [os.getuid(), str(socket_path), str(Path(profile_home).resolve(strict=True))]
    return hashlib.sha256(json.dumps(fields, separators=(",", ":")).encode()).hexdigest()


def boot_fingerprint() -> str:
    if sys.platform.startswith("linux"):
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return f"{sys.platform}:{psutil.boot_time():.6f}"


def capture(pid: int) -> dict | None:
    if type(pid) is not int or pid <= 0:
        raise GatewayError("INVALID_IDENTITY", "Invalid process id")
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            if proc.status() == psutil.STATUS_ZOMBIE:
                return None
            created = proc.create_time()
            kind, value = "epoch_centiseconds", str(int(created * 100))
            if sys.platform.startswith("linux"):
                raw = Path(f"/proc/{pid}/stat").read_text()
                kind, value = "linux_ticks", raw.rsplit(")", 1)[1].split()[19]
            return {
                "pid": pid, "uid": proc.uids().real, "ppid": proc.ppid(),
                "start_fingerprint": {"kind": kind, "boot": boot_fingerprint(), "value": value},
                "create_time": created, "sid": os.getsid(pid),
                "exe": str(Path(proc.exe()).resolve()), "argv": proc.cmdline(),
            }
    except (psutil.NoSuchProcess, ProcessLookupError, FileNotFoundError):
        return None
    except (psutil.AccessDenied, PermissionError) as exc:
        # macOS can drop argv before publishing zombie status (KERN_PROCARGS2
        # EINVAL becomes AccessDenied in psutil). A single immediate recheck
        # still sees a live PID. Wait briefly for proof of exit, never reap it:
        # Popen must retain the child's real exit code for restart/fuse policy.
        deadline = time.monotonic() + 0.02
        while "proc" in locals():
            try:
                if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                    return None
            except psutil.NoSuchProcess:
                return None
            except (psutil.AccessDenied, PermissionError):
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(0.001)
        raise GatewayError("UNKNOWN", "Process identity is not readable") from exc


def same_process(expected: dict, actual: dict | None = None) -> bool:
    if not isinstance(expected, dict) or not {"pid", "uid", "start_fingerprint"} <= expected.keys():
        raise GatewayError("INVALID_IDENTITY", "Incomplete process fingerprint")
    if actual is None:
        actual = capture(expected["pid"])
    return actual is not None and all(actual.get(key) == expected.get(key)
                                      for key in ("pid", "uid", "start_fingerprint"))


def hermes_start_matches(record: dict, start_time: object) -> bool:
    """Match Hermes' Linux ticks or rounded psutil centiseconds, without a tolerance window."""
    if type(start_time) is not int:
        return False
    fingerprint = record["start_fingerprint"]
    candidates = {int(round(record["create_time"] * 100))}
    if fingerprint["kind"] == "linux_ticks":
        candidates.add(int(fingerprint["value"]))
    return start_time in candidates


def signal_verified(expected: dict, signum: int) -> bool:
    actual = capture(expected["pid"])
    if actual is None:
        return False
    if not same_process(expected, actual) or actual["uid"] != os.getuid():
        raise GatewayError("IDENTITY_CHANGED", "Refusing to signal an unverified process")
    pidfd = None
    try:
        if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
            try:
                pidfd = os.pidfd_open(expected["pid"])
            except OSError as exc:
                # Python may expose pidfd_open on a kernel that predates it.
                if exc.errno != errno.ENOSYS:
                    raise
        if not same_process(expected):
            raise GatewayError("IDENTITY_CHANGED", "Process changed during signal delivery")
        if pidfd is not None:
            signal.pidfd_send_signal(pidfd, signum)
        else:
            os.kill(expected["pid"], signum)
        return True
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise GatewayError("STOP_FAILED", "Signal permission denied") from exc
    finally:
        if pidfd is not None:
            os.close(pidfd)


def descendants(parent: dict) -> list[dict]:
    if not same_process(parent):
        return []
    try:
        children = psutil.Process(parent["pid"]).children(recursive=True)
        candidates = [record for proc in children if (record := capture(proc.pid)) is not None]
        if not same_process(parent):
            return []
        # children() is only a snapshot of PIDs. Reused PIDs must still have a
        # verified parent chain, including for tasks that created a new session.
        owned = {parent["pid"]: parent}
        while candidates:
            remaining = []
            for record in candidates:
                ancestor = owned.get(record["ppid"])
                if (ancestor and record["uid"] == os.getuid()
                        and same_process(ancestor) and same_process(record)):
                    owned[record["pid"]] = record
                else:
                    remaining.append(record)
            if len(remaining) == len(candidates):
                break
            candidates = remaining
        return [record for pid, record in owned.items() if pid != parent["pid"]]
    except psutil.NoSuchProcess:
        return []
    except psutil.AccessDenied as exc:
        raise GatewayError("UNKNOWN", "Cannot establish child ownership") from exc


def public_identity(record: dict | None) -> dict | None:
    if record is None:
        return None
    return {key: record[key] for key in ("pid", "uid", "sid", "start_fingerprint")}
