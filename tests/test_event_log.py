from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from hermes_gateway_herdr.event_log import EventLog


class LogTests(unittest.TestCase):
    def test_default_retention_counts_include_the_active_file(self):
        original = EventLog._append
        def small_files(writer, name, data, limit, backups):
            original(writer, name, data, 2 * len(data), backups)
        with tempfile.TemporaryDirectory() as root, patch.object(EventLog, "_append", small_files):
            directory = Path(root) / "logs"
            log = EventLog(directory)
            for _ in range(30):
                log.event("child_exit", code=75)
                log.raw(b"fixture\n")
            log.close()
            self.assertFalse(log.worker.is_alive())
            self.assertEqual(5, len(list(directory.glob("events.jsonl*"))))
            self.assertEqual(3, len(list(directory.glob("gateway-output.log*"))))

    def test_slow_disk_has_bounded_queue_and_does_not_block_producer(self):
        with tempfile.TemporaryDirectory() as root:
            blocked, release = threading.Event(), threading.Event()
            def slow(*_):
                blocked.set()
                release.wait(2)
            with patch.object(EventLog, "_append", slow):
                log = EventLog(Path(root) / "logs", capacity=2)
                try:
                    log.raw(b"start")
                    self.assertTrue(blocked.wait(1))
                    started = time.monotonic()
                    for _ in range(1000):
                        log.raw(b"x" * 20000)
                    self.assertLess(time.monotonic() - started, 1)
                    self.assertLessEqual(log.queue.qsize(), 2)
                    self.assertGreater(log.dropped, 0)
                    log.close()
                finally:
                    release.set()
                    log.worker.join(2)
                self.assertFalse(log.worker.is_alive())

    def test_rotation_bounds_permissions_and_separates_raw_output(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "logs"
            log = EventLog(directory)
            log.close()
            for _ in range(12):
                log._append("gateway-output.log", b"FAKE_SECRET\n", 22, 2)
            log._append("events.jsonl", b'{"event":"child_exit","code":75}\n', 100, 2)
            self.assertEqual(4, len(list(directory.iterdir())))
            for path in directory.glob("gateway-output.log*"):
                self.assertLessEqual(path.stat().st_size, 22)
                self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertNotIn("FAKE_SECRET", (directory / "events.jsonl").read_text())
            external = Path(root) / "external"
            external.write_text("untouched")
            (directory / "events.jsonl").unlink()
            (directory / "events.jsonl").symlink_to(external)
            with self.assertRaises(Exception):
                log._append("events.jsonl", b"bad", 100, 2)
            self.assertEqual("untouched", external.read_text())
