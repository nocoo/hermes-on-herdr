"""OS identity is checked again immediately before every destructive action."""

import hashlib
import json
import os
from pathlib import Path
import signal
import sys

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
        # macOS can report EPERM for exe/argv while a process is exiting. Only a
        # subsequent confirmed disappearance makes that race equivalent to absence.
        if "proc" in locals():
            try:
                if not proc.is_running():
                    return None
            except (psutil.AccessDenied, PermissionError):
                pass
        raise GatewayError("UNKNOWN", "Process identity is not readable") from exc


def same_process(expected: dict, actual: dict | None = None) -> bool:
    if not isinstance(expected, dict) or not {"pid", "uid", "start_fingerprint"} <= expected.keys():
        raise GatewayError("INVALID_IDENTITY", "Incomplete process fingerprint")
    if actual is None:
        actual = capture(expected["pid"])
    return actual is not None and all(actual.get(key) == expected.get(key)
                                      for key in ("pid", "uid", "start_fingerprint"))


def hermes_start_matches(record: dict, start_time: object) -> bool:
    """Hermes may fall back to psutil even on Linux; both units are derived locally."""
    if type(start_time) is not int:
        return False
    fingerprint = record["start_fingerprint"]
    candidates = {int(record["create_time"] * 100)}
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
            pidfd = os.pidfd_open(expected["pid"])
            if not same_process(expected):
                raise GatewayError("IDENTITY_CHANGED", "Process changed during signal delivery")
            signal.pidfd_send_signal(pidfd, signum)
        else:
            if not same_process(expected):
                raise GatewayError("IDENTITY_CHANGED", "Process changed during signal delivery")
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
        result = [record for proc in children if (record := capture(proc.pid)) is not None]
        if not same_process(parent):
            return []
        return [record for record in result if record["uid"] == os.getuid()]
    except psutil.NoSuchProcess:
        return []
    except psutil.AccessDenied as exc:
        raise GatewayError("UNKNOWN", "Cannot establish child ownership") from exc


def public_identity(record: dict | None) -> dict | None:
    if record is None:
        return None
    return {key: record[key] for key in ("pid", "uid", "sid", "start_fingerprint")}
