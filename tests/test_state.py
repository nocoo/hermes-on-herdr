import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.state import Store

SRC = str(Path(__file__).resolve().parents[1] / "src")


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state"
        self.binding = {"schema": 1, "binding_id": "test-binding", "owner_key": "owner"}
        self.store = Store.initialize(self.path, self.binding)
        self.addCleanup(self.store.close)

    def test_repeat_setup_and_restart_preserve_pause(self):
        with self.store.mutation():
            self.store.set_intent("resume")
            stopped = self.store.set_intent("pause", request_id="pause-once")
            self.assertEqual(stopped, self.store.set_intent("pause", request_id="pause-once"))
            with self.assertRaises(GatewayError) as error:
                self.store.set_intent("restart")
            self.assertEqual(error.exception.code, "PAUSED")
        with Store.initialize(self.path, self.binding) as reopened:
            self.assertEqual(stopped, reopened.intent())

    def test_lock_excludes_other_process_and_survives_json_replacement(self):
        probe = """
import sys
sys.path.insert(0, sys.argv[1])
from hermes_gateway_herdr.state import Store
from hermes_gateway_herdr.errors import GatewayError
with Store(sys.argv[2]) as store:
    try:
        with store.lease(): pass
    except GatewayError as error:
        print(error.code)
    else:
        print('ACQUIRED')
"""
        with self.store.lease():
            inode = (self.path / "supervisor.lock").stat().st_ino
            with self.store.mutation():
                self.store.set_intent("resume")
            result = subprocess.run([sys.executable, "-I", "-B", "-c", probe, SRC, str(self.path)],
                                    capture_output=True, text=True, timeout=10, check=True)
            self.assertEqual(result.stdout.strip(), "BUSY")
            self.assertEqual(inode, (self.path / "supervisor.lock").stat().st_ino)
        with self.store.lease():
            self.assertEqual(inode, (self.path / "supervisor.lock").stat().st_ino)

    def test_child_exec_does_not_keep_lifetime_lock_alive(self):
        lease = self.store.lease()
        child = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import sys; sys.stdin.read()"],
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, close_fds=False)
        try:
            lease.close()
            with self.store.lease():
                self.assertIsNone(child.poll())
        finally:
            lease.close()
            child.communicate(timeout=10)

    def test_fsync_failure_does_not_ack_or_overwrite_old_intent(self):
        before = self.store.intent()
        with self.store.mutation(), patch("hermes_gateway_herdr.state.os.fsync", side_effect=OSError("full")):
            with self.assertRaises(GatewayError) as error:
                self.store.set_intent("resume")
            self.assertEqual(error.exception.code, "IO_ERROR")
        self.assertEqual(before, self.store.intent())
        self.assertEqual([], list(self.path.glob(".intent.json.*")))

    def test_corrupt_or_future_intent_is_not_replaced(self):
        path = self.path / "intent.json"
        for raw in ('{"schema":', '{"schema":999}', '{"schema":1,"revision":true,"desired":"running"}',
                    '{"schema":999,"schema":1}', '{"schema":1,"revision":1e999}'):
            path.write_text(raw)
            with self.store.mutation(), self.assertRaises(GatewayError):
                self.store.set_intent("pause")
            self.assertEqual(raw, path.read_text())

    def test_malformed_intent_enums_cannot_be_acknowledged_or_replaced(self):
        path = self.path / "intent.json"
        original = self.store.intent()
        for fields in ({"desired": []}, {"desired": {}},
                       {"requests": [{"id": "fixture", "action": []}]},
                       {"requests": [{"id": "fixture", "action": {}}]}):
            with self.subTest(fields=fields):
                raw = json.dumps(dict(original, **fields))
                path.write_text(raw)
                inode = path.stat().st_ino
                with self.store.mutation(), self.assertRaises(GatewayError) as error:
                    self.store.set_intent("pause")
                self.assertEqual("STATE_SCHEMA", error.exception.code)
                self.assertEqual(raw, path.read_text())
                self.assertEqual(inode, path.stat().st_ino)

    def test_malformed_pending_ticket_is_preserved_for_inspection(self):
        path = self.path / "pending.json"
        original = {"schema": 1, "generation": "fixture", "owner_key": "owner",
                    "intent_revision": 1, "phase": "pane_requested"}
        for fields in ({"phase": []}, {"phase": {}}, {"phase": "future"},
                       {"intent_revision": True}, {"intent_revision": -1}):
            with self.subTest(fields=fields):
                raw = json.dumps(dict(original, **fields))
                path.write_text(raw)
                path.chmod(0o600)
                with self.assertRaises(GatewayError) as error:
                    self.store.read("pending.json")
                self.assertEqual("STATE_SCHEMA", error.exception.code)
                with self.store.mutation(), self.assertRaises(GatewayError):
                    self.store.remove("pending.json")
                self.assertEqual(raw, path.read_text())

    def test_replace_failure_preserves_old_intent_and_removes_the_temporary_file(self):
        before = self.store.intent()
        inode = (self.path / "intent.json").stat().st_ino
        with self.store.mutation(), patch("hermes_gateway_herdr.state.os.replace", side_effect=OSError("fixture failure")):
            with self.assertRaises(GatewayError) as error:
                self.store.set_intent("resume")
            self.assertEqual("IO_ERROR", error.exception.code)
        self.assertEqual(before, self.store.intent())
        self.assertEqual(inode, (self.path / "intent.json").stat().st_ino)
        self.assertEqual([], list(self.path.glob(".intent.json.*")))

    def test_symlink_and_hardlink_are_rejected_without_touching_target(self):
        target = Path(self.temp.name) / "target"
        target.write_text(json.dumps(self.store.intent()))
        target.chmod(0o600)
        path = self.path / "intent.json"
        path.unlink()
        path.symlink_to(target)
        with self.store.mutation(), self.assertRaises(GatewayError):
            self.store.set_intent("resume")
        path.unlink()
        os.link(target, path)
        with self.assertRaises(GatewayError):
            self.store.intent()
        self.assertEqual("paused", json.loads(target.read_text())["desired"])

    def test_mutations_need_lock_and_cannot_delete_tombstone(self):
        with self.assertRaises(RuntimeError):
            self.store.set_intent("resume")
        with self.store.mutation(), self.assertRaises(ValueError):
            self.store.remove("intent.json")

    def test_old_request_and_compare_and_swap_cannot_overwrite_newer_pause(self):
        with self.store.mutation():
            self.store.set_intent("resume", request_id="old", expected_revision=0)
            pause = self.store.set_intent("pause")
            self.assertEqual(pause, self.store.set_intent("resume", request_id="old", expected_revision=0))
            with self.assertRaises(GatewayError) as error:
                self.store.set_intent("resume", request_id="new", expected_revision=1)
            self.assertEqual("STALE_REQUEST", error.exception.code)
            self.assertEqual(pause, self.store.intent())

    def test_atomic_replace_between_open_and_fstat_keeps_reader_snapshot_valid(self):
        old = self.store.intent()
        replacement = self.path / "replacement"
        replacement.write_text(json.dumps(dict(old, revision=old["revision"] + 1)))
        replacement.chmod(0o600)
        original_open = os.open
        def racing_open(name, flags, *args, **kwargs):
            fd = original_open(name, flags, *args, **kwargs)
            if name == "intent.json" and replacement.exists():
                os.replace(replacement, self.path / "intent.json")
            return fd
        with patch("hermes_gateway_herdr.state.os.open", side_effect=racing_open):
            self.assertEqual(old, self.store.intent())
        self.assertEqual(old["revision"] + 1, self.store.intent()["revision"])

    def test_atomic_replace_during_path_stat_does_not_reject_a_private_data_snapshot(self):
        old = self.store.intent()
        new = dict(old, revision=old["revision"] + 1)
        replacement = self.path / "replacement"
        replacement.write_text(json.dumps(new))
        replacement.chmod(0o600)
        original_stat = os.stat
        def racing_stat(name, *args, **kwargs):
            if name == "intent.json":
                # A kernel path lookup can retain the old inode while rename
                # removes its last link, before stat returns to the caller.
                fd = os.open(self.path / "intent.json", os.O_RDONLY)
                try:
                    os.replace(replacement, self.path / "intent.json")
                    info = os.fstat(fd)
                    self.assertEqual(0, info.st_nlink)
                    return info
                finally:
                    os.close(fd)
            return original_stat(name, *args, **kwargs)
        with patch("hermes_gateway_herdr.state.os.stat", side_effect=racing_stat):
            self.assertEqual(new, self.store.intent())
