"""Validate the JSON endpoint; release and binary wire versions are diagnostic."""

from .errors import GatewayError


def check_herdr_compatibility(result: dict) -> dict:
    if result.get("type") != "pong":
        raise GatewayError("PROTOCOL_ERROR", "Herdr JSON ping must return pong")
    # Metadata is not a plugin API contract. Missing or unusable values only
    # affect diagnostics; actual RPC response and ownership checks remain strict.
    version, protocol = result.get("version"), result.get("protocol")
    if not isinstance(version, str) or not 0 < len(version) <= 128 or not version.isprintable():
        version = None
    if type(protocol) is not int or not 0 <= protocol <= 0xFFFFFFFF:
        protocol = None
    return {"version": version, "protocol": protocol}
