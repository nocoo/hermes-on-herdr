"""All hooks, actions and read-only inspection share this dispatcher."""

import argparse
import json
import os
from pathlib import Path
import time
import uuid

from . import __version__
from .config import Config, HERDR_VERSION, HERMES_SHA, installation_preflight, preflight, profile_preflight
from .controller import Controller
from .errors import GatewayError
from .paths import check_private
from .rpc import Herdr, decode_object
from .state import Store
from .supervisor import Supervisor

ACTIONS = ("start", "resume", "pause", "stop", "restart")


def parser():
    result = argparse.ArgumentParser(prog="hermes-gateway-herdr", allow_abbrev=False,
                                     description="Control a dedicated, pane-owned Gateway. Real-host validation is pending.")
    result.add_argument("--config", type=Path, required=True)
    result.add_argument("--owner-socket", type=Path, help="Explicit owner context for commands outside a Herdr hook")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("ensure", "supervise", *ACTIONS, "status", "doctor", "logs", "bind"):
        command = commands.add_parser(name, allow_abbrev=False)
        command.add_argument("--json", action="store_true", help="JSON output (also the default)")
        if name == "ensure":
            command.add_argument("--source", choices=("manual", "startup", "event", "timer"), default="manual")
        if name in ACTIONS:
            command.add_argument("--request-id")
            command.add_argument("--expected-revision", type=int)
        if name in {"stop", "pause"}:
            command.add_argument("--wait", type=float, metavar="SECONDS", help="Wait for verified completion, up to 60 seconds")
        if name == "status":
            command.add_argument("--require-ready", action="store_true")
        if name == "logs":
            command.add_argument("--lines", type=int, default=50)
        if name == "bind":
            choice = command.add_mutually_exclusive_group()
            choice.add_argument("--apply", action="store_true", help="Initialize control state in the existing dedicated Profile")
            choice.add_argument("--dry-run", action="store_true", help="Show the binding plan (default)")
    return result


def binding_plan(config, *, apply=False):
    preflight(config)
    binding = config.binding(uuid.uuid4().hex)
    exists = config.state_dir.exists() or config.state_dir.is_symlink()
    if exists:
        with Store(config.state_dir) as store:
            current = store.read("binding.json", required=True)
            config.check_binding(current)
            binding = current
    if apply:
        with Store.initialize(config.state_dir, binding) as store:
            intent = store.intent()
    else:
        intent = {"desired": "unchanged" if exists else "paused"}
    return {"schema": 1, "state": "BOUND" if apply else "PLAN", "profile_home": str(config.profile_home),
            "owner_socket": str(config.owner_socket), "desired": intent["desired"], "existing": exists,
            "control_directory": str(config.state_dir), "creates_profile": False,
            "files": ["binding.json", "intent.json", "mutation.lock"], "starts_gateway": False}


def doctor(config):
    deadline = time.monotonic() + 4.5
    checks = []
    for name, inspect in (("profile", lambda: profile_preflight(config)),
                          ("hermes_version", lambda: installation_preflight(config, deadline=deadline))):
        try:
            inspect()
            checks.append({"name": name, "ok": True, "code": "OK"})
        except GatewayError as exc:
            checks.append({"name": name, "ok": False, "code": exc.code})
    try:
        client = Herdr(config)
        client.deadline = deadline
        client.available()
        enabled = client.enabled()
        checks.append({"name": "owner", "ok": enabled, "code": "OK" if enabled else "DISABLED"})
    except GatewayError as exc:
        checks.append({"name": "owner", "ok": False, "code": exc.code})
    try:
        status = Controller(config, budget=max(0.01, deadline - time.monotonic())).status()
    except GatewayError as exc:
        status = {"state": "ERROR", "code": exc.code}
    return {"schema": 1, "state": "DIAGNOSIS", "checks": checks, "runtime": status,
            "baseline": {"plugin": __version__, "herdr": HERDR_VERSION, "hermes_sha": HERMES_SHA},
            "real_validation": "NOT_RUN", "recovery": "next_owner_event"}


def events(config, lines):
    if not 1 <= lines <= 200:
        raise GatewayError("INVALID_ARGUMENT")
    with Store(config.state_dir) as store:
        config.check_binding(store.read("binding.json", required=True))
    directory = config.state_dir / "logs"
    if not directory.exists():
        return {"schema": 1, "events": []}
    check_private(directory.lstat(), directory=True)
    try:
        fd = os.open(directory / "events.jsonl", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return {"schema": 1, "events": []}
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        check_private(info, allow_unlinked=True)
        stream.seek(max(0, info.st_size - 65536))
        raw = stream.read(65536)
    allowed = {"time", "event", "generation", "pid", "revision", "code", "state", "stage"}
    output = []
    for line in raw.splitlines()[-lines:]:
        try:
            item = decode_object(line)
        except GatewayError:
            continue
        output.append({key: value for key, value in item.items() if key in allowed})
    return {"schema": 1, "events": output}


def result_code(result, *, command, source="manual", require_ready=False):
    state = result.get("state")
    if command == "status":
        return 0 if not require_ready or state == "READY" else 10
    if result.get("accepted") or state in {"NOT_OWNER", "IGNORED", "CANCELLED", "DISABLED"}:
        return 0
    if state in {"BUSY", "PENDING", "PENDING_UNKNOWN", "UNKNOWN", "ORPHAN", "DRAINING"}:
        return 0 if command == "ensure" and source != "manual" else 10
    if state == "FUSED":
        return 20
    return 0


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.command in ACTIONS:
            if (arguments.request_id is None) != (arguments.expected_revision is None):
                raise GatewayError("INVALID_ARGUMENT", "Explicit request IDs require an expected revision")
            if arguments.expected_revision is not None and arguments.expected_revision < 0:
                raise GatewayError("INVALID_ARGUMENT")
            if arguments.command in {"stop", "pause"} and arguments.wait is not None and not 0 < arguments.wait <= 60:
                raise GatewayError("INVALID_ARGUMENT")
        config = Config.load(arguments.config)
        env = dict(os.environ)
        if arguments.owner_socket is not None:
            env["HERDR_SOCKET_PATH"] = str(arguments.owner_socket)
        command = arguments.command
        if command == "supervise":
            return Supervisor(config, env).run()
        if command == "bind":
            result = binding_plan(config, apply=arguments.apply)
        elif command == "logs":
            result = events(config, arguments.lines)
        elif command == "doctor":
            result = doctor(config)
            print(json.dumps(result, allow_nan=False))
            return 0 if all(check["ok"] for check in result["checks"]) and result["runtime"].get("state") != "ERROR" else 20
        else:
            controller = Controller(config)
            if command == "status":
                result = controller.status()
            elif command == "ensure":
                result = controller.ensure(env, source=arguments.source)
            else:
                result = controller.action(command, env, request_id=arguments.request_id, expected_revision=arguments.expected_revision)
                if command in {"pause", "stop"} and arguments.wait is not None:
                    deadline = time.monotonic() + arguments.wait
                    while True:
                        status = Controller(config, budget=max(0.01, deadline - time.monotonic())).status()
                        if status["state"] == "PAUSED":
                            result.update(completed=True, runtime=status)
                            break
                        if time.monotonic() >= deadline or status["state"] == "ORPHAN":
                            result.update(completed=False, runtime=status, code="STOP_FAILED")
                            print(json.dumps(result, allow_nan=False))
                            return 30
                        time.sleep(0.05)
        print(json.dumps(result, allow_nan=False))
        return result_code(result, command=command, source=getattr(arguments, "source", "manual"),
                           require_ready=getattr(arguments, "require_ready", False))
    except GatewayError as exc:
        result = {"schema": 1, "state": "NOT_OWNER" if exc.code == "NOT_OWNER" else "ERROR", "code": exc.code}
        print(json.dumps(result))
        if exc.code == "NOT_OWNER" or (arguments.command == "ensure" and arguments.source != "manual" and exc.exit_code == 10):
            return 0
        return exc.exit_code
    except (OSError, ValueError, TypeError):
        print(json.dumps({"schema": 1, "state": "ERROR", "code": "IO_ERROR"}))
        return 30
