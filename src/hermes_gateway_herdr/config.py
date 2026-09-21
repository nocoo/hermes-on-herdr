"""Configuration inspection never imports Hermes or loads another profile's credentials."""

from dataclasses import dataclass
import os
from pathlib import Path
import re

from .errors import GatewayError
from .identity import owner_key
from .paths import json_object, private_bytes, trusted_path
from .state import CONTROL_DIR, check_private

PLUGIN_ID = "nocoo.hermes-gateway"
PANE_KEYS = ("HERDR_SOCKET_PATH", "HERDR_WORKSPACE_ID", "HERDR_TAB_ID", "HERDR_PANE_ID")
ID_PATTERN = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")


@dataclass(frozen=True)
class Config:
    profile_id: str
    profile_home: Path
    owner_socket: Path
    owner_session: str
    python_bin: Path
    hermes_bin: Path
    hermes_root: Path
    herdr_bin: Path
    agent_cwd: Path
    plugin_root: Path
    expected_platforms: tuple[str, ...]
    config_dir: Path

    @classmethod
    def load(cls, path: Path):
        try:
            raw = json_object(private_bytes(path, 64 * 1024), code="CONFIG_ERROR")
            if not isinstance(raw, dict) or type(raw.get("schema")) is not int or raw["schema"] != 1:
                raise ValueError("schema")
            expected = {field for field in cls.__dataclass_fields__ if field != "config_dir"}
            if set(raw) != expected | {"schema"}:
                raise ValueError("fields")
            if (not isinstance(raw["profile_id"], str) or raw["profile_id"] == "default"
                    or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", raw["profile_id"])):
                raise ValueError("profile")
            if not isinstance(raw["owner_session"], str) or not ID_PATTERN.fullmatch(raw["owner_session"]):
                raise ValueError("session")
            platforms = raw["expected_platforms"]
            if (not isinstance(platforms, list) or not platforms or len(set(platforms)) != len(platforms)
                    or not all(isinstance(item, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", item)
                               for item in platforms)):
                raise ValueError("platforms")
            directories = {key: trusted_path(raw[key], directory=True) for key in
                           ("profile_home", "hermes_root", "agent_cwd", "plugin_root")}
            directories["profile_home"] = directories["profile_home"].resolve(strict=True)
            home = directories["profile_home"]
            if home.parent.name != "profiles" or home.name != raw["profile_id"]:
                raise ValueError("profile layout")
            check_private(home.stat(), directory=True)
            socket_path = Path(raw["owner_socket"])
            if not socket_path.is_absolute() or any(ord(c) < 32 for c in str(socket_path)):
                raise ValueError("socket")
            socket_path = trusted_path(str(socket_path.parent), directory=True).resolve() / socket_path.name
            binaries = {key: trusted_path(raw[key]) for key in ("python_bin", "hermes_bin", "herdr_bin")}
            if not all(os.access(binary, os.X_OK) for binary in binaries.values()):
                raise ValueError("executable")
            config_dir = trusted_path(str(Path(path).parent), directory=True)
            check_private(config_dir.stat(), directory=True)
            python_hint = private_bytes(config_dir / "runtime-python", 4096).decode().splitlines()
            if python_hint != [str(binaries["python_bin"])]:
                raise ValueError("runtime-python")
            return cls(raw["profile_id"], owner_socket=socket_path, owner_session=raw["owner_session"],
                       expected_platforms=tuple(platforms), config_dir=config_dir, **directories, **binaries)
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise GatewayError("CONFIG_ERROR", "Invalid plugin configuration") from exc

    @property
    def key(self) -> str:
        return owner_key(self.profile_home, self.owner_socket)

    @property
    def state_dir(self) -> Path:
        return self.profile_home / CONTROL_DIR

    def binding(self, binding_id: str) -> dict:
        return {"schema": 1, "binding_id": binding_id, "owner_key": self.key, "uid": os.getuid(),
                "profile_id": self.profile_id, "profile_home": str(self.profile_home),
                "owner_socket": str(self.owner_socket)}

    def check_binding(self, record: dict) -> None:
        if not isinstance(record.get("binding_id"), str) or record != self.binding(record["binding_id"]):
            raise GatewayError("OWNERSHIP_CONFLICT", "Configuration does not match the installation binding")

    def check_context(self, env: dict, *, pane: bool = False) -> dict:
        supplied = env.get("HERDR_SOCKET_PATH", "")
        if not supplied or not Path(supplied).is_absolute():
            raise GatewayError("NOT_OWNER", "No owner session context")
        actual = Path(supplied).parent.resolve() / Path(supplied).name
        if actual != self.owner_socket:
            raise GatewayError("NOT_OWNER", "This session is not the configured owner")
        result = {key: env.get(key, "") for key in PANE_KEYS}
        if pane and not all(isinstance(result[key], str) and ID_PATTERN.fullmatch(result[key]) for key in PANE_KEYS[1:]):
            raise GatewayError("INVALID_IDENTITY", "Missing real pane context")
        return result

    def gateway_argv(self) -> list[str]:
        return [str(self.hermes_bin), "-p", self.profile_id, "gateway", "run", "--external-supervisor"]

    def child_env(self, source: dict) -> dict:
        self.check_context(source, pane=True)
        allowed = ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "COLORTERM",
                   "HERMES_ENABLE_PROJECT_PLUGINS")
        env = {key: source[key] for key in allowed if source.get(key)}
        env.update({key: source[key] for key in PANE_KEYS})
        env.update({
            "HERMES_HOME": str(self.profile_home), "HERDR_ENV": "1", "HERDR_BIN_PATH": str(self.herdr_bin),
            "PATH": os.pathsep.join(dict.fromkeys((str(self.herdr_bin.parent), str(self.python_bin.parent),
                                                    "/usr/bin", "/bin", "/usr/sbin", "/sbin"))),
            "TMPDIR": "/tmp", "GATEWAY_MULTIPLEX_PROFILES": "0",
            "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
        })
        return env


def profile_preflight(config: Config) -> None:
    """Keep the selected Profile and supervisor context intact; Hermes owns its settings."""
    path = config.profile_home / ".env"
    if not path.exists() and not path.is_symlink():
        return
    try:
        dotenv = private_bytes(path).decode("utf-8-sig").replace("\r", "\n")
        reserved = {"HERMES_HOME", "GATEWAY_MULTIPLEX_PROFILES", "HERMES_GATEWAY_LOCK_DIR",
                    "HERMES_GATEWAY_EXTERNAL_SUPERVISOR", "INVOCATION_ID", "XPC_SERVICE_NAME",
                    "LAUNCHD_SOCKET", "HERMES_DESKTOP_MANAGED", "HERMES_S6_SUPERVISED_CHILD"}
        for match in re.finditer(r"(?m)^\s*(?:export\s+)?('?)([A-Za-z_][A-Za-z0-9_]*)\1\s*=", dotenv):
            if match[2] in reserved or match[2].startswith(("HERDR_", "HGH_")):
                raise ValueError("environment override")
    except (ValueError, UnicodeError) as exc:
        raise GatewayError("CONFIG_ERROR", "Check Profile configuration: launch environment override or encoding") from exc
