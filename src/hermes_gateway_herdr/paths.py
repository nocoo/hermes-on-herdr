"""Stdlib-only path checks, also usable by the system-Python launcher."""

from __future__ import annotations

import os
import json
import math
from pathlib import Path
import stat

from .errors import GatewayError


def json_object(raw: bytes, *, code: str = "PROTOCOL_ERROR") -> dict:
    def mapping(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("non-finite number")
        return result

    def invalid_constant(_):
        raise ValueError("non-finite number")

    try:
        result = json.loads(raw, object_pairs_hook=mapping, parse_float=finite_float, parse_constant=invalid_constant)
        if not isinstance(result, dict):
            raise ValueError("object required")
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise GatewayError(code, "Malformed JSON object") from exc


def check_private(st: os.stat_result, *, directory: bool = False, allow_unlinked: bool = False,
                  allow_owner_execute: bool = False) -> None:
    expected = 0o700 if directory else 0o600
    mode = stat.S_IMODE(st.st_mode)
    if allow_owner_execute and not directory:
        mode &= ~stat.S_IXUSR
    right_type = stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)
    if (not right_type or st.st_uid != os.getuid() or mode != expected
            or (not directory and st.st_nlink not in ({0, 1} if allow_unlinked else {1}))):
        raise GatewayError("UNSAFE_PATH", "Expected a private, current-user-owned resource")


def private_bytes(path: Path, limit: int = 1024 * 1024, *, allow_owner_execute: bool = False) -> bytes:
    try:
        # Reject known special files before opening; keep the descriptor check for races.
        check_private(path.lstat(), allow_owner_execute=allow_owner_execute)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            check_private(os.fstat(stream.fileno()), allow_owner_execute=allow_owner_execute)
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise GatewayError("CONFIG_ERROR", "Configuration exceeds its size limit")
        return raw
    except OSError as exc:
        raise GatewayError("CONFIG_ERROR", "Required private configuration is unavailable") from exc


def trusted_path(value: str, *, directory: bool = False) -> Path:
    """Preserve venv interpreter spelling: resolving its symlink would bypass the venv."""
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or any(ord(c) < 32 for c in value):
        raise GatewayError("CONFIG_ERROR", "Paths must be absolute and contain no control characters")
    path = Path(value)
    try:
        resolved = path.resolve(strict=True)
        st = resolved.stat()
        if not (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)):
            raise GatewayError("UNSAFE_PATH", "Unexpected path type")
        for candidate in (path, *path.parents, resolved, *resolved.parents):
            info = candidate.stat()
            sticky_dir = stat.S_ISDIR(info.st_mode) and bool(info.st_mode & stat.S_ISVTX)
            if info.st_uid not in {0, os.getuid()} or (info.st_mode & 0o022 and not sticky_dir):
                raise GatewayError("UNSAFE_PATH", "Path is writable outside the trusted owner")
        return path
    except OSError as exc:
        raise GatewayError("CONFIG_ERROR", "Configured path is unavailable") from exc
