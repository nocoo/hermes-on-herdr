from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tomllib
import unittest
from unittest.mock import patch

from hermes_gateway_herdr import cli
from hermes_gateway_herdr.config import profile_preflight
from hermes_gateway_herdr.controller import Controller
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

    def inline(self, *args):
        output = io.StringIO()
        # The replacement exists only in the test process; production has no bypass flag.
        with patch.object(cli, "Controller", side_effect=lambda config, **kwargs: Controller(config, check=profile_preflight, **kwargs)), \
                patch.dict(os.environ, self.fixture.context(), clear=True), redirect_stdout(output):
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

    def test_status_exit_code_is_separate_from_require_ready(self):
        ordinary = self.invoke("status", "--json")
        required = self.invoke("status", "--json", "--require-ready")
        self.assertEqual(0, ordinary.returncode)
        self.assertEqual(10, required.returncode)
        self.assertEqual("PAUSED", json.loads(required.stdout)["state"])

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
        self.assertFalse(self.store.lifetime_held())
        self.assertEqual(1, len(self.owner.processes))

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
        after = {str(path): path.read_bytes() for path in self.config.profile_home.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
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
        self.assertEqual(1, len(manifest["startup"]))
        self.assertEqual(["gateway"], [pane["id"] for pane in manifest["panes"]])
        self.assertEqual({"workspace.focused", "pane.exited", "pane.closed"}, {event["on"] for event in manifest["events"]})
        for group in ("startup", "panes", "actions", "events"):
            for item in manifest[group]:
                command = item["command"]
                self.assertTrue(os.access(ROOT / command[0], os.X_OK))
                parsed = cli.parser().parse_args(["--config", str(self.config.config_dir / "config.json"), *command[1:]])
                self.assertIsNotNone(parsed.command)
