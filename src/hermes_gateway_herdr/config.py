"""Configuration inspection never imports Hermes or loads another profile's credentials."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import parse_qsl, urlsplit

import yaml

from .errors import GatewayError
from .identity import owner_key
from .paths import json_object, private_bytes, trusted_path
from .state import CONTROL_DIR, check_private

PLUGIN_ID = "nocoo.hermes-gateway"
HERDR_VERSION = "0.9.0"
HERMES_SHA = "b7ac3ba1cdf89f94dfe86de27e01358b194f4053"
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
        allowed = ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "COLORTERM")
        env = {key: source[key] for key in allowed if source.get(key)}
        env.update({key: source[key] for key in PANE_KEYS})
        env.update({
            "HERMES_HOME": str(self.profile_home), "HERDR_ENV": "1", "HERDR_BIN_PATH": str(self.herdr_bin),
            "PATH": os.pathsep.join(dict.fromkeys((str(self.herdr_bin.parent), str(self.python_bin.parent),
                                                    "/usr/bin", "/bin", "/usr/sbin", "/sbin"))),
            "TMPDIR": "/tmp", "HERMES_ENABLE_PROJECT_PLUGINS": "0", "GATEWAY_MULTIPLEX_PROFILES": "0",
            "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
        })
        return env


class _UniqueYaml(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    pairs = loader.construct_pairs(node, deep=deep)
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate YAML key")
        result[key] = value
    return result


_UniqueYaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def profile_preflight(config: Config) -> None:
    """Structural and policy checks only; platform/model credentials still need real E2E."""
    try:
        data = yaml.load(private_bytes(config.profile_home / "config.yaml"), Loader=_UniqueYaml)
        if not isinstance(data, dict):
            raise ValueError("mapping")
        model = data.get("model", {})
        if (not isinstance(model, dict) or not isinstance(model.get("provider"), str)
                or model["provider"].strip() in {"", "auto"}
                or not isinstance(model.get("default"), str) or not model["default"].strip()):
            raise ValueError("model")
        if any(key in model for key in ("api_key", "token", "password", "secret")):
            raise ValueError("model secret")
        for key in ("base_url", "api_base"):
            if model.get(key):
                url = urlsplit(model[key])
                if url.username or url.password or any(k.lower() in {"key", "api_key", "token", "secret", "password"}
                                                      for k, _ in parse_qsl(url.query)):
                    raise ValueError("URL credential")
        terminal = data.get("terminal", {})
        if (terminal.get("backend") != "local" or terminal.get("home_mode") != "profile"
                or Path(terminal.get("cwd", "")).resolve() != config.agent_cwd.resolve()
                or terminal.get("auto_source_bashrc") is not False or terminal.get("shell_init_files") != []):
            raise ValueError("terminal")
        if (data.get("plugins", {}).get("enabled") != []
                or data.get("gateway", {}).get("multiplex_profiles") is not False
                or data.get("multiplex_profiles", False) is not False
                or type(data.get("nous", {}).get("keepalive_interval_seconds")) is not int
                or data["nous"]["keepalive_interval_seconds"] != 0
                or data.get("mcp_servers") or data.get("hooks")):
            raise ValueError("shared state")
        tools = data.get("platform_toolsets", {})
        for platform in config.expected_platforms:
            selected = tools.get(platform)
            if (not isinstance(selected, list) or "terminal" not in selected
                    or not set(selected) <= {"terminal", "skills", "memory"}):
                raise ValueError("toolsets")
        disabled = data.get("agent", {}).get("disabled_toolsets", [])
        if not isinstance(disabled, list) or not {"cronjob", "browser", "file"} <= set(disabled):
            raise ValueError("disabled tools")
        # .env is for secrets. Never let it rewrite identity or turn policy switches back on.
        dotenv = private_bytes(config.profile_home / ".env").decode()
        forbidden = {"HERMES_HOME", "HOME", "PATH", "PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV",
                     "GATEWAY_MULTIPLEX_PROFILES", "GATEWAY_ALLOW_ALL_USERS", "HERMES_ENABLE_PROJECT_PLUGINS",
                     "HERMES_YOLO_MODE", "HERMES_ACCEPT_HOOKS", "HERMES_IGNORE_USER_CONFIG", "INVOCATION_ID",
                     "HERMES_GATEWAY_LOCK_DIR",
                     "XPC_SERVICE_NAME", "LAUNCHD_SOCKET", "HERMES_DESKTOP_MANAGED", "HERMES_S6_SUPERVISED_CHILD"}
        keys = re.findall(r"(?m)^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", dotenv)
        if any(key in forbidden or key.startswith(("HERDR_", "HGH_")) or key.endswith("_ALLOW_ALL_USERS") for key in keys):
            raise ValueError("environment override")
    except (ValueError, TypeError, AttributeError, yaml.YAMLError, UnicodeError) as exc:
        raise GatewayError("CONFIG_ERROR", "Profile does not meet the dedicated Gateway policy") from exc


def installation_preflight(config: Config, *, deadline: float | None = None) -> None:
    """Inspect the pinned checkout using git; never run the Hermes CLI for preflight."""
    try:
        deadline = deadline if deadline is not None else time.monotonic() + 4
        def remaining():
            duration = min(2, deadline - time.monotonic())
            if duration <= 0:
                raise GatewayError("UNSUPPORTED_VERSION", "Installation inspection deadline exhausted")
            return duration
        result = subprocess.run(["/usr/bin/git", "-C", str(config.hermes_root), "rev-parse", "HEAD"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=remaining(),
                                env={"PATH": "/usr/bin:/bin", "GIT_OPTIONAL_LOCKS": "0"})
        if result.returncode != 0 or result.stdout.strip() != HERMES_SHA:
            raise GatewayError("UNSUPPORTED_VERSION", "Hermes checkout is outside the pinned baseline")
        dirty = subprocess.run(["/usr/bin/git", "-C", str(config.hermes_root), "diff", "--quiet", "HEAD", "--"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=remaining(), env={"PATH": "/usr/bin:/bin", "GIT_OPTIONAL_LOCKS": "0"})
        if dirty.returncode != 0:
            raise GatewayError("UNSUPPORTED_VERSION", "Hermes tracked source is modified")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GatewayError("UNSUPPORTED_VERSION", "Cannot verify the Hermes installation") from exc


def preflight(config: Config, *, deadline: float | None = None) -> None:
    profile_preflight(config)
    installation_preflight(config, deadline=deadline)
