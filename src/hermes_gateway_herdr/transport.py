"""Bounded local JSON transport, also usable by system-Python recovery."""

import json
import os
from pathlib import Path
import socket
import stat
import struct
import time

from .errors import GatewayError
from .paths import json_object as decode_object


def check_socket(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise GatewayError("RPC_UNAVAILABLE", "Control socket is unavailable") from exc
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise GatewayError("UNSAFE_PATH", "Control socket has an unexpected type, owner or mode")


def check_peer(connection: socket.socket) -> None:
    if hasattr(socket, "SO_PEERCRED"):
        _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != os.getuid():
            raise GatewayError("UNSAFE_PEER", "Socket peer belongs to another user")
    elif hasattr(connection, "getpeereid"):
        uid, _ = connection.getpeereid()
        if uid != os.getuid():
            raise GatewayError("UNSAFE_PEER", "Socket peer belongs to another user")


def exchange(path: Path, payload: dict, *, timeout: float = 2, limit: int = 512 * 1024) -> dict:
    check_socket(path)
    deadline = time.monotonic() + timeout
    outgoing = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode() + b"\n"
    if len(outgoing) > 16 * 1024:
        raise GatewayError("PROTOCOL_ERROR", "Request is too large")
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError
        return value
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(remaining())
            connection.connect(str(path))
            check_peer(connection)
            connection.settimeout(remaining())
            connection.sendall(outgoing)
            raw = bytearray()
            while b"\n" not in raw:
                connection.settimeout(remaining())
                chunk = connection.recv(min(4096, limit + 1 - len(raw)))
                if not chunk:
                    raise GatewayError("PROTOCOL_ERROR", "Response ended before newline")
                raw.extend(chunk)
                if len(raw) > limit:
                    raise GatewayError("PROTOCOL_ERROR", "Response is too large")
            line, remainder = bytes(raw).split(b"\n", 1)
            if remainder.strip():
                raise GatewayError("PROTOCOL_ERROR", "Multiple response frames")
            response = decode_object(line)
            if response.get("id") != payload.get("id"):
                raise GatewayError("PROTOCOL_ERROR", "Response id does not match")
            return response
    except (TimeoutError, OSError) as exc:
        raise GatewayError("RPC_UNAVAILABLE", "Control request did not complete") from exc
