"""System-Python entrypoint; recovery must not import the managed runtime."""

import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__
from .errors import GatewayError
from .paths import check_private, json_object, private_bytes, trusted_path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ID = "nocoo.hermes-gateway"
RECOVERY_TAB = "Hermes · 恢复: hermes-on-herdr"
RECOVERY_HINT = "Dashboard 未就绪？运行 hermes-on-herdr 查看原因并恢复。"


def config_path(explicit=None):
    if explicit is not None:
        return Path(explicit)
    directory = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    if directory:
        return Path(directory) / "config.json"
    # Match Herdr's plugin registry, including its XDG override. No Profile scan.
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "herdr" / "plugins" / "config" / PLUGIN_ID / "config.json"


def read_config(path):
    path = Path(path)
    if not path.is_absolute():
        raise GatewayError("CONFIG_ERROR")
    if not path.exists() and not path.is_symlink():
        raise GatewayError("SETUP_REQUIRED")
    trusted_path(str(path.parent), directory=True)
    check_private(path.parent.stat(), directory=True)
    return json_object(private_bytes(path, 65536), code="CONFIG_ERROR")


def runtime_argv(config, arguments):
    data = read_config(config)
    hint = private_bytes(config.parent / "runtime-python", 4096).decode().splitlines()
    if len(hint) != 1:
        raise GatewayError("CONFIG_ERROR")
    interpreter = trusted_path(hint[0])
    if data.get("python_bin") != str(interpreter) or not os.access(interpreter, os.X_OK):
        raise GatewayError("CONFIG_ERROR")
    trusted_path(str(ROOT), directory=True)
    entry = trusted_path(str(ROOT / "src" / "hermes_gateway_herdr" / "__main__.py"))
    return [str(interpreter), "-I", "-B", str(entry), "--config", str(config), *arguments]


def recover_failed_supervisor(code):
    if code and "supervise" in sys.argv[1:] and sys.stdin.isatty() and sys.stdout.isatty():
        # Exec preserves the pane's root PID. A wrapper process would break ownership.
        arguments = ["recover" if arg == "supervise" else arg for arg in sys.argv[1:]]
        os.execv("/usr/bin/python3", ["/usr/bin/python3", "-IS", str(ROOT / "bin" / "hermes-on-herdr"), *arguments])
    return code


def main():
    parser = argparse.ArgumentParser(prog="hermes-on-herdr", add_help=False, allow_abbrev=False)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--owner-socket", type=Path)
    options, arguments = parser.parse_known_args()
    if not arguments or arguments[0] == "recover":
        from .recovery import main as recover
        return recover(config_path(options.config), arguments[1:] if arguments else [], owner_socket=options.owner_socket)
    if options.config is None and ("--help" in arguments or "-h" in arguments):
        print("Usage: hermes-on-herdr [recover]\n"
              "       hermes-on-herdr --config /absolute/config.json COMMAND\n"
              "       hermes-on-herdr --version\n"
              "Commands: recover, ensure, supervise, start, resume, pause, stop, restart, status, doctor, logs, bind, dashboard, monitor\n"
              "Without arguments, open recovery using the installed plugin configuration. bind defaults to a dry run.")
        return 0
    try:
        if options.owner_socket is not None:
            arguments = ["--owner-socket", str(options.owner_socket), *arguments]
        argv = runtime_argv(config_path(options.config), arguments)
        os.execv(argv[0], argv)
    except (GatewayError, OSError, ValueError, UnicodeError) as error:
        code = error.code if isinstance(error, GatewayError) else "CONFIG_ERROR"
        print(json.dumps({"schema": 1, "state": "ERROR", "code": code}))
        return recover_failed_supervisor(20)
