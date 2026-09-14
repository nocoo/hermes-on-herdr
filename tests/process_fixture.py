"""Only test programs execute here. No command in this file starts Herdr or Hermes."""

from dataclasses import replace
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).resolve().parent)]

from hermes_gateway_herdr.config import Config, profile_preflight
from hermes_gateway_herdr.controller import Controller
from hermes_gateway_herdr.identity import capture, same_process
from hermes_gateway_herdr.lifecycle import Limits
from hermes_gateway_herdr.rpc import Herdr
from hermes_gateway_herdr.supervisor import Supervisor
from helpers import SocketServer, private_file
from test_rpc import gateway_payloads


def append(path, value):
    with path.open("a") as stream:
        stream.write(json.dumps(value) + "\n")
    path.chmod(0o600)


def gateway(config_path, index):
    config = Config.load(config_path)
    root = config.agent_cwd
    plan = json.loads((root / "plan.json").read_text())
    record = capture(os.getpid())
    append(root / "children.jsonl", dict(record, environment=dict(os.environ)))
    stopping = [None]
    def request_stop(number, _):
        append(root / "signals.jsonl", {"pid": os.getpid(), "signal": number})
        if number == signal.SIGTERM and plan.get("ignore_term"):
            return
        stopping[0] = 75 if number == signal.SIGUSR1 else 0
    for number in (signal.SIGTERM, signal.SIGUSR1):
        signal.signal(number, request_stop)
    lock_path = config.profile_home / "gateway.lock"
    # Match upstream open(a+): privacy must come from the supervisor's child umask.
    lock = lock_path.open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    identity, status = gateway_payloads(config, record)
    private_file(config.profile_home / "gateway.pid", json.dumps({"pid": record["pid"], "start_time": identity["start_time"]}))
    def answer(request):
        if plan.get("stall_probe"):
            time.sleep(plan["stall_probe"])
        payload = identity if request["verb"] == "identify" else dict(status, answered_at=time.time())
        return {"id": request["id"], "protocol": 1, "ok": True, "result": payload}
    server = SocketServer(config.profile_home / "gateway.sock", answer)
    task = None
    if plan.get("task"):
        task = subprocess.Popen([sys.executable, "-I", "-B", __file__, "task", str(root)], start_new_session=True)
        # Wait for the task to install its signal policy before a test can stop the Gateway.
        deadline = time.monotonic() + 2
        while not (root / "task.json").exists() and time.monotonic() < deadline:
            time.sleep(0.005)
    if plan.get("flood"):
        def flood(fd):
            for _ in range(256):
                os.write(fd, b"FAKE_RAW_SECRET " * 1024)
        for fd in (1, 2):
            threading.Thread(target=flood, args=(fd,), daemon=True).start()
    private_file(root / "gateway-up", str(os.getpid()))
    exits = plan.get("exits", [None])
    code = exits[min(index, len(exits) - 1)]
    deadline = time.monotonic() + plan.get("exit_after", 0.15)
    while stopping[0] is None and (code is None or time.monotonic() < deadline):
        time.sleep(0.005)
    result = stopping[0] if stopping[0] is not None else code
    # Test socket worker delays must not artificially make normal signal cleanup slow.
    server.stop.set()
    server.socket.close()
    server.path.unlink(missing_ok=True)
    (config.profile_home / "gateway.pid").unlink(missing_ok=True)
    lock.close()
    return result


def supervise(config_path):
    config = Config.load(config_path)
    root = config.agent_cwd
    plan = json.loads((root / "plan.json").read_text())
    settings = dict(poll=0.005, rpc=0.15, r0=1, probe=0.05, recheck=0.1, ready_spacing=0.03, ready=0.3,
                    owner_grace=0.4, stop=0.25, kill=0.25, restart=0.3, restart_spacing=0.03,
                    backoff=(0.02, 0.03, 0.05, 0.1, 0.15, 0.2))
    settings.update(plan.get("limits", {}))
    limits = replace(Limits(), **settings)
    launched = []
    launch_file = root / "launches.jsonl"
    attempts = 0
    def launch(argv, **kwargs):
        nonlocal attempts
        assert argv == config.gateway_argv(), argv
        assert kwargs["start_new_session"] is False
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["umask"] == 0o077
        attempts += 1
        if plan.get("fail_first_spawn") and attempts == 1:
            raise OSError("fixture spawn failure")
        index = len(launch_file.read_text().splitlines()) if launch_file.exists() else 0
        append(launch_file, {"argv": argv, "active_previous": sum(same_process(item) for item in launched),
                             "stdin": "DEVNULL", "same_session": True})
        child = subprocess.Popen([sys.executable, "-I", "-B", __file__, "gateway", str(config_path), str(index)], **kwargs)
        if plan.get("crash_before_child_record"):
            os._exit(9)
        record = capture(child.pid)
        if record:
            launched.append(record)
        return child
    def check(config):
        profile_preflight(config)
        if plan.get("hold_first_check") and not (root / "check-complete").exists():
            private_file(root / "check-complete", "1")
            deadline = time.monotonic() + 3
            while not (root / "check-release").exists() and time.monotonic() < deadline:
                time.sleep(0.005)
    if plan.get("dashboard_failure"):
        from unittest.mock import patch
        class BrokenDisplay:
            @classmethod
            def start(cls, *_):
                if plan["dashboard_failure"] == "start":
                    raise RuntimeError("fixture display startup failure")
                return cls()

            def poll(self):
                if plan["dashboard_failure"] == "poll":
                    raise RuntimeError("fixture display polling failure")

            def close(self, **_):
                if plan["dashboard_failure"] == "close":
                    raise RuntimeError("fixture display cleanup failure")
        with patch("hermes_gateway_herdr.supervisor.Display", BrokenDisplay):
            return Supervisor(config, dict(os.environ), limits=limits, launch=launch, check=check).run()
    return Supervisor(config, dict(os.environ), limits=limits, launch=launch, check=check).run()


def dashboard_fixture(config_path, mode):
    from unittest.mock import patch
    from hermes_gateway_herdr import dashboard
    from hermes_gateway_herdr.dashboard_demo import demo_snapshot
    config = Config.load(config_path)
    class Samples:
        def __init__(self, _, *, host):
            self.host, self.selected, self.count = host, config.profile_id, 0

        def collect(self, *, managed_only=False):
            self.count += 1
            append(config.agent_cwd / "samples.jsonl", {"time": time.monotonic(), "host": self.host,
                                                       "selected": self.selected, "managed_only": managed_only})
            if mode == "error" and self.count > 1:
                raise RuntimeError("fixture collector failure")
            return demo_snapshot(1 if managed_only else 20, now=time.time())
    original_app = dashboard.App
    def app(options):
        result = original_app(options)
        if mode == "motion":
            result.on("frame", lambda stats: append(config.agent_cwd / "frames.jsonl",
                                                     {"time": time.monotonic(), "cells": stats.changed_cells}))
        return result
    with patch.object(dashboard, "Monitor", Samples), patch.object(dashboard, "App", app):
        return dashboard.run_dashboard(config, startup=mode == "startup")


if __name__ == "__main__":
    if sys.argv[1] == "controller":
        config = Config.load(Path(sys.argv[2]))
        point = sys.argv[3]
        class CrashHerdr(Herdr):
            def call(self, method, *args, **kwargs):
                selected = "workspace" if method == "workspace.create" else "pane" if method == "plugin.pane.open" else "none"
                if point == "before_" + selected:
                    os._exit(91)
                result = super().call(method, *args, **kwargs)
                if point == "after_" + selected:
                    os._exit(91)
                return result
        Controller(config, herdr=CrashHerdr(config)).ensure(dict(os.environ))
        raise SystemExit(0)
    if sys.argv[1] == "supervisor":
        raise SystemExit(supervise(Path(sys.argv[2])))
    if sys.argv[1] == "gateway":
        raise SystemExit(gateway(Path(sys.argv[2]), int(sys.argv[3])))
    if sys.argv[1] == "dashboard":
        raise SystemExit(dashboard_fixture(Path(sys.argv[2]), sys.argv[3]))
    if sys.argv[1] == "task":
        root = Path(sys.argv[2])
        plan = json.loads((root / "plan.json").read_text())
        if plan.get("task_ignore_term"):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        private_file(root / "task.json", json.dumps(capture(os.getpid())))
        while True:
            time.sleep(0.1)
