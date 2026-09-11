import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import unittest

from hermes_gateway_herdr.config import PLUGIN_ID
from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture, same_process, signal_verified
from hermes_gateway_herdr.rpc import control_query, exchange, supervisor_socket
from hermes_gateway_herdr.state import Store
from helpers import Fixture, SocketServer, json_lines, private_file, wait_until


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config
        self.process = self.record = None
        self.enabled = True
        self.owner_offline = False
        self.terminal_id = "terminal-first"
        self.moved = False
        self.server = SocketServer(self.config.owner_socket, self.answer)
        self.addCleanup(self.server.close)
        self.store = Store.initialize(self.config.state_dir, self.config.binding("fixture"))
        self.addCleanup(self.store.close)
        self.addCleanup(self.cleanup_processes)

    def answer(self, request):
        if self.owner_offline:
            return None
        method = request["method"]
        if method == "ping":
            result = {"version": "0.9.0"}
        elif method == "plugin.list":
            result = {"plugins": [{"plugin_id": PLUGIN_ID, "plugin_root": str(self.config.plugin_root), "enabled": self.enabled}]}
        elif method == "pane.get":
            result = {"pane": {"workspace_id": "w-moved" if self.moved else "w-fixture", "tab_id": "tab-fixture",
                               "pane_id": "pane-fixture", "terminal_id": self.terminal_id}}
        elif method == "pane.process_info":
            result = {"process_info": {"pane_id": "pane-fixture", "shell_pid": self.process.pid}}
        else:
            raise AssertionError(method)
        return {"id": request["id"], "result": result}

    def cleanup_processes(self):
        errors = ""
        if self.process is not None:
            if self.process.poll() is None and self.record and same_process(self.record):
                signal_verified(self.record, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                signal_verified(self.record, signal.SIGKILL)
                self.process.wait(timeout=3)
            self.process.stdout.close()
            errors = self.process.stderr.read().decode()
            self.process.stderr.close()
        paths = (self.fixture.root / "children.jsonl",)
        records = [record for path in paths for record in json_lines(path)]
        task = self.fixture.root / "task.json"
        if task.exists():
            records.append(json.loads(task.read_text()))
        for record in records:
            if same_process(record):
                signal_verified(record, signal.SIGKILL)
                wait_until(lambda: not same_process(record))
        if errors:
            raise AssertionError(errors)

    def start(self, plan=None, *, paused=False):
        private_file(self.fixture.root / "plan.json", json.dumps(plan or {}))
        with self.store.mutation():
            intent = self.store.set_intent("resume")
            self.store.write("pending.json", {"schema": 1, "owner_key": self.config.key, "generation": "generation",
                                             "intent_revision": intent["revision"], "phase": "pane_requested"})
            if paused:
                self.store.set_intent("pause")
        self.process = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).with_name("process_fixture.py")),
                                         "supervisor", str(self.config.config_dir / "config.json")],
                                        env=self.fixture.context(), stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.record = capture(self.process.pid)
        return self.process

    def status(self):
        return control_query(supervisor_socket(self.config), "status", timeout=0.5)

    def wait_child(self):
        return wait_until(lambda: self.store.read("runtime.json") and self.store.read("runtime.json").get("gateway"))

    def action(self, action, *, send=True):
        with self.store.mutation():
            intent = self.store.set_intent(action)
        if send:
            verb = "stop" if action in {"stop", "pause"} else "restart"
            return control_query(supervisor_socket(self.config), verb, request_id=intent["request_id"],
                                 owner_key=self.config.key, generation="generation", intent_revision=intent["revision"])
        return intent

    def assert_single(self):
        self.assertTrue(all(item["active_previous"] == 0 for item in json_lines(self.fixture.root / "launches.jsonl")))

    def test_75_restarts_child_and_clean_zero_latches_pause(self):
        self.start({"exits": [75, 75, 0]})
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertEqual(3, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual("observed_clean_exit", self.store.intent()["reason"])
        self.assertEqual(self.record["pid"], self.store.read("runtime.json")["supervisor"]["pid"])
        self.assertFalse(self.store.lifetime_held())
        self.assert_single()

    def test_fatal_exit_fuses_without_retry(self):
        self.start({"exits": [78]})
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertTrue(self.store.read("fuse.json")["fused"])
        self.assertEqual("EXIT_78", self.store.read("fuse.json")["reason"])

    def test_restart_ack_replay_sends_one_usr1_and_keeps_supervisor(self):
        self.start()
        first = self.wait_child()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        intent = self.action("restart", send=False)
        for _ in range(2):
            ack = control_query(supervisor_socket(self.config), "restart", request_id=intent["request_id"],
                                owner_key=self.config.key, generation="generation", intent_revision=intent["revision"])
            self.assertTrue(ack["accepted"])
        wait_until(lambda: len(json_lines(self.fixture.root / "children.jsonl")) == 2)
        signals = json_lines(self.fixture.root / "signals.jsonl")
        self.assertEqual(1, sum(item["signal"] == signal.SIGUSR1 and item["pid"] == first["pid"] for item in signals))
        self.assertIsNone(self.process.poll())
        self.assert_single()
        self.action("pause", send=False)
        self.assertEqual(0, self.process.wait(timeout=5))

    def test_pause_without_socket_delivery_stops_gateway_and_detached_task(self):
        self.start({"task": True, "ignore_term": True, "task_ignore_term": True})
        child = self.wait_child()
        task = wait_until(lambda: json.loads((self.fixture.root / "task.json").read_text())
                          if (self.fixture.root / "task.json").exists() else None)
        self.assertNotEqual(child["sid"], task["sid"])
        self.action("pause", send=False)
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertFalse(same_process(child))
        self.assertFalse(same_process(task))
        self.assertFalse(self.store.lifetime_held())
        self.assertEqual("paused", self.store.intent()["desired"])

    def test_slow_peers_and_output_flood_do_not_block_pause(self):
        self.start({"stall_probe": 1, "flood": True})
        child = self.wait_child()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        slow = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        slow.connect(str(supervisor_socket(self.config)))
        self.addCleanup(slow.close)
        slow.sendall(b'{"protocol":1')
        before = time.monotonic()
        # The child may exit before a socket ACK; the durable intent remains the acceptance record.
        self.action("pause", send=False)
        self.assertEqual(0, self.process.wait(timeout=3))
        self.assertLess(time.monotonic() - before, 2)
        self.assertFalse(same_process(child))
        events = self.config.state_dir / "logs" / "events.jsonl"
        self.assertNotIn("FAKE_RAW_SECRET", events.read_text())

    def test_late_pane_after_pause_cannot_spawn(self):
        self.start(paused=True)
        self.assertEqual(20, self.process.wait(timeout=5))
        self.assertFalse((self.fixture.root / "launches.jsonl").exists())
        self.assertEqual("paused", self.store.intent()["desired"])

    def test_handoff_terminal_change_keeps_child_and_disable_pauses(self):
        self.start()
        child = self.wait_child()
        self.terminal_id = "terminal-after-handoff"
        wait_until(lambda: self.store.read("runtime.json")["pane"]["terminal_id"] == self.terminal_id)
        self.assertTrue(same_process(child))
        self.enabled = False
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual("plugin_disabled", self.store.intent()["reason"])

    def test_owner_grace_and_term_preserve_running_intent(self):
        self.start()
        child = self.wait_child()
        self.owner_offline = True
        wait_until(lambda: self.store.read("runtime.json")["state"] == "UNKNOWN")
        self.owner_offline = False
        wait_until(lambda: self.store.read("runtime.json")["state"] != "UNKNOWN")
        self.assertTrue(same_process(child))
        signal_verified(self.record, signal.SIGTERM)
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertEqual("running", self.store.intent()["desired"])
        self.assertFalse(same_process(child))

    def test_control_rejects_unknown_verb_and_stale_generation(self):
        self.start()
        self.wait_child()
        for payload in ({"verb": "exec", "argv": ["touch", "bad"]},
                        {"verb": "stop", "owner_key": self.config.key, "generation": "old", "intent_revision": 1}):
            response = exchange(supervisor_socket(self.config), {"protocol": 1, "id": "request", **payload})
            self.assertFalse(response["ok"])
        self.assertEqual("running", self.store.intent()["desired"])
        signal_verified(self.record, signal.SIGINT)
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertEqual("supervisor_interrupt", self.store.intent()["reason"])

    def test_pause_works_with_corrupted_profile_yaml(self):
        self.start()
        child = self.wait_child()
        private_file(self.config.profile_home / "config.yaml", "model: [broken")
        self.action("pause", send=False)
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertFalse(same_process(child))

    def test_resume_during_stop_waits_for_old_child_then_starts_once(self):
        self.start({"ignore_term": True})
        child = self.wait_child()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        self.action("pause", send=False)
        wait_until(lambda: self.store.read("runtime.json")["state"] == "DRAINING")
        self.action("resume", send=False)
        wait_until(lambda: len(json_lines(self.fixture.root / "children.jsonl")) == 2)
        self.assertFalse(same_process(child))
        self.assert_single()
        self.assertEqual("running", self.store.intent()["desired"])
        self.action("pause", send=False)
        self.assertEqual(0, self.process.wait(timeout=5))

    def test_fresh_socket_observations_reach_ready_and_lifetime_excludes_second_supervisor(self):
        self.start()
        child = self.wait_child()
        wait_until(lambda: self.store.read("runtime.json")["state"] == "READY")
        self.assertEqual(2, self.status()["last_probe"]["level"])
        self.assertEqual(0o600, (self.config.profile_home / "gateway.lock").stat().st_mode & 0o777)
        duplicate = subprocess.run(self.process.args, env=self.fixture.context(), stdin=subprocess.DEVNULL,
                                   capture_output=True, timeout=3, start_new_session=True)
        self.assertEqual(10, duplicate.returncode)
        self.assertEqual(b"", duplicate.stderr)
        self.assertTrue(same_process(child))
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))

    def test_repeated_failure_fuses_without_overlapping_children(self):
        self.start({"exits": [1], "exit_after": 0.02})
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertEqual(6, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertEqual("CRASH_LOOP", self.store.read("fuse.json")["reason"])
        self.assert_single()

    def test_owner_loss_beyond_grace_stops_without_pausing(self):
        self.start()
        child = self.wait_child()
        self.owner_offline = True
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertFalse(same_process(child))
        self.assertEqual("running", self.store.intent()["desired"])
