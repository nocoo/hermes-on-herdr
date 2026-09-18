import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import termios
import time
import unittest

import psutil

from hermes_gateway_herdr.config import PLUGIN_ID
from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture, same_process, signal_verified
from hermes_gateway_herdr.rpc import control_query, exchange, supervisor_socket
from hermes_gateway_herdr.state import Store
from helpers import Fixture, SocketServer, Terminal, json_lines, private_file, wait_until


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config
        self.process = self.record = None
        self.enabled = True
        self.pong = {"type": "pong", "version": "0.9.1", "protocol": 22}
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
            result = dict(self.pong)
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
            if self.process.stdout is not None:
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

    def start(self, plan=None, *, paused=False, terminal=None):
        private_file(self.fixture.root / "plan.json", json.dumps(plan or {}))
        with self.store.mutation():
            intent = self.store.set_intent("resume")
            self.store.write("pending.json", {"schema": 1, "owner_key": self.config.key, "generation": "generation",
                                             "intent_revision": intent["revision"], "phase": "pane_requested"})
            if paused:
                self.store.set_intent("pause")
        self.process = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).with_name("process_fixture.py")),
                                         "supervisor", str(self.config.config_dir / "config.json")],
                                        env=self.fixture.context(), stdin=terminal.slave if terminal else subprocess.DEVNULL,
                                        stdout=terminal.slave if terminal else subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
        self.record = capture(self.process.pid)
        return self.process

    def status(self):
        return control_query(supervisor_socket(self.config), "status", timeout=0.5)

    def wait_child(self):
        return wait_until(lambda: self.store.read("runtime.json") and self.store.read("runtime.json").get("gateway"))

    def wait_idle(self, state="PAUSED"):
        runtime = wait_until(lambda: (r := self.store.read("runtime.json")) and r["state"] == state and not r["gateway"] and r)
        self.assertIsNone(self.process.poll())
        self.assertTrue(self.store.lifetime_held())
        return runtime

    def shutdown(self):
        signal_verified(self.record, signal.SIGTERM)
        self.assertEqual(0, self.process.wait(timeout=3))
        self.assertFalse(self.store.lifetime_held())

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

    def test_patch_upgrade_keeps_gateway_but_protocol_change_stops_it(self):
        self.pong["version"] = "0.9.0"
        self.start()
        child = self.wait_child()
        wait_until(lambda: self.status()["state"] == "READY")
        self.pong["version"] = "0.9.1"
        before = sum(r["method"] == "pane.process_info" for r in self.server.requests)
        wait_until(lambda: sum(r["method"] == "pane.process_info" for r in self.server.requests) >= before + 2)
        self.assertEqual("READY", self.status()["state"])
        self.assertTrue(same_process(child))
        self.assertIsNone(self.process.poll())
        self.pong["protocol"] = 23
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertFalse(same_process(child))
        self.assertFalse(self.store.lifetime_held())
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))

    def display_failure(self, stage):
        self.start({"dashboard_failure": stage})
        child = self.wait_child()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        self.assertTrue(same_process(child))
        self.action("pause", send=False)
        self.wait_idle()
        self.assertFalse(same_process(child))
        self.shutdown()
        events = json_lines(self.config.state_dir / "logs" / "events.jsonl")
        self.assertTrue(any(e["event"] == "dashboard_unavailable" and e["stage"] == stage for e in events))
        self.assertFalse(any(e["event"] == "supervisor_error" for e in events))

    def test_display_start_failure_does_not_prevent_gateway_start_or_pause(self):
        self.display_failure("start")

    def test_display_poll_failure_does_not_trigger_gateway_emergency_cleanup(self):
        self.display_failure("poll")

    def test_display_cleanup_failure_does_not_leak_gateway_or_lifetime_lock(self):
        self.display_failure("close")

    def test_embedded_dashboard_stays_open_after_q_and_pause_and_enter_restarts_in_place(self):
        terminal = Terminal()
        self.addCleanup(terminal.close)
        self.start(terminal=terminal)
        child = self.wait_child()
        wait_until(lambda: terminal.contains("HERDR MANAGED"))
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "READY")
        wait_until(lambda: terminal.contains("SYSTEM"))
        self.assertFalse(terminal.contains("Open the monitoring dashboard?"))
        revision = self.store.intent()["revision"]
        terminal.send(b"q\r")
        time.sleep(0.2)
        self.assertTrue(same_process(child))
        self.assertEqual("READY", self.status()["state"])
        self.assertEqual(revision, self.store.intent()["revision"])
        terminal.send(b"\x03")
        paused = self.wait_idle()
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual("supervisor_interrupt", self.store.intent()["reason"])
        self.assertFalse(same_process(child))
        self.assertFalse(terminal.restored())
        wait_until(lambda: terminal.contains("PAUSED"))
        terminal.send(b"\r")
        replacement = self.wait_child()
        self.assertNotEqual(child["pid"], replacement["pid"])
        self.assertEqual(paused["pane"], self.store.read("runtime.json")["pane"])
        self.assertEqual(paused["supervisor"], self.store.read("runtime.json")["supervisor"])
        wait_until(lambda: self.status()["state"] == "READY")
        self.assertEqual("dashboard_start", self.store.intent()["reason"])
        self.assert_single()
        self.shutdown()
        self.assertTrue(terminal.restored())

    def test_renderer_crash_recovers_in_the_same_pane_without_restarting_gateway(self):
        terminal = Terminal()
        self.addCleanup(terminal.close)
        self.start({"limits": {"display_retry": 0.2}}, terminal=terminal)
        child = self.wait_child()
        wait_until(lambda: terminal.contains("HERDR MANAGED"))
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "READY")
        # Inspect only children of this fixture's supervisor, never the host process table.
        renderers = [p for p in psutil.Process(self.process.pid).children() if p.pid != child["pid"]]
        self.assertEqual(1, len(renderers))
        renderer = capture(renderers[0].pid)
        self.assertNotIn(renderer["pid"], [p["pid"] for p in self.store.read("runtime.json")["descendants"]])
        signal_verified(renderer, signal.SIGKILL)
        wait_until(lambda: terminal.contains("Dashboard 未就绪"))
        with terminal.lock:
            terminal.output = b""
        wait_until(lambda: terminal.contains("HERDR MANAGED"))
        self.assertTrue(same_process(child))
        self.assertFalse(same_process(renderer))
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertEqual("READY", self.status()["state"])
        self.action("pause", send=False)
        self.wait_idle()
        self.assertFalse(same_process(child))
        self.shutdown()
        self.assertTrue(terminal.restored())

    def test_blocked_renderer_output_cannot_delay_pause_or_terminal_cleanup(self):
        terminal = Terminal(300, 100, drain=False)
        self.addCleanup(terminal.close)
        self.start(terminal=terminal)
        child = self.wait_child()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        wait_until(lambda: select.select([terminal.master], [], [], 0)[0])
        os.read(terminal.master, 4096)  # Let terminal setup complete, then block the large first frame.
        wait_until(lambda: not termios.tcgetattr(terminal.slave)[3] & termios.ICANON)
        # The PTY master is deliberately not drained during the stop.
        before = time.monotonic()
        self.action("pause", send=False)
        self.wait_idle()
        self.assertLess(time.monotonic() - before, 2)
        self.assertFalse(same_process(child))
        self.shutdown()
        self.assertTrue(terminal.restored())

    def test_75_restarts_child_and_clean_zero_latches_pause(self):
        self.start({"exits": [75, 75, 0]})
        self.wait_idle()
        self.assertEqual(3, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual("observed_clean_exit", self.store.intent()["reason"])
        self.assertEqual(self.record["pid"], self.store.read("runtime.json")["supervisor"]["pid"])
        self.assert_single()

    def test_fatal_exit_keeps_dashboard_available_and_enter_resets_fuse(self):
        terminal = Terminal()
        self.addCleanup(terminal.close)
        self.start({"exits": [78, None]}, terminal=terminal)
        fused = self.wait_idle("FUSED")
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertTrue(self.store.read("fuse.json")["fused"])
        self.assertEqual("EXIT_78", self.store.read("fuse.json")["reason"])
        wait_until(lambda: terminal.contains("Start [Enter]") and terminal.contains("FUSED"))
        terminal.send(b"\r")
        self.wait_child()
        wait_until(lambda: self.status()["state"] == "READY")
        self.assertFalse(self.status()["fused"])
        self.assertEqual(fused["supervisor"], self.store.read("runtime.json")["supervisor"])
        self.assertEqual(fused["pane"], self.store.read("runtime.json")["pane"])
        self.assertEqual(2, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assert_single()

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
        self.wait_idle()

    def test_pause_without_socket_delivery_stops_gateway_and_detached_task(self):
        self.start({"task": True, "ignore_term": True, "task_ignore_term": True})
        child = self.wait_child()
        task = wait_until(lambda: json.loads((self.fixture.root / "task.json").read_text())
                          if (self.fixture.root / "task.json").exists() else None)
        self.assertNotEqual(child["sid"], task["sid"])
        self.action("pause", send=False)
        self.wait_idle()
        self.assertFalse(same_process(child))
        self.assertFalse(same_process(task))
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
        self.wait_idle()
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
        self.action("pause", send=False)
        self.wait_idle()
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
        self.wait_idle()
        self.assertEqual("supervisor_interrupt", self.store.intent()["reason"])

    def test_malformed_control_fields_cannot_terminate_the_owned_gateway(self):
        self.start()
        child = self.wait_child()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        intent = self.store.intent()
        cases = [({"verb": value}, "UNSUPPORTED_VERB") for value in ([], {}, None, True, 42)]
        cases += [({"protocol": True}, "PROTOCOL_ERROR"),
                  ({"unexpected": "fixture-private-sentinel"}, "PROTOCOL_ERROR"),
                  ({"verb": "stop", "owner_key": []}, "STALE_REQUEST")]
        for fields, code in cases:
            with self.subTest(fields=fields):
                request = {"id": "malformed", "protocol": 1, "verb": "status", **fields}
                response = exchange(supervisor_socket(self.config), request)
                self.assertFalse(response["ok"])
                self.assertEqual(code, response["code"])
                self.assertNotIn("fixture-private-sentinel", json.dumps(response))
                self.assertIsNone(self.process.poll())
                self.assertTrue(same_process(child))
        self.assertEqual(intent, self.store.intent())
        self.assertEqual(child["pid"], self.status()["gateway"]["pid"])
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.action("pause", send=False)
        self.wait_idle()
        self.assertFalse(same_process(child))

    def test_pause_works_with_corrupted_profile_yaml(self):
        self.start()
        child = self.wait_child()
        private_file(self.config.profile_home / "config.yaml", "model: [broken")
        self.action("pause", send=False)
        self.wait_idle()
        self.assertFalse(same_process(child))

    def test_pause_cancels_pending_configuration_retry_and_monitor_stays_usable(self):
        terminal = Terminal()
        self.addCleanup(terminal.close)
        private_file(self.config.profile_home / "config.yaml", "model: [broken")
        self.start(terminal=terminal)
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "BLOCKED")
        wait_until(lambda: terminal.contains("Check Profile configuration"))
        self.assertIsNone(self.process.poll())
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))
        self.action("pause", send=False)
        self.wait_idle()
        self.fixture.write_profile()
        time.sleep(0.3)
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))
        self.assertFalse(terminal.restored())
        self.shutdown()
        self.assertTrue(terminal.restored())

    def test_start_rechecks_configuration_after_a_pre_pause_inspection_finishes_late(self):
        self.start({"hold_first_check": True})
        wait_until(lambda: (self.fixture.root / "check-complete").exists())
        self.action("pause", send=False)
        self.wait_idle()
        private_file(self.config.profile_home / "config.yaml", "model: [broken")
        self.action("resume", send=False)
        private_file(self.fixture.root / "check-release", "1")
        wait_until(lambda: self.status()["state"] == "BLOCKED")
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))
        self.fixture.write_profile()
        self.wait_child()
        wait_until(lambda: self.status()["state"] == "READY")
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))

    def test_spawn_failure_keeps_dashboard_and_enter_retries_before_the_automatic_deadline(self):
        terminal = Terminal()
        self.addCleanup(terminal.close)
        self.start({"fail_first_spawn": True, "limits": {"recheck": 30}}, terminal=terminal)
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("state") == "BLOCKED")
        blocked = self.status()
        self.assertEqual("SPAWN_FAILED", blocked["code"])
        self.assertFalse(blocked["fused"])
        wait_until(lambda: terminal.contains("Start [Enter]"))
        terminal.send(b"\r")
        self.wait_child()
        wait_until(lambda: self.status()["state"] == "READY")
        self.assertEqual(blocked["supervisor"], self.status()["supervisor"])
        self.assertEqual(blocked["pane"], self.status()["pane"])
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))

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
        self.wait_idle()

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
        # Keep this crash-budget check independent of the fixture's very short
        # owner-loss deadlines; dedicated tests exercise owner expiry separately.
        self.start({"exits": [1], "exit_after": 0.02, "limits": {"rpc": 1, "owner_grace": 3}})
        self.wait_idle("FUSED")
        self.assertEqual(6, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertEqual("CRASH_LOOP", self.store.read("fuse.json")["reason"], self.store.read("runtime.json"))
        self.assert_single()

    def test_owner_loss_beyond_grace_stops_without_pausing(self):
        self.start()
        child = self.wait_child()
        self.owner_offline = True
        self.assertEqual(0, self.process.wait(timeout=5))
        self.assertFalse(same_process(child))
        self.assertEqual("running", self.store.intent()["desired"])
