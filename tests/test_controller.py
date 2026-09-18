from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from hermes_gateway_herdr.controller import Controller
from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture, same_process, signal_verified
from hermes_gateway_herdr.rpc import supervisor_socket
from hermes_gateway_herdr.state import Store
from fake_owner import FakeOwner
from helpers import Fixture, SocketServer, json_lines, private_file, wait_until


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config
        self.owner = FakeOwner(self.fixture)
        self.addCleanup(self.owner.close)
        self.store = Store.initialize(self.config.state_dir, self.config.binding("fixture"))
        self.addCleanup(self.store.close)
        with self.store.mutation():
            self.store.set_intent("resume")

    def controller(self, **kwargs):
        return Controller(self.config, **kwargs)

    def ensure(self):
        try:
            return self.controller().ensure(self.fixture.context())
        except GatewayError as exc:
            if exc.code == "BUSY":
                return {"state": "BUSY"}
            raise

    def action(self, action):
        return self.controller().action(action, self.fixture.context())

    def gateway(self):
        def live():
            record = (self.store.read("runtime.json") or {}).get("gateway")
            return record if record and same_process(record) else None
        return wait_until(live)

    def test_invalid_json_endpoint_cannot_create_workspace_pane_or_gateway(self):
        for fields, code in (({"type": "ok"}, "PROTOCOL_ERROR"),
                             ({"type": None}, "PROTOCOL_ERROR"),
                             ({"type": True}, "PROTOCOL_ERROR")):
            with self.subTest(fields=fields):
                self.owner.pong = {"type": "pong", "version": "0.9.1", "protocol": 22, **fields}
                with self.assertRaises(GatewayError) as error:
                    self.ensure()
                self.assertEqual(code, error.exception.code)
                self.assertIsNone(self.store.read("pending.json"))
                self.assertIsNone(self.store.read("runtime.json"))
        self.assertEqual([], self.owner.processes)
        self.assertEqual(1, len(self.owner.workspaces))
        self.assertEqual(["ping"] * 3, [r["method"] for r in self.owner.server.requests])

    def test_new_release_and_wire_protocol_can_start_a_verified_gateway(self):
        self.owner.pong.update(version="1.0.0", protocol=23)
        self.ensure()
        child = self.gateway()
        wait_until(lambda: self.controller().status()["state"] == "READY")
        self.assertTrue(same_process(child))
        self.assertEqual(1, len(self.owner.processes))

    def test_missing_required_api_blocks_creation_on_a_newer_release(self):
        self.owner.pong.update(version="1.0.0", protocol=23)
        original = self.owner.answer
        def answer(request):
            if request["method"] == "plugin.list":
                return {"id": request["id"], "error": {"code": "method_not_found"}}
            return original(request)
        self.owner.server.handler = answer
        with self.assertRaises(GatewayError) as error:
            self.ensure()
        self.assertEqual("HERDR_ERROR", error.exception.code)
        self.assertEqual(["ping", "plugin.list"], [r["method"] for r in self.owner.server.requests])
        self.assertIsNone(self.store.read("pending.json"))
        self.assertIsNone(self.store.read("runtime.json"))
        self.assertEqual([], self.owner.processes)

    def test_twenty_concurrent_hooks_create_one_gateway_without_focus_change(self):
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda _: self.ensure(), range(20)))
        child = self.gateway()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        self.assertTrue(same_process(child))
        states = [item["state"] for item in results]
        self.assertTrue(set(states) <= {"PENDING", "PENDING_UNKNOWN", "STARTING", "BUSY", "UNKNOWN", "DEGRADED", "READY"}, states)
        methods = [request["method"] for request in self.owner.server.requests]
        self.assertEqual(1, methods.count("workspace.create"))
        self.assertEqual(1, methods.count("plugin.pane.open"))
        self.assertNotEqual("w-user", self.store.read("runtime.json")["pane"]["workspace_id"])
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))
        self.assertIn("pane-user", self.owner.panes)

    def test_lost_open_response_is_reconciled_without_second_create(self):
        self.owner.drop_pane = True
        self.assertEqual("PENDING_UNKNOWN", self.ensure()["state"])
        child = self.gateway()
        result = self.ensure()
        self.assertIn(result["state"], {"STARTING", "READY", "DEGRADED"})
        self.assertTrue(same_process(child))
        self.assertEqual(1, len(self.owner.processes))
        self.assertIsNone(self.store.read("pending.json"))

    def test_unknown_workspace_result_blocks_automatic_retry(self):
        self.owner.drop_workspace = True
        self.assertEqual("PENDING_UNKNOWN", self.ensure()["state"])
        generation = self.store.read("pending.json")["generation"]
        for _ in range(3):
            self.assertEqual("PENDING_UNKNOWN", self.ensure()["state"])
        self.assertEqual(generation, self.store.read("pending.json")["generation"])
        self.assertEqual(2, len(self.owner.workspaces))
        self.assertEqual([], self.owner.processes)

    def test_pause_then_resume_revokes_unknown_generation_and_rejects_late_old_pane(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        count = [0]
        def delay_first():
            count[0] += 1
            if count[0] == 1:
                entered.set()
                release.wait(2)
        self.owner.before_open = delay_first
        with ThreadPoolExecutor(max_workers=1) as pool:
            original = pool.submit(self.ensure)
            self.assertTrue(entered.wait(2))
            old = self.store.read("pending.json")["generation"]
            self.assertTrue(self.action("pause")["accepted"])
            self.assertEqual("paused", self.store.intent()["desired"])
            self.action("resume")
            child = self.gateway()
            self.assertNotEqual(old, self.store.read("runtime.json")["generation"])
            release.set()
            self.assertEqual("CANCELLED", original.result(timeout=3)["state"])
        wait_until(lambda: len(self.owner.processes) == 2 and self.owner.processes[1].poll() is not None)
        self.assertTrue(same_process(child))
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))

    def test_controller_releases_mutation_lock_while_waiting_for_open_response(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def delayed_response():
            entered.set()
            release.wait(2)
        self.owner.after_open = delayed_response
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.ensure)
            self.assertTrue(entered.wait(2))
            # The new process acquires mutation.lock and records a child while RPC is still waiting.
            self.assertTrue(same_process(self.gateway()))
            release.set()
            self.assertEqual("STARTING", pending.result(timeout=3)["state"])

    def test_cold_restore_preserves_shell_and_reuses_only_owned_workspace(self):
        self.ensure()
        old_child = self.gateway()
        old = self.store.read("runtime.json")
        signal_verified(old["supervisor"], signal.SIGTERM)
        self.assertEqual(0, self.owner.processes[0].wait(timeout=3))
        self.assertFalse(same_process(old_child))
        self.owner.pids[old["pane"]["pane_id"]] = os.getpid()  # Cold restoration produced a user shell.
        self.ensure()
        wait_until(lambda: (self.store.read("runtime.json") or {}).get("generation") != old["generation"])
        new_child = self.gateway()
        self.assertNotEqual(new_child["pid"], old_child["pid"])
        self.assertIn(old["pane"]["pane_id"], self.owner.panes)
        self.assertEqual(os.getpid(), self.owner.pids[old["pane"]["pane_id"]])
        self.assertEqual(2, len(self.owner.workspaces))
        self.assertEqual(old["pane"]["workspace_id"], self.store.read("runtime.json")["pane"]["workspace_id"])

    def test_startup_keeps_a_diagnostic_pane_and_recovers_after_profile_correction(self):
        self.fixture.profile_data["terminal"]["backend"] = "docker"
        self.fixture.write_profile()
        Controller(self.config).ensure(self.fixture.context(), source="startup")
        blocked = wait_until(lambda: (status := self.controller().status())["state"] == "BLOCKED" and status)
        self.assertEqual("CONFIG_ERROR", blocked["code"])
        self.assertIn("terminal", blocked["message"])
        self.assertIsNone(blocked["gateway"])
        self.assertFalse(blocked["fused"])
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))
        self.fixture.profile_data["terminal"]["backend"] = "local"
        self.fixture.write_profile()
        ready = wait_until(lambda: (status := self.controller().status())["state"] == "READY" and status)
        self.assertEqual(blocked["pane"], ready["pane"])
        self.assertEqual(blocked["supervisor"], ready["supervisor"])
        self.assertIsNone(ready["code"])
        self.assertIsNone(ready["retry_at"])
        self.assertEqual(1, len(self.owner.processes))
        self.assertEqual(1, len(json_lines(self.fixture.root / "launches.jsonl")))

    def test_held_lifetime_without_identifiable_socket_never_creates(self):
        with self.store.lease():
            self.assertEqual("UNKNOWN", self.ensure()["state"])
        self.assertEqual([], self.owner.processes)
        self.assertEqual(1, len(self.owner.workspaces))

    def test_handoff_adopts_ledger_and_refreshes_terminal_id(self):
        self.ensure()
        child = self.gateway()
        runtime = self.store.read("runtime.json")
        self.owner.panes[runtime["pane"]["pane_id"]]["terminal_id"] = "terminal-new-server"
        result = self.ensure()
        self.assertEqual("terminal-new-server", result["pane"]["terminal_id"])
        self.assertTrue(same_process(child))
        self.assertEqual(1, len(self.owner.processes))
        self.assertEqual("verified_ledger", self.store.read("runtime.json")["ownership_source"])

    def test_pause_works_with_bad_yaml_and_unavailable_owner(self):
        self.ensure()
        child = self.gateway()
        private_file(self.config.profile_home / "config.yaml", "broken: [")
        self.owner.enabled = False
        with patch("hermes_gateway_herdr.controller.control_query", side_effect=GatewayError("RPC_UNAVAILABLE")):
            self.assertTrue(self.action("pause")["accepted"])
        self.assertEqual("paused", self.store.intent()["desired"])
        wait_until(lambda: not same_process(child))

    def test_malformed_optional_ack_does_not_hide_a_committed_pause(self):
        with self.store.mutation():
            self.store.write("runtime.json", {"schema": 1, "owner_key": self.config.key, "generation": "fixture",
                                             "instance_nonce": "fixture-nonce", "supervisor": capture(os.getpid()),
                                             "pane": self.owner.panes["pane-user"]})
        server = SocketServer(supervisor_socket(self.config), lambda req: {
            "id": req["id"], "protocol": 1, "ok": False, "code": [], "message": "fixture-private-sentinel"})
        self.addCleanup(server.close)
        result = self.action("pause")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["notified"])
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual(self.store.intent()["revision"], server.requests[0]["intent_revision"])
        self.assertEqual([], self.owner.processes)
        self.assertNotIn("fixture-private-sentinel", json.dumps(result))

    def test_damaged_pending_ticket_cannot_create_resources_or_be_overwritten(self):
        path = self.config.state_dir / "pending.json"
        raw = json.dumps({"schema": 1, "owner_key": self.config.key, "generation": "damaged",
                          "intent_revision": self.store.intent()["revision"], "phase": []})
        private_file(path, raw)
        with self.assertRaises(GatewayError) as error:
            self.ensure()
        self.assertEqual("STATE_SCHEMA", error.exception.code)
        self.assertEqual(raw, path.read_text())
        self.assertEqual([], self.owner.server.requests)

    def test_nonowner_and_unrelated_exit_event_do_not_create_and_owner_restores_paused_dashboard(self):
        with self.assertRaises(GatewayError) as error:
            self.controller().ensure({"HERDR_SOCKET_PATH": str(self.fixture.root / "other.sock")})
        self.assertEqual("NOT_OWNER", error.exception.code)
        env = self.fixture.context()
        env.update(HERDR_PLUGIN_EVENT="pane.exited", HERDR_PLUGIN_EVENT_JSON=json.dumps({
            "event": "pane.exited", "data": {"type": "pane_exited", "pane_id": "pane-user"}}))
        self.assertEqual("IGNORED", self.controller().ensure(env, source="event")["state"])
        self.assertEqual([], self.owner.processes)
        self.action("pause")
        self.controller().ensure(self.fixture.context(), source="startup")
        paused = wait_until(lambda: (runtime := self.store.read("runtime.json")) and runtime["state"] == "PAUSED" and runtime)
        self.assertIsNone(paused["gateway"])
        self.assertEqual("paused", self.store.intent()["desired"])
        self.assertEqual(1, len(self.owner.processes))
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))
        for _ in range(3):
            self.assertEqual("PAUSED", self.ensure()["state"])
        self.assertEqual(1, len(self.owner.processes))

    def test_status_is_read_only_and_reports_pause_without_creating_locks(self):
        self.action("pause")
        before = {path.name: path.read_bytes() for path in self.config.state_dir.iterdir()}
        self.assertEqual("PAUSED", self.controller().status()["state"])
        after = {path.name: path.read_bytes() for path in self.config.state_dir.iterdir()}
        self.assertEqual(before, after)

    def test_crash_between_popen_and_pid_record_blocks_replacement(self):
        private_file(self.fixture.root / "plan.json", json.dumps({"crash_before_child_record": True}))
        self.ensure()
        wait_until(lambda: self.owner.processes[0].poll() is not None)
        self.assertTrue(self.store.read("runtime.json")["spawn_pending"])
        self.assertEqual("UNKNOWN", self.ensure()["state"])
        self.assertEqual("UNKNOWN", self.controller().ensure(self.fixture.context(), repair=True)["state"])
        self.assertEqual(1, len(self.owner.processes))
        # The orphan is stopped only by fixture cleanup, using its captured identity.
        wait_until(lambda: bool(json_lines(self.fixture.root / "children.jsonl")))

    def test_dead_record_with_reused_pid_does_not_signal_the_replacement(self):
        record = capture(os.getpid())
        record["start_fingerprint"] = dict(record["start_fingerprint"], value="stale")
        with self.store.mutation():
            self.store.write("runtime.json", {"schema": 1, "owner_key": self.config.key, "generation": "old",
                                             "instance_nonce": "old-nonce", "supervisor": record, "gateway": record,
                                             "pane": self.owner.panes["pane-user"]})
        with patch("os.kill", side_effect=AssertionError("Controller must not signal reused PID")):
            self.ensure()
        self.assertTrue(same_process(self.gateway()))
        self.assertEqual(1, len(self.owner.processes))

    def test_short_controller_deadline_bounds_slow_owner(self):
        def slow(request):
            time.sleep(0.1)
            return self.owner.answer(request)
        self.owner.server.handler = slow
        before = time.monotonic()
        with self.assertRaises(GatewayError):
            self.controller(budget=0.03).ensure(self.fixture.context())
        self.assertLess(time.monotonic() - before, 0.5)
        self.assertEqual([], self.owner.processes)

    def test_pause_fsync_failure_cannot_ack_or_notify(self):
        self.ensure()
        child = self.gateway()
        with patch("hermes_gateway_herdr.state.os.fsync", side_effect=OSError("full")), \
                patch("hermes_gateway_herdr.controller.control_query") as query:
            with self.assertRaises(GatewayError) as error:
                self.action("pause")
            self.assertEqual("IO_ERROR", error.exception.code)
            query.assert_not_called()
        self.assertEqual("running", self.store.intent()["desired"])
        self.assertTrue(same_process(child))

    def test_orphan_blocks_creation_and_pause_does_not_claim_it_has_stopped(self):
        self.ensure()
        child = self.gateway()
        wait_until(lambda: (self.fixture.root / "gateway-up").exists())
        signal_verified(self.owner.records[0], signal.SIGKILL)
        self.owner.processes[0].wait(timeout=3)
        self.assertEqual("ORPHAN", self.ensure()["state"])
        self.assertEqual("ORPHAN", self.controller().ensure(self.fixture.context(), repair=True)["state"])
        self.assertTrue(self.action("pause")["accepted"])
        status = self.controller().status()
        self.assertEqual("ORPHAN", status["state"])
        self.assertEqual("paused", status["desired"])
        self.assertTrue(same_process(child))
        self.assertEqual(1, len(self.owner.processes))

    def crash_controller(self, point):
        result = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).with_name("process_fixture.py")),
                                 "controller", str(self.config.config_dir / "config.json"), point],
                                env=self.fixture.context(), stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
        self.assertEqual(91, result.returncode, result.stderr.decode())
        self.assertEqual(b"", result.stderr)

    def test_controller_crash_before_workspace_send_remains_unknown(self):
        self.crash_controller("before_workspace")
        self.assertEqual("PENDING_UNKNOWN", self.ensure()["state"])
        self.assertEqual("PENDING_UNKNOWN", self.ensure()["state"])
        self.assertEqual(1, len(self.owner.workspaces))

    def test_controller_crash_after_workspace_response_never_blindly_retries(self):
        self.crash_controller("after_workspace")
        self.assertEqual("PENDING_UNKNOWN", self.ensure()["state"])
        self.assertEqual(2, len(self.owner.workspaces))
        self.assertEqual([], self.owner.processes)

    def test_controller_crash_before_pane_send_is_fenced_until_explicit_resume(self):
        self.crash_controller("before_pane")
        old = self.store.read("pending.json")["generation"]
        self.assertEqual("PENDING_UNKNOWN", self.ensure()["state"])
        self.action("resume")
        self.assertTrue(same_process(self.gateway()))
        self.assertNotEqual(old, self.store.read("runtime.json")["generation"])
        self.assertEqual(1, len(self.owner.processes))

    def test_manual_repair_rebuilds_after_dead_creator_without_resetting_running_fuse(self):
        self.crash_controller("before_pane")
        old = self.store.read("pending.json")["generation"]
        reset = self.store.intent()["reset_revision"]
        fuse = {"schema": 1, "fused": True, "failures": [], "restarts": [], "reset_revision": reset}
        with self.store.mutation():
            self.store.write("fuse.json", fuse)
        self.assertIn("pane", self.controller().ensure(self.fixture.context(), repair=True))
        runtime = wait_until(lambda: (item := self.store.read("runtime.json")) and item["state"] == "FUSED" and item)
        self.assertNotEqual(old, runtime["generation"])
        self.assertIsNone(runtime["gateway"])
        self.assertEqual("running", self.store.intent()["desired"])
        self.assertEqual(reset, self.store.intent()["reset_revision"])
        self.assertEqual(fuse, self.store.read("fuse.json"))
        self.assertEqual([], json_lines(self.fixture.root / "launches.jsonl"))

    def test_controller_crash_after_pane_response_adopts_surviving_supervisor(self):
        self.crash_controller("after_pane")
        child = self.gateway()
        self.assertIn(self.ensure()["state"], {"STARTING", "DEGRADED", "READY"})
        self.assertTrue(same_process(child))
        self.assertEqual(1, len(self.owner.processes))
