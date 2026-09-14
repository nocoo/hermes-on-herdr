import json
import os
from pathlib import Path
import subprocess
import unittest
import venv
from unittest.mock import patch

from hermes_gateway_herdr import recovery
from hermes_gateway_herdr.bootstrap import PLUGIN_ID, RECOVERY_HINT, RECOVERY_TAB
from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture
from hermes_gateway_herdr.state import Store
from fake_owner import FakeOwner
from helpers import Fixture, ROOT, Terminal, private_file, wait_until


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config_dir / "config.json"
        self.owner = FakeOwner(self.fixture)
        self.addCleanup(self.owner.close)
        self.store = Store.initialize(self.fixture.config.state_dir, self.fixture.config.binding("fixture"))
        self.addCleanup(self.store.close)
        self.environment = patch.dict(os.environ, self.fixture.context(), clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def launch(self, *arguments, config=True, env=None):
        return subprocess.run([str(ROOT / "bin/hermes-on-herdr"),
                               *(["--config", str(self.config)] if config else []), *arguments],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              env=env or dict(os.environ), timeout=8)

    def test_system_python_recovery_handles_broken_bootstrap_without_dependencies_or_writes(self):
        hint = self.config.parent / "runtime-python"
        original_config, original_hint = self.config.read_text(), hint.read_text()
        for failure in ("missing_config", "malformed_config", "missing_hint", "missing_interpreter"):
            with self.subTest(failure=failure):
                private_file(self.config, original_config)
                private_file(hint, original_hint)
                if failure == "missing_config":
                    self.config.unlink()
                elif failure == "malformed_config":
                    private_file(self.config, '{"FAKE_SECRET": bad JSON')
                elif failure == "missing_hint":
                    hint.unlink()
                else:
                    data = json.loads(original_config)
                    data["python_bin"] = str(self.fixture.root / "missing-python")
                    private_file(self.config, json.dumps(data))
                    private_file(hint, data["python_bin"] + "\n")
                before = {path.name: path.read_bytes() for path in self.config.parent.iterdir()}
                result = self.launch("recover", "--json")
                self.assertEqual(0, result.returncode, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual("ERROR", report["state"])
                self.assertNotIn("FAKE_SECRET", result.stdout + result.stderr)
                self.assertEqual(before, {path.name: path.read_bytes() for path in self.config.parent.iterdir()})
                self.assertEqual(failure == "missing_hint", "hint" in {a["id"] for a in report["actions"]})
        isolated = subprocess.run(["/usr/bin/python3", "-IS", "-c",
                                  f"import sys; sys.path.insert(0, {str(ROOT / 'src')!r}); "
                                  "from hermes_gateway_herdr import recovery; "
                                  "assert not {'yaml', 'psutil', 'hqtui'} & sys.modules.keys()"],
                                 capture_output=True, timeout=3)
        self.assertEqual(0, isolated.returncode, isolated.stderr)
        self.assertEqual([], self.owner.processes)

    def test_parameter_free_command_uses_herdr_xdg_configuration(self):
        base = self.fixture.root / "xdg"
        directory = base / "herdr/plugins/config" / PLUGIN_ID
        directory.mkdir(parents=True, mode=0o700)
        for name in ("config.json", "runtime-python"):
            private_file(directory / name, (self.config.parent / name).read_text())
        result = self.launch("recover", "--json", config=False, env=dict(os.environ, XDG_CONFIG_HOME=str(base)))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(directory / "config.json"), json.loads(result.stdout)["configuration"])
        result = self.launch(config=False, env=dict(os.environ, HERDR_PLUGIN_CONFIG_DIR=str(directory)))
        self.assertIn("恢复中心", result.stdout)
        self.assertNotIn('"schema"', result.stdout)
        self.assertEqual([], self.owner.processes)

    def test_one_click_hint_repair_restores_dashboard_and_preserves_pause_and_user_pane(self):
        hint = self.config.parent / "runtime-python"
        hint.unlink()
        intent = self.store.intent()
        config_bytes = self.config.read_bytes()
        report = recovery.diagnose(self.config)
        opened = recovery.perform(self.config, "hint", report)
        self.assertIn("pane", opened)
        runtime = wait_until(lambda: (item := self.store.read("runtime.json")) and item["state"] == "PAUSED" and item)
        self.assertIsNone(runtime["gateway"])
        self.assertEqual(intent, self.store.intent())
        self.assertEqual(config_bytes, self.config.read_bytes())
        self.assertEqual(str(self.fixture.config.python_bin) + "\n", hint.read_text())
        self.assertEqual(0o600, hint.stat().st_mode & 0o777)
        repeated = recovery.perform(self.config, "monitor", recovery.diagnose(self.config))
        self.assertEqual(runtime["pane"], repeated["pane"])
        self.assertEqual(1, len(self.owner.processes))
        self.assertEqual(RECOVERY_HINT, self.owner.panes[runtime["pane"]["pane_id"]]["label"])
        renamed = [request["params"] for request in self.owner.server.requests if request["method"] == "tab.rename"]
        self.assertTrue(renamed)
        self.assertTrue(all(item == {"tab_id": runtime["pane"]["tab_id"], "label": RECOVERY_TAB} for item in renamed))
        self.assertNotIn("label", self.owner.panes["pane-user"])

    def test_hint_repair_rejects_symlink_and_fifo_without_touching_them(self):
        hint = self.config.parent / "runtime-python"
        target = self.fixture.root / "do-not-change"
        private_file(target, "keep me")
        for kind in ("symlink", "fifo"):
            hint.unlink()
            if kind == "symlink":
                hint.symlink_to(target)
            else:
                os.mkfifo(hint, 0o600)
            with self.subTest(kind=kind), self.assertRaises(GatewayError) as raised:
                recovery.repair_hint(self.config)
            self.assertEqual("UNSAFE_PATH", raised.exception.code)
            report = json.loads(self.launch("recover", "--json").stdout)
            self.assertNotIn("hint", {item["id"] for item in report["actions"]})
            self.assertEqual("keep me", target.read_text())

    def test_recovery_revokes_dead_creation_ticket_while_preserving_pause_and_fuse(self):
        controller = capture(os.getpid())
        controller["start_fingerprint"] = dict(controller["start_fingerprint"], boot="previous-boot")
        fuse = {"schema": 1, "fused": True, "reason": "fixture", "failures": [], "restarts": [], "reset_revision": 0}
        with self.store.mutation():
            self.store.write("fuse.json", fuse)
            self.store.write("pending.json", {"schema": 1, "owner_key": self.fixture.config.key,
                                               "generation": "old-ticket", "intent_revision": 0,
                                               "phase": "pane_known", "controller": controller})
        (self.config.parent / "runtime-python").unlink()
        result = recovery.perform(self.config, "hint", recovery.diagnose(self.config))
        self.assertIn("pane", result)
        runtime = wait_until(lambda: (item := self.store.read("runtime.json")) and item["state"] == "PAUSED" and item)
        self.assertIsNone(runtime["gateway"])
        self.assertNotEqual("old-ticket", runtime["generation"])
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual(0, self.store.intent().get("reset_revision", 0))
        self.assertEqual(fuse, self.store.read("fuse.json"))
        self.assertEqual(1, len(self.owner.processes))

    def test_foreign_owner_and_stale_start_cannot_override_pause(self):
        report = recovery.diagnose(self.config)
        with self.store.mutation():
            self.store.set_intent("pause")
        intent = self.store.intent()
        result = recovery.perform(self.config, "start", report)
        self.assertEqual("STALE_REQUEST", result["code"])
        self.assertEqual(intent, self.store.intent())
        with patch.dict(os.environ, HERDR_SOCKET_PATH=str(self.fixture.root / "another.sock")):
            with self.assertRaises(GatewayError) as raised:
                recovery.perform(self.config, "monitor", report)
            self.assertEqual("NOT_OWNER", raised.exception.code)
        self.assertEqual([], self.owner.processes)

    def test_uncertain_and_orphaned_processes_are_explained_without_a_start_button(self):
        for state in ("ORPHAN", "UNKNOWN", "DRAINING"):
            with self.subTest(state=state), patch.object(recovery, "invoke", return_value={
                    "state": "DIAGNOSIS", "checks": [], "runtime": {"state": state, "intent_revision": 0}}):
                report = recovery.diagnose(self.config)
                self.assertEqual(state, report["state"])
                self.assertNotIn("start", {item["id"] for item in report["actions"]})
                self.assertTrue(report["reason"])
                self.assertTrue(report["next_step"])
        self.assertEqual([], self.owner.processes)
        self.assertIsNone(self.store.read("pending.json"))

    def test_dependency_fix_is_explicit_and_limited_to_the_configured_venv(self):
        missing = {"state": "ERROR", "code": "DEPENDENCY_MISSING"}
        with patch.object(recovery, "invoke", return_value=missing):
            report = recovery.diagnose(self.config)
        self.assertIn("dependencies", {item["id"] for item in report["actions"]})
        with patch.object(recovery.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
                patch.object(recovery, "invoke", return_value={"state": "PENDING"}) as invoke:
            recovery.perform(self.config, "dependencies", report)
        argv = run.call_args.args[0]
        self.assertEqual(str(self.fixture.config.python_bin), argv[0])
        self.assertIn("--require-virtualenv", argv)
        self.assertEqual(str(ROOT / "requirements.txt"), argv[-1])
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual("monitor", invoke.call_args.args[1])

    def test_native_recovery_popup_works_even_with_malformed_configuration(self):
        original = self.owner.server.handler
        def answer(request):
            if request["method"] == "plugin.pane.open":
                self.assertEqual({"plugin_id": PLUGIN_ID, "entrypoint": "recovery", "placement": "popup", "focus": True},
                                 request["params"])
                return {"id": request["id"], "result": {"type": "ok"}}
            return original(request)
        self.owner.server.handler = answer
        private_file(self.config, "broken JSON")
        result = self.launch("recover", "--open")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("ok", json.loads(result.stdout)["type"])
        self.assertEqual([], self.owner.processes)

    def test_attach_uses_native_herdr_and_saved_session_without_a_shell_command(self):
        report = {"actions": [{"id": "attach"}]}
        with patch.object(recovery, "diagnose", return_value=report), patch.object(recovery.os, "execve") as execute:
            recovery.attach(self.config)
        binary, argv, env = execute.call_args.args
        self.assertEqual(str(self.fixture.config.herdr_bin), binary)
        self.assertEqual([binary], argv)
        self.assertEqual(self.fixture.config.owner_session, env["HERDR_SESSION"])
        self.assertEqual(str(self.fixture.config.owner_socket), env["HERDR_SOCKET_PATH"])
        self.assertNotIn("HERDR_PANE_ID", env)
        self.assertNotIn("HGH_GENERATION", env)

    def failed_supervisor_ui(self, button):
        terminal = Terminal()
        self.addCleanup(terminal.close)
        process = subprocess.Popen([str(ROOT / "bin/hermes-on-herdr"), "--config", str(self.config), "supervise"],
                                   stdin=terminal.slave, stdout=terminal.slave, stderr=terminal.slave,
                                   env=dict(os.environ))
        try:
            wait_until(lambda: terminal.contains("恢复中心"))
            wait_until(lambda: terminal.contains(button))
            self.assertIsNone(process.poll())
            terminal.send(b"q")
            self.assertEqual(0, process.wait(timeout=8), terminal.read())
            self.assertTrue(terminal.restored())
            self.assertEqual([], self.owner.processes)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)

    def test_failed_supervisor_execs_recovery_in_the_same_pty_and_restores_terminal(self):
        (self.config.parent / "runtime-python").unlink()
        self.failed_supervisor_ui("修复 Python")
        self.assertFalse((self.config.parent / "runtime-python").exists())

    def test_real_dependency_import_failure_falls_back_to_system_python_ui(self):
        directory = self.fixture.root / "empty-venv"
        venv.EnvBuilder(with_pip=False, symlinks=False).create(directory)
        data = json.loads(self.config.read_text())
        data["python_bin"] = str(directory / "bin/python")
        private_file(self.config, json.dumps(data))
        private_file(self.config.parent / "runtime-python", data["python_bin"] + "\n")
        self.assertEqual("DEPENDENCY_MISSING", json.loads(self.launch("status").stdout)["code"])
        self.failed_supervisor_ui("修复插件依赖")
