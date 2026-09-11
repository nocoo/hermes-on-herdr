import copy
from dataclasses import replace
import fcntl
import json
import os
from pathlib import Path
import time
import unittest

from hermes_gateway_herdr.config import HERMES_SHA
from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture
from hermes_gateway_herdr.rpc import GatewayProbe, Herdr, evaluate_gateway, exchange, hermes_socket, profile_in_use
from helpers import Fixture, SocketServer, private_file


def gateway_payloads(config, child):
    identity = {"protocol": 1, "kind": "hermes-gateway", "pid": child["pid"],
                "start_time": int(child["start_fingerprint"]["value"]), "hermes_home": str(config.profile_home),
                "profile": config.profile_id, "supervisor": "external", "code_sha": HERMES_SHA}
    status = dict(identity, answering_pid=child["pid"], answered_at=time.time(), gateway_state="running",
                  platforms={"telegram": {"state": "connected", "writer_pid": child["pid"],
                                          "writer_start_time": identity["start_time"]}})
    return identity, status


class RpcTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config
        self.child = capture(os.getpid())
        self.identity, self.status = gateway_payloads(self.config, self.child)

    def serve(self, path, handler):
        server = SocketServer(path, handler)
        self.addCleanup(server.close)
        return server

    def test_readiness_needs_two_spaced_observations_and_resets_after_failure(self):
        probe = GatewayProbe(self.config)
        self.assertEqual(1, probe.observe(self.child, self.identity, self.status, 0)["level"])
        self.assertEqual(1, probe.observe(self.child, self.identity, self.status, 0.5)["level"])
        self.assertEqual(2, probe.observe(self.child, self.identity, self.status, 1)["level"])
        self.status["platforms"]["telegram"]["writer_pid"] = 0
        self.assertEqual("DEGRADED", probe.observe(self.child, self.identity, self.status, 2)["state"])
        self.status["platforms"]["telegram"]["writer_pid"] = self.child["pid"]
        self.assertEqual(1, probe.observe(self.child, self.identity, self.status, 3)["level"])

    def test_stale_platform_writer_and_cron_only_never_become_ready(self):
        for patch in ({"writer_pid": 0}, {"writer_start_time": 1}, {"needs_attention": True},
                      {"error_code": "BAD_TOKEN"}, {"state": "retrying"}):
            status = copy.deepcopy(self.status)
            status["platforms"]["telegram"].update(patch)
            self.assertFalse(evaluate_gateway(self.config, self.child, self.identity, status)["operational"])
        self.status["platforms"] = {}
        self.assertFalse(evaluate_gateway(self.config, self.child, self.identity, self.status)["operational"])

    def test_live_wrong_home_pid_version_and_multiplex_are_rejected(self):
        for patch in ({"hermes_home": "/other"}, {"pid": 1}, {"start_time": 1}, {"code_sha": "new-version"},
                      {"supervisor": "manual"}, {"served_profiles": ["default"]}, {"hermes_home": None}):
            with self.subTest(patch=patch), self.assertRaises(GatewayError):
                evaluate_gateway(self.config, self.child, dict(self.identity, **patch), self.status)

    def test_probe_uses_new_socket_connections_and_matches_response_ids(self):
        def handler(request):
            payload = self.identity if request["verb"] == "identify" else self.status
            return {"id": request["id"], "ok": True, "protocol": 1, "result": payload}
        server = self.serve(self.config.profile_home / "gateway.sock", handler)
        probe = GatewayProbe(self.config, interval=0)
        self.assertEqual(1, probe.inspect(self.child)["level"])
        self.assertEqual(2, probe.inspect(self.child)["level"])
        self.assertEqual(["identify", "status", "identify", "status"], [r["verb"] for r in server.requests])
        self.assertEqual(4, len({r["id"] for r in server.requests}))

    def test_malformed_large_and_unterminated_frames_are_rejected(self):
        replies = [b'{"id":"wrong"}\n', b'{"id":"request","id":"request"}\n',
                   b'{"id":"request"}', b'x' * 1000 + b'\n', b'[]\n']
        index = [0]
        def handler(_):
            reply = replies[index[0]]
            index[0] += 1
            return reply
        self.serve(self.config.owner_socket, handler)
        for _ in replies:
            with self.assertRaises(GatewayError):
                exchange(self.config.owner_socket, {"id": "request"}, limit=512)

    def test_slow_peer_cannot_extend_deadline(self):
        def handler(_):
            time.sleep(0.15)
            return b'{}\n'
        self.serve(self.config.owner_socket, handler)
        started = time.monotonic()
        with self.assertRaises(GatewayError):
            exchange(self.config.owner_socket, {"id": "request"}, timeout=0.03)
        self.assertLess(time.monotonic() - started, 2)

    def test_handoff_accepts_new_terminal_id_but_not_moved_pane(self):
        pane = {"workspace_id": "w-fixture", "tab_id": "tab-fixture", "pane_id": "pane-fixture", "terminal_id": "new"}
        expected = dict(pane, terminal_id="old")
        def handler(request):
            result = {"pane": pane} if request["method"] == "pane.get" else {
                "process_info": {"pane_id": pane["pane_id"], "shell_pid": self.child["pid"]}}
            return {"id": request["id"], "result": result}
        self.serve(self.config.owner_socket, handler)
        self.assertEqual("new", Herdr(self.config).membership(expected, self.child)["terminal_id"])
        pane["workspace_id"] = "moved"
        with self.assertRaises(GatewayError) as error:
            Herdr(self.config).membership(expected, self.child)
        self.assertEqual("ENV_STALE", error.exception.code)

    def test_long_socket_pointer_cannot_target_another_file(self):
        home = self.fixture.root / ("long" * 25) / "profiles" / "herdr-control"
        home.mkdir(parents=True, mode=0o700)
        private_file(home / "gateway.sock.path", "/tmp/someone-elses.sock")
        with self.assertRaises(GatewayError) as error:
            hermes_socket(replace(self.config, profile_home=home))
        self.assertEqual("UNSAFE_PATH", error.exception.code)

    def test_hermes_fences_block_launch_without_modifying_upstream_files(self):
        self.assertFalse(profile_in_use(self.config))
        lock = self.config.profile_home / "gateway.lock"
        private_file(lock, "fixture lock")
        inode = lock.stat().st_ino
        with lock.open() as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertTrue(profile_in_use(self.config))
        self.assertFalse(profile_in_use(self.config))
        self.assertEqual(inode, lock.stat().st_ino)
        self.assertEqual("fixture lock", lock.read_text())
        pid = self.config.profile_home / "gateway.pid"
        private_file(pid, json.dumps({"pid": self.child["pid"], "start_time": self.identity["start_time"]}))
        self.assertTrue(profile_in_use(self.config))
        private_file(pid, json.dumps({"pid": self.child["pid"], "start_time": 1}))
        self.assertFalse(profile_in_use(self.config))
        private_file(pid, json.dumps({"pid": self.child["pid"]}))
        with self.assertRaises(GatewayError):
            profile_in_use(self.config)

    def test_unresponsive_gateway_socket_is_unknown_not_absent(self):
        def slow(_):
            time.sleep(0.05)
            return None
        self.serve(self.config.profile_home / "gateway.sock", slow)
        with self.assertRaises(GatewayError) as error:
            profile_in_use(self.config, timeout=0.01)
        self.assertEqual("UNKNOWN", error.exception.code)
