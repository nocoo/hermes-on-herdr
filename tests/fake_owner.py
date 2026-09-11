"""Fake Herdr speaks the pinned API and only launches tests/process_fixture.py."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

from hermes_gateway_herdr.config import PLUGIN_ID
from hermes_gateway_herdr.identity import capture, same_process, signal_verified
from helpers import SocketServer, json_lines, private_file, wait_until


class FakeOwner:
    def __init__(self, fixture, plan=None):
        self.fixture, self.config = fixture, fixture.config
        private_file(fixture.root / "plan.json", json.dumps(plan or {}))
        self.processes, self.records = [], []
        self.workspaces = [{"workspace_id": "w-user", "label": "Hermes Control"}]
        self.panes = {"pane-user": {"workspace_id": "w-user", "tab_id": "tab-user", "pane_id": "pane-user", "terminal_id": "terminal-user"}}
        self.pids = {"pane-user": os.getpid()}
        self.enabled = True
        self.drop_workspace = self.drop_pane = False
        self.error_after_open = False
        self.before_open = self.after_open = None
        self.mutex = threading.Lock()
        self.server = SocketServer(self.config.owner_socket, self.answer)

    def answer(self, request):
        method, params = request["method"], request.get("params", {})
        if method == "ping":
            result = {"version": "0.9.0"}
        elif method == "plugin.list":
            result = {"plugins": [{"plugin_id": PLUGIN_ID, "plugin_root": str(self.config.plugin_root), "enabled": self.enabled}]}
        elif method == "session.snapshot":
            result = {"snapshot": {"workspaces": list(self.workspaces), "panes": list(self.panes.values())}}
        elif method == "workspace.create":
            assert params["focus"] is False
            with self.mutex:
                number = len(self.workspaces)
                workspace = {"workspace_id": f"w-created-{number}", "label": params["label"]}
                self.workspaces.append(workspace)
            if self.drop_workspace:
                return None
            result = {"workspace": workspace, "tab": {"tab_id": f"tab-shell-{number}"},
                      "root_pane": {"pane_id": f"pane-shell-{number}"}}
        elif method == "plugin.pane.open":
            if self.before_open:
                self.before_open()
            assert params["plugin_id"] == PLUGIN_ID and params["entrypoint"] == "gateway"
            assert params["focus"] is False and params["placement"] == "tab"
            assert params["cwd"] == str(self.config.plugin_root)
            assert set(params["env"]) == {"HGH_OWNER_KEY", "HGH_GENERATION"}
            with self.mutex:
                number = len(self.processes)
                pane = {"workspace_id": params["workspace_id"], "tab_id": f"tab-created-{number}",
                        "pane_id": f"pane-created-{number}", "terminal_id": f"terminal-created-{number}"}
                self.panes[pane["pane_id"]] = pane
                env = self.fixture.context(params["env"]["HGH_GENERATION"])
                env.update({f"HERDR_{key.upper()}": pane[key] for key in ("workspace_id", "tab_id", "pane_id")})
                process = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).with_name("process_fixture.py")),
                                            "supervisor", str(self.config.config_dir / "config.json")], env=env,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           start_new_session=True)
                self.processes.append(process)
                self.records.append(capture(process.pid))
                self.pids[pane["pane_id"]] = process.pid
            if self.after_open:
                self.after_open()
            if self.drop_pane:
                return None
            if self.error_after_open:
                return {"id": request["id"], "error": {"code": "fixture_response_failed", "message": "FAKE_SECRET"}}
            result = {"plugin_pane": {"plugin_id": PLUGIN_ID, "entrypoint": "gateway", "pane": pane}}
        elif method == "pane.get":
            pane = self.panes.get(params["pane_id"])
            if pane is None:
                return {"id": request["id"], "error": {"code": "pane_not_found", "message": "fixture"}}
            result = {"pane": pane}
        elif method == "pane.process_info":
            result = {"process_info": {"pane_id": params["pane_id"], "shell_pid": self.pids.get(params["pane_id"])}}
        else:
            raise AssertionError(f"Unexpected API mutation: {method}")
        return {"id": request["id"], "result": result}

    def close(self):
        errors = []
        for process, record in zip(self.processes, self.records):
            if process.poll() is None and record and same_process(record):
                signal_verified(record, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                signal_verified(record, signal.SIGKILL)
                process.wait(timeout=3)
            process.stdout.close()
            errors.append(process.stderr.read().decode())
            process.stderr.close()
        records = json_lines(self.fixture.root / "children.jsonl")
        task = self.fixture.root / "task.json"
        if task.exists():
            records.append(json.loads(task.read_text()))
        for record in records:
            if same_process(record):
                signal_verified(record, signal.SIGKILL)
                wait_until(lambda: not same_process(record))
        self.server.close()
        if any(errors):
            raise AssertionError(errors)
