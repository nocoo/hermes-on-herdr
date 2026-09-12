import errno
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import psutil

from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture, descendants, hermes_start_matches, owner_key, signal_verified


class IdentityTests(unittest.TestCase):
    def test_linux_identity_reads_proc_ticks_with_spaces_and_parentheses_in_process_name(self):
        pid = os.getpid()
        files = {f"/proc/{pid}/stat": f"{pid} (gateway worker ) (child)) S " + " ".join(map(str, range(4, 53))),
                 "/proc/sys/kernel/random/boot_id": "fixture-boot\n"}
        with patch("hermes_gateway_herdr.identity.sys.platform", "linux"), \
                patch.object(Path, "read_text", autospec=True, side_effect=lambda path: files[str(path)]):
            record = capture(pid)
        self.assertEqual({"kind": "linux_ticks", "boot": "fixture-boot", "value": "22"}, record["start_fingerprint"])
        self.assertTrue(hermes_start_matches(record, 22))

    def test_unavailable_pidfd_falls_back_only_after_rechecking_process_identity(self):
        record = capture(os.getpid())
        reused = dict(record, start_fingerprint=dict(record["start_fingerprint"], value="reused"))
        for current in (record, reused):
            with self.subTest(reused=current is reused), \
                    patch("hermes_gateway_herdr.identity.capture", side_effect=[record, current]), \
                    patch.object(os, "pidfd_open", create=True, side_effect=OSError(errno.ENOSYS, "Not implemented")), \
                    patch.object(signal, "pidfd_send_signal", create=True) as send, patch.object(os, "kill") as kill:
                if current is record:
                    self.assertTrue(signal_verified(record, signal.SIGTERM))
                    kill.assert_called_once_with(record["pid"], signal.SIGTERM)
                else:
                    with self.assertRaises(GatewayError) as error:
                        signal_verified(record, signal.SIGTERM)
                    self.assertEqual("IDENTITY_CHANGED", error.exception.code)
                    kill.assert_not_called()
                send.assert_not_called()

    def test_pidfd_permission_failure_never_falls_back_to_kill(self):
        record = capture(os.getpid())
        with patch.object(os, "pidfd_open", create=True, side_effect=PermissionError(errno.EPERM, "Denied")), \
                patch.object(signal, "pidfd_send_signal", create=True) as send, patch.object(os, "kill") as kill:
            with self.assertRaises(GatewayError) as error:
                signal_verified(record, signal.SIGTERM)
            self.assertEqual("STOP_FAILED", error.exception.code)
            kill.assert_not_called()
            send.assert_not_called()

    def test_aliases_share_owner_key_and_pid_is_not_part_of_binding(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "profile"
            profile.mkdir()
            alias = Path(root) / "alias"
            alias.symlink_to(profile, target_is_directory=True)
            self.assertEqual(owner_key(profile, Path(root) / "owner.sock"),
                             owner_key(alias, Path(root) / "owner.sock"))
            self.assertNotEqual(owner_key(profile, Path(root) / "owner.sock"),
                                owner_key(profile, Path(root) / "other.sock"))

    def test_reused_pid_never_receives_signal(self):
        child = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import sys; sys.stdin.read()"],
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            identity = capture(child.pid)
            stale = dict(identity, start_fingerprint=dict(identity["start_fingerprint"], value="not-this-process"))
            with self.assertRaises(GatewayError) as error:
                signal_verified(stale, signal.SIGTERM)
            self.assertEqual("IDENTITY_CHANGED", error.exception.code)
            self.assertIsNone(child.poll())
            self.assertTrue(signal_verified(identity, signal.SIGTERM))
            child.wait(timeout=10)
            self.assertFalse(signal_verified(identity, signal.SIGTERM))
        finally:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=10)

    def test_permission_failure_is_unknown_not_absent(self):
        with patch("hermes_gateway_herdr.identity.psutil.Process", side_effect=psutil.AccessDenied()):
            with self.assertRaises(GatewayError) as error:
                capture(os.getpid())
            self.assertEqual("UNKNOWN", error.exception.code)

    def test_hermes_fingerprint_units_are_explicit(self):
        identity = capture(os.getpid())
        self.assertTrue(hermes_start_matches(identity, int(round(identity["create_time"] * 100))))
        self.assertFalse(hermes_start_matches(identity, identity["create_time"]))
        self.assertFalse(hermes_start_matches(identity, "2026-09-11T00:00:00Z"))

    def test_hermes_psutil_start_rounding_rejects_adjacent_centiseconds(self):
        for kind in ["epoch_centiseconds", "linux_ticks"]:
            for created, expected in [(1234.564, 123456), (1234.566, 123457)]:
                with self.subTest(kind=kind, created=created):
                    record = {"create_time": created,
                              "start_fingerprint": {"kind": kind, "value": "9001"}}
                    self.assertTrue(hermes_start_matches(record, expected))
                    self.assertFalse(hermes_start_matches(record, expected - 1))
                    self.assertFalse(hermes_start_matches(record, expected + 1))
                    if kind == "linux_ticks":
                        self.assertTrue(hermes_start_matches(record, 9001))

    def test_permission_race_requires_proof_of_disappearance(self):
        proc = psutil.Process(os.getpid())
        with patch("hermes_gateway_herdr.identity.psutil.Process", return_value=proc), \
                patch.object(proc, "uids", side_effect=psutil.AccessDenied()), \
                patch.object(proc, "is_running", return_value=False):
            self.assertIsNone(capture(os.getpid()))

    def test_permission_race_requires_proof_of_zombie_before_treating_it_as_absent(self):
        proc = psutil.Process(os.getpid())
        for status in (psutil.STATUS_ZOMBIE, psutil.NoSuchProcess(os.getpid()), psutil.STATUS_SLEEPING):
            with self.subTest(status=status), \
                    patch("hermes_gateway_herdr.identity.psutil.Process", return_value=proc), \
                    patch.object(proc, "uids", side_effect=psutil.AccessDenied()), \
                    patch.object(proc, "is_running", return_value=True), \
                    patch.object(proc, "status", side_effect=[psutil.STATUS_RUNNING, status]):
                if status == psutil.STATUS_ZOMBIE or isinstance(status, psutil.NoSuchProcess):
                    self.assertIsNone(capture(os.getpid()))
                else:
                    with self.assertRaises(GatewayError) as error:
                        capture(os.getpid())
                    self.assertEqual("UNKNOWN", error.exception.code)

    def test_stale_descendant_snapshot_cannot_claim_a_reused_pid(self):
        def record(pid, ppid, sid=10):
            return {"pid": pid, "ppid": ppid, "uid": os.getuid(), "sid": sid,
                    "start_fingerprint": {"kind": "fixture", "value": str(pid), "boot": "fixture"}}
        records = {10: record(10, 1), 11: record(11, 900), 12: record(12, 11),
                   13: record(13, 10), 14: record(14, 13, sid=14)}
        with patch("hermes_gateway_herdr.identity.capture", side_effect=records.get), \
                patch("hermes_gateway_herdr.identity.psutil.Process") as process:
            # PID 11 used to be a child; its replacement belongs to an unrelated parent.
            # Return the real grandchild before its parent to also exercise recursive discovery.
            process.return_value.children.return_value = [Mock(pid=14), Mock(pid=11), Mock(pid=12), Mock(pid=13)]
            self.assertEqual({13, 14}, {item["pid"] for item in descendants(records[10])})
