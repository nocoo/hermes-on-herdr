from contextlib import redirect_stdout
from http.client import HTTPConnection
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tomllib
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

from hermes_gateway_herdr import __version__, cli
from hermes_gateway_herdr.config import profile_preflight
from hermes_gateway_herdr.identity import same_process, signal_verified
from hermes_gateway_herdr.state import Store
from fake_owner import FakeOwner
from helpers import Fixture, ROOT, json_lines, private_file, wait_until


class CliTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config
        self.owner = FakeOwner(self.fixture)
        self.addCleanup(self.owner.close)
        self.store = Store.initialize(self.config.state_dir, self.config.binding("fixture"))
        self.addCleanup(self.store.close)

    def invoke(self, *args, env=None):
        return subprocess.run([str(ROOT / "bin" / "hermes-gateway-herdr"), "--config",
                               str(self.config.config_dir / "config.json"), *args],
                              env=env or self.fixture.context(), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=6)

    def test_version_works_before_setup_for_both_launchers_and_python_entrypoint(self):
        missing = self.fixture.root / "not-configured"
        commands = [[str(ROOT / "bin" / name)] for name in ("hermes-on-herdr", "hermes-gateway-herdr")]
        commands.append([sys.executable, "-I", "-B", str(ROOT / "src" / "hermes_gateway_herdr" / "__main__.py")])
        for command in commands:
            for args in (("--version",), ("--config", str(missing / "config.json"), "--version")):
                with self.subTest(command=command, args=args):
                    result = subprocess.run([*command, *args], env={"HERDR_PLUGIN_CONFIG_DIR": str(missing)},
                                            capture_output=True, text=True, timeout=3)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual(f"hermes-on-herdr {__version__}\n", result.stdout)
        self.assertFalse(missing.exists())
        self.assertEqual([], self.owner.processes)

    def test_help_is_available_in_an_unconfigured_plugin_environment(self):
        missing = self.fixture.root / "not-configured"
        for name in ("hermes-on-herdr", "hermes-gateway-herdr"):
            result = subprocess.run([str(ROOT / "bin" / name), "--help"],
                                    env={"HERDR_PLUGIN_CONFIG_DIR": str(missing)}, capture_output=True, text=True, timeout=3)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Commands:", result.stdout)
        self.assertFalse(missing.exists())
        self.assertEqual([], self.owner.processes)

    def test_version_does_not_load_configuration(self):
        output = io.StringIO()
        with patch.object(cli.Config, "load", side_effect=AssertionError("Version read configuration")), \
                redirect_stdout(output), self.assertRaises(SystemExit) as result:
            cli.main(["--version"])
        self.assertEqual(0, result.exception.code)
        self.assertEqual(f"hermes-on-herdr {__version__}\n", output.getvalue())

    def inline(self, *args):
        output = io.StringIO()
        with patch.dict(os.environ, self.fixture.context(), clear=True), redirect_stdout(output):
            code = cli.main(["--config", str(self.config.config_dir / "config.json"), *args])
        return code, json.loads(output.getvalue())

    def test_launcher_ignores_path_pythonhome_and_pythonpath_injection(self):
        malicious = self.fixture.root / "injection"
        malicious.mkdir(mode=0o700)
        sentinel = self.fixture.root / "SHOULD_NOT_EXIST"
        (malicious / "sitecustomize.py").write_text(f"from pathlib import Path; Path({str(sentinel)!r}).touch()\n")
        (malicious / "python3").write_text("#!/bin/sh\nexit 88\n")
        (malicious / "python3").chmod(0o700)
        env = dict(self.fixture.context(), PATH=str(malicious), PYTHONPATH=str(malicious), PYTHONHOME=str(malicious))
        result = self.invoke("status", "--json", env=env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("PAUSED", json.loads(result.stdout)["state"])
        self.assertFalse(sentinel.exists())

    def test_rebranded_launcher_and_legacy_alias_share_the_existing_installation(self):
        outputs = []
        for name in ("hermes-on-herdr", "hermes-gateway-herdr"):
            binary = ROOT / "bin" / name
            help_result = subprocess.run([str(binary), "--help"], env=self.fixture.context(), capture_output=True, text=True, timeout=3)
            self.assertEqual(0, help_result.returncode, help_result.stderr)
            self.assertIn("Usage: hermes-on-herdr ", help_result.stdout)
            result = subprocess.run([str(binary), "--config", str(self.config.config_dir / "config.json"), "status", "--json"],
                                    env=self.fixture.context(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3)
            self.assertEqual(0, result.returncode, result.stderr)
            outputs.append(json.loads(result.stdout))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual("PAUSED", outputs[0]["state"])
        self.assertEqual([], self.owner.processes)

    def test_status_exit_code_is_separate_from_require_ready(self):
        ordinary = self.invoke("status", "--json")
        required = self.invoke("status", "--json", "--require-ready")
        self.assertEqual(0, ordinary.returncode)
        self.assertEqual(10, required.returncode)
        self.assertEqual("PAUSED", json.loads(required.stdout)["state"])

    def test_http_panel_observes_the_owned_gateway_and_exits_without_stopping_it(self):
        self.assertEqual(0, self.inline("start")[0])
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "READY")
        child = self.store.read("runtime.json")["gateway"]
        panel = subprocess.Popen([str(ROOT / "bin/hermes-on-herdr"), "--config", str(self.config.config_dir / "config.json"),
                                  "dashboard", "--http-port", "0"], env=self.fixture.context(), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import select
            self.assertTrue(select.select([panel.stdout], [], [], 3)[0])
            url = urlsplit(json.loads(panel.stdout.readline())["health_url"])

            def health():
                connection = HTTPConnection(url.hostname, url.port, timeout=1)
                try:
                    connection.request("GET", url.path)
                    response = connection.getresponse()
                    data = json.loads(response.read())
                    return data if response.status == 200 else None
                finally:
                    connection.close()

            data = wait_until(health)
            self.assertEqual(self.config.profile_id, data["profile"])
            self.assertEqual(child["pid"], data["gateway_pid"])
            self.assertEqual("READY", data["state"])
        finally:
            panel.terminate()
            _, errors = panel.communicate(timeout=3)
            self.assertEqual("", errors)
        self.assertTrue(same_process(child))
        self.assertEqual("running", self.store.intent()["desired"])

    def test_launcher_rejects_public_hint_symlink_and_shell_text(self):
        hint = self.config.config_dir / "runtime-python"
        hint.chmod(0o644)
        self.assertEqual("UNSAFE_PATH", json.loads(self.invoke("status").stdout)["code"])
        hint.unlink()
        target = self.fixture.root / "hint-target"
        private_file(target, str(self.config.python_bin) + "\n")
        hint.symlink_to(target)
        self.assertEqual(20, self.invoke("status").returncode)
        hint.unlink()
        sentinel = self.fixture.root / "SHOULD_NOT_EXIST"
        private_file(hint, f"$(touch {sentinel})\n")
        self.assertEqual(20, self.invoke("status").returncode)
        self.assertFalse(sentinel.exists())

    def test_fifo_configuration_and_state_are_rejected_without_waiting_for_a_writer(self):
        for path in (self.config.config_dir / "runtime-python", self.config.state_dir / "intent.json"):
            with self.subTest(path=path.name):
                original = path.read_text()
                path.unlink()
                os.mkfifo(path, 0o600)
                result = self.invoke("status")
                self.assertEqual(20, result.returncode)
                self.assertEqual("UNSAFE_PATH", json.loads(result.stdout)["code"])
                path.unlink()
                private_file(path, original)

    def test_unconfigured_hook_reports_setup_required_without_creating_profile(self):
        before = set(self.fixture.profile.iterdir())
        result = subprocess.run([str(ROOT / "bin" / "hermes-gateway-herdr"), "ensure", "--source", "startup"],
                                env={"HOME": str(self.fixture.root), "PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(20, result.returncode)
        self.assertEqual("SETUP_REQUIRED", json.loads(result.stdout)["code"])
        self.assertEqual(before, set(self.fixture.profile.iterdir()))
        self.assertFalse((self.fixture.root / ".hermes").exists())

    def test_cli_lifecycle_uses_real_fake_processes_and_waits_for_verified_stop(self):
        code, result = self.inline("resume")
        self.assertEqual(0, code)
        self.assertTrue(result["accepted"])
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "READY")
        first = self.store.read("runtime.json")["gateway"]
        self.assertEqual(0, self.inline("status", "--require-ready")[0])
        self.assertEqual(0, self.inline("restart")[0])
        wait_until(lambda: not same_process(first))
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "READY")
        code, stopped = self.inline("stop", "--wait", "2")
        self.assertEqual(0, code)
        self.assertTrue(stopped["completed"])
        self.assertEqual("PAUSED", stopped["runtime"]["state"])
        self.assertTrue(self.store.lifetime_held())
        self.assertEqual(1, len(self.owner.processes))

    def test_monitor_opens_and_focuses_the_same_dashboard_even_when_paused(self):
        self.assertEqual(0, self.inline("monitor")[0])
        paused = wait_until(lambda: (runtime := self.store.read("runtime.json")) and runtime["state"] == "PAUSED" and runtime)
        self.assertIsNone(paused["gateway"])
        self.assertEqual(0, self.inline("monitor")[0])
        focused = [r["params"]["pane_id"] for r in self.owner.server.requests if r["method"] == "pane.focus"]
        self.assertEqual([paused["pane"]["pane_id"]] * 2, focused)
        self.assertEqual(1, len(self.owner.processes))
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))

    def test_disabled_start_arms_startup_without_launching_before_enable(self):
        self.owner.enabled = False
        code, result = self.inline("start")
        self.assertEqual(0, code)
        self.assertTrue(result["accepted"])
        self.assertEqual("DISABLED", result["state"])
        self.assertEqual("running", self.store.intent()["desired"])
        hook = self.invoke("ensure", "--source", "startup")
        self.assertEqual(0, hook.returncode)
        self.assertEqual("DISABLED", json.loads(hook.stdout)["state"])
        self.assertIsNone(self.store.read("runtime.json"))
        self.assertIsNone(self.store.read("pending.json"))
        self.assertEqual([], self.owner.processes)
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))

        self.owner.enabled = True
        self.assertEqual(0, self.inline("ensure", "--source", "startup")[0])
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "READY")
        child = self.store.read("runtime.json")["gateway"]
        code, repeated = self.inline("ensure", "--source", "startup")
        self.assertEqual(0, code)
        self.assertEqual("READY", repeated["state"])
        self.assertTrue(same_process(child))
        self.assertEqual(child, self.store.read("runtime.json")["gateway"])
        self.assertEqual(1, len(self.owner.processes))
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))

    def test_hook_busy_and_nonowner_return_quick_normal_results(self):
        with self.store.mutation():
            self.store.set_intent("resume")
        with self.store.lease():
            result = self.invoke("ensure", "--source", "startup")
        self.assertEqual(0, result.returncode)
        self.assertEqual("UNKNOWN", json.loads(result.stdout)["state"])
        env = dict(self.fixture.context(), HERDR_SOCKET_PATH=str(self.fixture.root / "another.sock"))
        result = self.invoke("ensure", "--source", "startup", env=env)
        self.assertEqual(0, result.returncode)
        self.assertEqual("NOT_OWNER", json.loads(result.stdout)["state"])
        self.assertEqual([], self.owner.processes)

    def test_explicit_request_id_requires_revision_and_cannot_replay_old_resume(self):
        code, result = self.inline("resume", "--request-id", "first")
        self.assertEqual(20, code)
        self.assertEqual("INVALID_ARGUMENT", result["code"])
        self.assertEqual("paused", self.store.intent()["desired"])
        code, _ = self.inline("resume", "--request-id", "first", "--expected-revision", "0")
        self.assertEqual(0, code)
        wait_until(lambda: self.store.read("runtime.json"))
        self.inline("pause", "--wait", "2")
        code, replay = self.inline("resume", "--request-id", "first", "--expected-revision", "0")
        self.assertEqual(0, code)
        self.assertEqual("paused", replay["desired"])
        self.assertEqual(1, len(self.owner.processes))

    def test_doctor_is_read_only_and_never_executes_configured_upstream_binaries(self):
        before = {str(path): path.read_bytes() for path in self.config.profile_home.rglob("*") if path.is_file()}
        result = self.invoke("doctor", "--json")
        self.assertEqual(20, result.returncode)  # Fake root deliberately is not the pinned Hermes checkout.
        data = json.loads(result.stdout)
        self.assertEqual("UNSUPPORTED_VERSION", data["checks"][1]["code"])
        self.assertEqual("NOT_RUN", data["real_validation"])
        self.assertEqual({"version_range": ">=0.9.0,<0.10.0", "protocols": [22], "stable_only": True},
                         data["baseline"]["herdr"])
        self.assertEqual({"name": "owner", "ok": True, "code": "OK", "herdr": {"version": "0.9.1", "protocol": 22}},
                         data["checks"][2])
        after = {str(path): path.read_bytes() for path in self.config.profile_home.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual([], self.owner.processes)

    def test_doctor_explains_unsupported_herdr_protocol_without_echoing_peer_text(self):
        self.owner.pong.update(protocol=23, message="fixture-private-sentinel")
        result = self.invoke("doctor", "--json")
        self.assertEqual(20, result.returncode)
        owner = json.loads(result.stdout)["checks"][2]
        self.assertFalse(owner["ok"])
        self.assertEqual("UNSUPPORTED_VERSION", owner["code"])
        self.assertIn("protocol", owner["message"])
        self.assertIn("22", owner["message"])
        self.assertNotIn("fixture-private-sentinel", result.stdout)
        self.assertEqual([], self.owner.processes)

    def test_binding_dry_run_then_apply_only_writes_control_state(self):
        fresh = Fixture()
        self.addCleanup(fresh.close)
        before = {path.name: path.read_bytes() for path in fresh.profile.iterdir()}
        with patch.object(cli, "preflight", profile_preflight):
            plan = cli.binding_plan(fresh.config)
            self.assertEqual("PLAN", plan["state"])
            self.assertFalse(fresh.config.state_dir.exists())
            bound = cli.binding_plan(fresh.config, apply=True)
            self.assertEqual("paused", bound["desired"])
            with Store(fresh.config.state_dir) as store:
                with store.mutation():
                    store.set_intent("resume")
                    store.set_intent("pause", reason="operator_latch")
                intent = store.intent()
            cli.binding_plan(fresh.config, apply=True)
            with Store(fresh.config.state_dir) as store:
                self.assertEqual(intent, store.intent())
        self.assertEqual(before, {name: (fresh.profile / name).read_bytes() for name in before})
        self.assertFalse(plan["creates_profile"])

    def test_logs_reads_only_bounded_structured_events(self):
        directory = self.config.state_dir / "logs"
        directory.mkdir(mode=0o700)
        private_file(directory / "gateway-output.log", "FAKE_RAW_SECRET")
        private_file(directory / "events.jsonl", '\n'.join(json.dumps({"event": "child_started", "pid": n, "unlisted": "FAKE_SECRET"}) for n in range(300)) + '\n')
        result = self.invoke("logs", "--lines", "5")
        self.assertEqual(0, result.returncode)
        self.assertEqual(5, len(json.loads(result.stdout)["events"]))
        self.assertNotIn("FAKE_SECRET", result.stdout)
        self.assertNotIn("FAKE_RAW_SECRET", result.stdout)

    def test_fifo_event_log_is_rejected_without_waiting_for_a_writer(self):
        directory = self.config.state_dir / "logs"
        directory.mkdir(mode=0o700)
        path = directory / "events.jsonl"
        os.mkfifo(path, 0o600)
        inode = path.stat().st_ino
        result = self.invoke("logs")
        self.assertEqual(20, result.returncode, result.stderr)
        self.assertEqual("UNSAFE_PATH", json.loads(result.stdout)["code"])
        self.assertEqual(inode, path.stat().st_ino)
        self.assertEqual([], self.owner.processes)

    def test_fifo_gateway_lock_returns_unknown_and_does_not_block_pause(self):
        path = self.config.profile_home / "gateway.lock"
        os.mkfifo(path, 0o600)
        inode = path.stat().st_ino
        result = self.invoke("status")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("UNKNOWN", json.loads(result.stdout)["state"])
        pause = self.invoke("pause")
        self.assertEqual(0, pause.returncode, pause.stderr)
        self.assertTrue(json.loads(pause.stdout)["accepted"])
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual(inode, path.stat().st_ino)
        self.assertEqual([], self.owner.processes)

    def test_stop_wait_reports_orphan_as_incomplete(self):
        self.inline("resume")
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        signal_verified(self.owner.records[0], signal.SIGKILL)
        self.owner.processes[0].wait(timeout=3)
        code, result = self.inline("stop", "--wait", "0.2")
        self.assertEqual(30, code)
        self.assertTrue(result["accepted"])
        self.assertFalse(result["completed"])
        self.assertEqual("ORPHAN", result["runtime"]["state"])

    def test_manifest_registers_only_implemented_commands_and_one_startup(self):
        manifest = tomllib.loads((ROOT / "herdr-plugin.toml").read_text())
        self.assertEqual(__version__, manifest["version"])
        self.assertEqual("hermes on herdr", manifest["name"])
        self.assertEqual("nocoo.hermes-gateway", manifest["id"])
        self.assertEqual(1, len(manifest["startup"]))
        self.assertEqual(["gateway", "recovery"], [pane["id"] for pane in manifest["panes"]])
        self.assertEqual({"workspace.focused", "pane.exited", "pane.closed"}, {event["on"] for event in manifest["events"]})
        for group in ("startup", "panes", "actions", "events"):
            for item in manifest[group]:
                command = item["command"]
                self.assertTrue(os.access(ROOT / command[0], os.X_OK))
                parsed = cli.parser().parse_args(["--config", str(self.config.config_dir / "config.json"), *command[1:]])
                self.assertIsNotNone(parsed.command)
