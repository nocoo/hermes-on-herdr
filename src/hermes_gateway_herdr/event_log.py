"""A bounded best-effort log queue. Slow disks never backpressure the Gateway pipes."""

import json
import os
from pathlib import Path
import queue
import threading
import time

from .state import check_private


class EventLog:
    def __init__(self, directory: Path, *, capacity: int = 128):
        directory.mkdir(mode=0o700, exist_ok=True)
        check_private(directory.lstat(), directory=True)
        self.directory = directory
        self.queue = queue.Queue(maxsize=capacity)
        self.dropped = 0
        self.worker = threading.Thread(target=self._run, daemon=True, name="gateway-log-writer")
        self.worker.start()

    def _put(self, item):
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            self.dropped += 1

    def event(self, name: str, **fields):
        # Callers supply only lifecycle metadata; raw adapter errors never enter this stream.
        payload = dict(time=time.time(), event=name, **fields)
        self._put(("events.jsonl", (json.dumps(payload, allow_nan=False) + "\n").encode(), 5 * 1024 * 1024, 4))

    def raw(self, data: bytes):
        self._put(("gateway-output.log", data[:16384], 10 * 1024 * 1024, 2))

    def _append(self, name: str, data: bytes, limit: int, backups: int):
        path = self.directory / name
        if path.exists() or path.is_symlink():
            check_private(path.lstat())
            if path.stat().st_size + len(data) > limit:
                for index in range(backups, 0, -1):
                    source = self.directory / (name if index == 1 else f"{name}.{index - 1}")
                    target = self.directory / f"{name}.{index}"
                    if target.exists() or target.is_symlink():
                        check_private(target.lstat())
                    if source.exists() or source.is_symlink():
                        check_private(source.lstat())
                        os.replace(source, target)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, "ab") as stream:
            check_private(os.fstat(stream.fileno()))
            stream.write(data)

    def _run(self):
        while True:
            item = self.queue.get()
            if item is None:
                return
            try:
                self._append(*item)
            except Exception:
                self.dropped += 1

    def close(self):
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            # Free one slot for the stop marker without ever waiting on disk I/O.
            try:
                self.queue.get_nowait()
                self.dropped += 1
            except queue.Empty:
                pass
            self.queue.put_nowait(None)
        self.worker.join(timeout=0.2)
