from dataclasses import replace
import json
import os
from pathlib import Path
from unittest import TestCase, mock
import time

from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.monitor import (HISTORY, PROBE_BATCH, Monitor, Profile, discover,
                                         inspect_profile, metadata, text)
from helpers import Fixture, SocketServer, private_file


class MonitorTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config

    def profile(self, name):
        path = self.fixture.root / "profiles" / name
        path.mkdir(mode=0o700)
        return Profile(name, path)

    def native(self, profile):
        # Socket exchange is injected; the marker only drives discovery of that endpoint.
        private_file(profile.home / "gateway.sock", "")
        record = {"pid": 31415, "uid": os.getuid(), "create_time": 1234.566,
                  "start_fingerprint": {"kind": "epoch_centiseconds", "boot": "fixture", "value": "123456"}}
        identity = {"protocol": 1, "kind": "hermes-gateway", "profile": profile.name,
                    "hermes_home": str(profile.home), "pid": 31415, "start_time": 123457,
                    "supervisor": "manual", "served_profiles": []}
        status = dict(identity, answering_pid=31415, answered_at=time.time(), gateway_state="running", active_agents=2,
                      platforms={"discord": {"state": "connected", "writer_pid": 31415, "writer_start_time": 123457}})
        query = mock.Mock(side_effect=lambda path, verb, **kw: identity if verb == "identify" else status)
        process = mock.Mock(return_value=record)
        metrics = mock.Mock(return_value=(2.5, 40 * 1048576))
        return identity, status, query, process, metrics

    def inspect(self, profile, query, process, metrics):
        return inspect_profile(self.config, profile, query=query, process=process, metrics=metrics)

    def test_discovers_default_and_named_profiles_without_touching_secrets(self):
        self.profile("alpha_1")
        self.profile("deleted")
        self.profile(".staging")
        self.profile("INVALID")
        (self.fixture.root / "profiles" / "alias").symlink_to(self.fixture.profile, target_is_directory=True)
        tombstones = self.fixture.root / "profiles" / ".deleted"
        tombstones.mkdir()
        (tombstones / "deleted").touch()
        with mock.patch.object(Path, "read_text", side_effect=AssertionError("No configuration or secret reads")):
            rows = discover(self.config)
        self.assertEqual([p.name for p in rows], ["herdr-control", "default", "alpha_1"])
        self.assertEqual([p.name for p in rows if p.managed], ["herdr-control"])

    def test_native_metadata_accepts_readable_modes_but_not_unsafe_objects(self):
        path = self.fixture.profile / "gateway.pid"
        for mode in (0o600, 0o644, 0o700):
            private_file(path, '{"pid":12}')
            path.chmod(mode)
            before = path.stat()
            self.assertEqual(metadata(path), {"pid": 12})
            self.assertEqual((path.stat().st_ino, path.stat().st_mode), (before.st_ino, before.st_mode))
        for mode in (0o660, 0o666):
            path.chmod(mode)
            with self.assertRaises(GatewayError):
                metadata(path)
        path.chmod(0o600)
        alias = path.with_name("alias")
        alias.symlink_to(path)
        with self.assertRaises(OSError):
            metadata(alias)
        alias.unlink()
        os.link(path, alias)
        with self.assertRaises(GatewayError):
            metadata(path)
        alias.unlink()
        path.unlink()
        os.mkfifo(path, 0o600)
        start = time.monotonic()
        with self.assertRaises(GatewayError):
            metadata(path)
        self.assertLess(time.monotonic() - start, 0.1)

    def test_native_metadata_is_bounded_and_does_not_accept_invalid_json(self):
        path = self.fixture.profile / "gateway.pid"
        for data in ('{"pid":NaN}', '[1]', '{"pid":1,"pid":2}', ' ' * 65537):
            private_file(path, data)
            with self.assertRaises(GatewayError):
                metadata(path)

    def test_live_probe_matches_exact_home_identity_and_writer_before_showing_connected(self):
        profile = self.profile("personal")
        identity, status, query, process, metrics = self.native(profile)
        result, cpu = self.inspect(profile, query, process, metrics)
        self.assertEqual((result.state, result.pid, result.active, cpu), ("RUNNING", 31415, 2, 2.5))
        self.assertEqual(result.platforms, (("discord", "connected"),))
        self.assertEqual([call.args[1] for call in query.call_args_list], ["identify", "status"])
        self.assertEqual(process.call_count, 2)
        status["platforms"]["discord"]["writer_start_time"] += 1
        result, _ = self.inspect(profile, query, process, metrics)
        self.assertEqual(result.state, "DEGRADED")
        self.assertEqual(result.platforms, (("discord", "unverified"),))

    def test_cross_profile_recycled_pid_and_old_answers_never_look_healthy(self):
        profile = self.profile("personal")
        for field, value in (("hermes_home", str(self.fixture.root)), ("start_time", 123456),
                             ("profile", "other"), ("protocol", True)):
            with self.subTest(field=field):
                identity, status, query, process, metrics = self.native(profile)
                identity[field] = value
                result, _ = self.inspect(profile, query, process, metrics)
                self.assertEqual(result.state, "UNKNOWN")
                metrics.assert_not_called()
        identity, status, query, process, metrics = self.native(profile)
        status["answered_at"] -= 30
        self.assertEqual(self.inspect(profile, query, process, metrics)[0].state, "UNKNOWN")
        status["answered_at"] = time.time()
        record = process.return_value
        process.side_effect = [record, dict(record, start_fingerprint=dict(record["start_fingerprint"], value="99999"))]
        self.assertEqual(self.inspect(profile, query, process, metrics)[0].state, "UNKNOWN")

    def test_live_pid_without_control_is_unknown_and_dead_pid_is_stopped(self):
        profile = self.profile("personal")
        path = profile.home / "gateway.pid"
        private_file(path, '{"pid":31415}')
        before = path.read_bytes(), path.stat().st_ino
        result, _ = inspect_profile(self.config, profile, process=lambda pid: {"pid": pid})
        self.assertEqual(result.state, "UNKNOWN")
        result, _ = inspect_profile(self.config, profile, process=lambda pid: None)
        self.assertEqual(result.state, "STOPPED")
        self.assertEqual((path.read_bytes(), path.stat().st_ino), before)

    def test_never_started_long_profile_does_not_require_a_socket_pointer(self):
        profile = self.profile("a" * 64)
        self.assertGreater(len(os.fsencode(profile.home / "gateway.sock")), 100)
        result, _ = inspect_profile(self.config, profile)
        self.assertEqual(result.state, "STOPPED")

    def test_real_slow_socket_has_a_short_deadline_and_only_receives_read_requests(self):
        profile = self.profile("slow")
        def answer(request):
            time.sleep(0.3)
            return None
        server = SocketServer(profile.home / "gateway.sock", answer)
        self.addCleanup(server.close)
        started = time.monotonic()
        result, _ = inspect_profile(self.config, profile)
        self.assertLess(time.monotonic() - started, 0.28)
        self.assertEqual(result.state, "UNKNOWN")
        self.assertEqual([r["verb"] for r in server.requests], ["identify"])

    def test_failed_probe_drops_old_connected_data_and_error_text(self):
        profile = self.profile("personal")
        identity, status, query, process, metrics = self.native(profile)
        good, _ = self.inspect(profile, query, process, metrics)
        query.side_effect = GatewayError("RPC_UNAVAILABLE", "token=secret\x1b]52;clipboard")
        bad, cpu = self.inspect(good, query, process, metrics)
        self.assertEqual((bad.state, bad.pid, bad.platforms, bad.active, cpu), ("UNKNOWN", None, (), None, None))
        self.assertNotIn("secret", repr(bad))
        self.assertEqual(text("a\x1b\n\r\x07b"), "ab")

    def test_many_profiles_have_fair_bounded_sampling_and_no_process_table_scan(self):
        for i in range(20):
            self.profile(f"worker-{i:02}")
        calls = []
        def inspect(config, profile):
            calls.append(profile.name)
            return replace(profile, state="STOPPED"), None
        monitor = Monitor(self.config, inspect=inspect, managed_status=lambda: {"state": "PAUSED"}, host=False)
        monitor.selected = "worker-19"
        with mock.patch("psutil.process_iter", side_effect=AssertionError("No whole-host process scans")), \
                mock.patch("psutil.cpu_percent", side_effect=AssertionError("System sampling is disabled")):
            for i in range(11):
                offset = len(calls)
                result = monitor.collect(now=10 + i * 2)
                batch = calls[offset:]
                self.assertLessEqual(len(batch), PROBE_BATCH)
                self.assertEqual(batch[:2], ["herdr-control", "worker-19"])
        self.assertEqual(set(calls), {p.name for p in result.profiles})

    def test_cpu_deltas_use_elapsed_time_reset_for_new_process_and_bound_history(self):
        cpu = [2.0]
        pid = [123]
        def inspect(config, profile):
            return replace(profile, pid=pid[0], started=float(pid[0]), rss=1048576, state="RUNNING"), cpu[0]
        monitor = Monitor(self.config, inspect=inspect, managed_status=lambda: {"state": "RUNNING"}, host=False)
        self.assertIsNone(monitor.collect(now=1).profiles[0].cpu)
        cpu[0] += .1
        self.assertAlmostEqual(monitor.collect(now=3).profiles[0].cpu, 5.0)
        pid[0] += 1
        self.assertIsNone(monitor.collect(now=4).profiles[0].cpu)
        for i in range(HISTORY + 5):
            cpu[0] += .1
            profile = monitor.collect(now=5 + i * 2).profiles[0]
        self.assertEqual(len(profile.cpu_history), HISTORY)
        self.assertEqual(len(profile.memory_history), HISTORY)

    def test_managed_state_cannot_promote_wrong_native_pid_or_disconnected_platform(self):
        sampled = {"state": "RUNNING", "pid": 123, "started": 1, "rss": 100}
        monitor = Monitor(self.config, inspect=lambda c, p: (replace(p, **sampled), 1), host=False,
                          managed_status=lambda: {"state": "READY", "gateway": {"pid": 999}})
        self.assertEqual(monitor.collect(now=1).profiles[0].state, "UNKNOWN")
        monitor.managed_status = lambda: {"state": "READY", "gateway": {"pid": 123}}
        sampled["state"] = "DEGRADED"
        self.assertEqual(monitor.collect(now=3).profiles[0].state, "DEGRADED")
        sampled["state"] = "RUNNING"
        self.assertEqual(monitor.collect(now=5).profiles[0].state, "READY")

    def test_multiplexer_shows_shared_profile_without_double_counting_resources(self):
        self.profile("shared")
        def inspect(config, profile):
            if profile.name == "default":
                return replace(profile, state="RUNNING", pid=123, started=1, rss=1024, served=("default", "shared")), 1
            return replace(profile, state="STOPPED"), None
        monitor = Monitor(self.config, inspect=inspect, host=False, managed_status=lambda: {"state": "PAUSED"})
        rows = {p.name: p for p in monitor.collect(now=1).profiles}
        self.assertEqual((rows["shared"].state, rows["shared"].shared_from, rows["shared"].pid), ("SHARED", "default", 123))
        self.assertIsNone(rows["shared"].rss)
        self.assertIsNone(rows["shared"].active)
        self.assertEqual(rows["shared"].platforms, ())

    def test_one_profile_error_does_not_break_other_samples_and_removal_cleans_cache(self):
        extra = self.profile("extra")
        def inspect(config, profile):
            if profile.name == "default":
                raise ValueError("private detail")
            return replace(profile, state="STOPPED"), None
        monitor = Monitor(self.config, inspect=inspect, host=False, managed_status=lambda: {"state": "PAUSED"})
        rows = monitor.collect(now=1).profiles
        self.assertEqual([p.state for p in rows], ["PAUSED", "UNKNOWN", "STOPPED"])
        extra.home.rmdir()
        self.assertEqual(len(monitor.collect(now=32).profiles), 2)
        self.assertNotIn("extra", monitor._histories)
