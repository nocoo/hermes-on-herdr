import copy
from dataclasses import replace
import fcntl
import json
import os
from pathlib import Path
import time
import unittest

from hermes_gateway_herdr.config import HERMES_SHA, PLUGIN_ID
from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture
from hermes_gateway_herdr.paths import private_bytes
from hermes_gateway_herdr.rpc import GatewayProbe, Herdr, control_query, evaluate_gateway, exchange, hermes_socket, profile_in_use
from helpers import Fixture, SocketServer, private_file


def gateway_payloads(config, child):
    fingerprint = child["start_fingerprint"]
    start = (int(fingerprint["value"]) if fingerprint["kind"] == "linux_ticks"
             else int(round(child["create_time"] * 100)))
    identity = {"protocol": 1, "kind": "hermes-gateway", "pid": child["pid"],
                "start_time": start, "hermes_home": str(config.profile_home),
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

    def test_checkout_alias_preserves_live_ownership_but_a_different_directory_is_rejected(self):
        old, new = self.fixture.root / "old-checkout", self.fixture.root / "new-checkout"
        old.mkdir()
        new.mkdir()
        registered = {"plugin_id": PLUGIN_ID, "enabled": True, "plugin_root": str(old)}
        self.serve(self.config.owner_socket, lambda req: {"id": req["id"], "result": {"plugins": [registered]}})
        # This client already holds the old configuration, like a running supervisor.
        client = Herdr(replace(self.config, plugin_root=old))
        self.assertTrue(client.enabled())
        registered["plugin_root"] = str(new)
        with self.assertRaises(GatewayError) as error:
            client.enabled()
        self.assertEqual("OWNERSHIP_CONFLICT", error.exception.code)
        old.rename(old.with_name("archived-checkout"))
        old.symlink_to(new, target_is_directory=True)
        self.assertTrue(client.enabled())
        self.assertTrue(Herdr(replace(self.config, plugin_root=new)).enabled())

    def serve(self, path, handler):
        server = SocketServer(path, handler)
        self.addCleanup(server.close)
        return server

    def test_herdr_accepts_release_and_wire_changes_with_the_same_json_api(self):
        pong = {"type": "pong"}
        server = self.serve(self.config.owner_socket, lambda req: {"id": req["id"], "result": dict(pong)})
        client = Herdr(self.config)
        for version in ("0.9.0", "0.9.1", "0.10.0", "1.0.0", "2.3.4", "0.10.0-rc.1", "dev-build"):
            for protocol in (21, 22, 23, 999):
                with self.subTest(version=version, protocol=protocol):
                    pong.update(version=version, protocol=protocol, capabilities={"future": True})
                    self.assertEqual({"version": version, "protocol": protocol}, client.available())
        self.assertEqual(["ping"] * 28, [r["method"] for r in server.requests])

    def test_herdr_metadata_is_optional_and_sanitized_without_becoming_a_gate(self):
        pong = {"type": "pong"}
        self.serve(self.config.owner_socket, lambda req: {"id": req["id"], "result": dict(pong)})
        self.assertEqual({"version": None, "protocol": None}, Herdr(self.config).available())
        for version in (None, True, [], {}, "", "bad\nversion", "x" * 129):
            for protocol in (None, True, "22", 22.0, -1, [], {}, 2 ** 32):
                with self.subTest(version=version, protocol=protocol):
                    pong.update(version=version, protocol=protocol)
                    self.assertEqual({"version": None, "protocol": None}, Herdr(self.config).available())

    def test_herdr_rejects_non_pong_responses_without_echoing_peer_text(self):
        pong = {}
        self.serve(self.config.owner_socket, lambda req: {"id": req["id"], "result": dict(pong)})
        for fields in ({}, {"type": None}, {"type": True}, {"type": []}, {"type": {}},
                       {"type": "fixture-private-sentinel"}):
            with self.subTest(fields=fields):
                pong.clear()
                pong.update(fields)
                with self.assertRaises(GatewayError) as error:
                    Herdr(self.config).available()
                self.assertEqual("PROTOCOL_ERROR", error.exception.code)
                self.assertNotIn("fixture-private-sentinel", str(error.exception))

    def test_herdr_rechecks_the_live_server_after_an_upgrade(self):
        pong = {"type": "pong", "version": "0.9.0", "protocol": 22}
        server = self.serve(self.config.owner_socket, lambda req: {"id": req["id"], "result": dict(pong)})
        client = Herdr(self.config)
        self.assertEqual("0.9.0", client.available()["version"])
        pong.update(version="1.0.0", protocol=23)
        self.assertEqual({"version": "1.0.0", "protocol": 23}, client.available())
        pong["type"] = "incompatible-response"
        with self.assertRaises(GatewayError) as error:
            client.available()
        self.assertEqual("PROTOCOL_ERROR", error.exception.code)
        self.assertEqual(["ping"] * 3, [r["method"] for r in server.requests])

    def test_plugin_registration_requires_an_explicit_absolute_root(self):
        registered = {"plugin_id": PLUGIN_ID, "enabled": True}
        self.serve(self.config.owner_socket, lambda req: {"id": req["id"], "result": {"plugins": [registered]}})
        for fields in ({}, {"plugin_root": None}, {"plugin_root": []}, {"plugin_root": {}},
                       {"plugin_root": ""}, {"plugin_root": "."}, {"plugin_root": "relative/checkout"},
                       {"plugin_root": "/bad\x00root"}, {"plugin_root": "/bad\nroot"}):
            with self.subTest(fields=fields):
                registered.clear()
                registered.update(plugin_id=PLUGIN_ID, enabled=True, **fields)
                with self.assertRaises(GatewayError) as error:
                    Herdr(self.config).enabled()
                self.assertEqual("PROTOCOL_ERROR", error.exception.code)

    def test_plugin_registration_rejects_ambiguous_or_malformed_enablement(self):
        registered = {"plugin_id": PLUGIN_ID, "enabled": True, "plugin_root": str(self.config.plugin_root)}
        result = {}
        self.serve(self.config.owner_socket, lambda req: {"id": req["id"], "result": result})
        for plugins in (None, {}, [registered, registered], [dict(registered, enabled=1)],
                        [{"plugin_id": PLUGIN_ID, "plugin_root": str(self.config.plugin_root)}]):
            with self.subTest(plugins=plugins):
                result["plugins"] = plugins
                with self.assertRaises(GatewayError) as error:
                    Herdr(self.config).enabled()
                self.assertEqual("PROTOCOL_ERROR", error.exception.code)
        for plugins in ([], [{"plugin_id": "unrelated"}], [dict(registered, enabled=False)]):
            result["plugins"] = plugins
            self.assertFalse(Herdr(self.config).enabled())

    def test_control_rejections_sanitize_peer_codes_of_any_json_type(self):
        rejection = {"protocol": 1, "ok": False, "message": "fixture-private-sentinel"}
        self.serve(self.config.owner_socket, lambda req: dict(rejection, id=req["id"]))
        for code in ([], {}, None, True, 42, "fixture-private-sentinel", "BUSY", "STATE_SCHEMA"):
            with self.subTest(code=code):
                rejection["code"] = code
                with self.assertRaises(GatewayError) as error:
                    control_query(self.config.owner_socket, "status")
                self.assertEqual(code if code in ("BUSY", "STATE_SCHEMA") else "PROTOCOL_ERROR", error.exception.code)
                self.assertNotIn("fixture-private-sentinel", str(error.exception))

    def test_control_response_requires_exact_protocol_and_result_object(self):
        response = {}
        self.serve(self.config.owner_socket, lambda req: dict(response, id=req["id"]))
        for fields in ({}, {"protocol": True}, {"protocol": 2}, {"ok": 1}, {"result": []}, {"result": None}):
            with self.subTest(fields=fields):
                response.clear()
                response.update(protocol=1, ok=True, result={})
                if not fields:
                    response.pop("protocol")
                response.update(fields)
                with self.assertRaises(GatewayError) as error:
                    control_query(self.config.owner_socket, "status")
                self.assertEqual("PROTOCOL_ERROR", error.exception.code)

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
                   b'{"id":"request"}', b'x' * 1000 + b'\n', b'[]\n', b'{"id":"request","value":1e999}\n']
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

    def test_private_executable_hermes_pid_blocks_live_but_not_stale_process(self):
        pid = self.config.profile_home / "gateway.pid"
        for start, expected in [(self.identity["start_time"], True), (1, False)]:
            with self.subTest(start=start):
                private_file(pid, json.dumps({"pid": self.child["pid"], "start_time": start}))
                pid.chmod(0o700)
                before = pid.read_bytes(), pid.stat().st_ino, pid.stat().st_mode
                self.assertIs(expected, profile_in_use(self.config))
                self.assertEqual(before, (pid.read_bytes(), pid.stat().st_ino, pid.stat().st_mode))
                # Configuration and plugin state retain their strict 0600 contract.
                with self.assertRaises(GatewayError):
                    private_bytes(pid)

    def test_hermes_pid_permissions_exception_keeps_privacy_and_link_checks(self):
        pid = self.config.profile_home / "gateway.pid"
        private_file(pid, json.dumps({"pid": self.child["pid"], "start_time": 1}))
        for mode in [0o644, 0o755, 0o710, 0o701]:
            with self.subTest(mode=oct(mode)):
                pid.chmod(mode)
                with self.assertRaises(GatewayError):
                    profile_in_use(self.config)
        pid.chmod(0o700)
        linked = self.fixture.root / "linked-pid"
        os.link(pid, linked)
        with self.assertRaises(GatewayError):
            profile_in_use(self.config)
        pid.unlink()
        pid.symlink_to(linked)
        with self.assertRaises(GatewayError):
            profile_in_use(self.config)
