"""Shared, dependency-free checks for the live Herdr JSON API."""

import re

from .errors import GatewayError

HERDR_MIN_VERSION = (0, 9, 0)
HERDR_MAX_VERSION = (0, 10, 0)
HERDR_PROTOCOLS = (22,)
HERDR_VERSION_RANGE = ">=" + ".".join(map(str, HERDR_MIN_VERSION)) + ",<" + ".".join(map(str, HERDR_MAX_VERSION))
_VERSION = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def check_herdr_compatibility(result: dict) -> dict:
    version, protocol = result.get("version"), result.get("protocol")
    match = _VERSION.fullmatch(version) if isinstance(version, str) and len(version) <= 128 else None
    if result.get("type") != "pong" or match is None or type(protocol) is not int or protocol < 0:
        raise GatewayError("PROTOCOL_ERROR", "Herdr ping must return pong, a semantic version and an integer protocol")
    if protocol not in HERDR_PROTOCOLS:
        raise GatewayError("UNSUPPORTED_VERSION", "Herdr protocol is unsupported; supported protocols: "
                           + ", ".join(map(str, HERDR_PROTOCOLS)))
    # Protocol 22 also covers older releases outside our reviewed plugin API. In 0.x,
    # a new minor release can break that API without changing the wire protocol.
    release = tuple(map(int, match.group(1, 2, 3)))
    if match.group(4) or not HERDR_MIN_VERSION <= release < HERDR_MAX_VERSION:
        raise GatewayError("UNSUPPORTED_VERSION", f"Herdr requires a stable release in {HERDR_VERSION_RANGE}")
    return {"version": version, "protocol": protocol}
