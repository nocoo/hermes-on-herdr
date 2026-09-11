import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading

import yaml

from hermes_gateway_herdr.config import Config

ROOT = Path(__file__).resolve().parents[1]


def private_file(path: Path, value: str) -> None:
    path.write_text(value)
    path.chmod(0o600)


class Fixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hgh-", dir="/tmp")
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / "profiles" / "herdr-control"
        self.profile.mkdir(parents=True, mode=0o700)
        self.config_dir = self.root / "config"
        self.config_dir.mkdir(mode=0o700)
        executable = self.root / "never-run-upstream"
        executable.write_text("#!/bin/sh\nexit 99\n")
        executable.chmod(0o700)
        self.config = Config("herdr-control", self.profile, self.root / "herdr.sock", "fixture",
                             Path(sys.executable), executable, self.root, executable, self.root, ROOT,
                             ("telegram",), self.config_dir)
        self.profile_data = {
            "model": {"provider": "fixture", "default": "fixture-model"},
            "terminal": {"backend": "local", "home_mode": "profile", "cwd": str(self.root),
                         "auto_source_bashrc": False, "shell_init_files": []},
            "plugins": {"enabled": []}, "gateway": {"multiplex_profiles": False},
            "nous": {"keepalive_interval_seconds": 0},
            "platform_toolsets": {"telegram": ["terminal", "skills", "memory"]},
            "agent": {"disabled_toolsets": ["cronjob", "browser", "file"]},
        }
        self.write_profile()
        private_file(self.profile / ".env", "# No real credentials\n")
        self.write_config()

    def write_config(self):
        value = {"schema": 1}
        for key in Config.__dataclass_fields__:
            if key != "config_dir":
                item = getattr(self.config, key)
                value[key] = str(item) if isinstance(item, Path) else list(item) if isinstance(item, tuple) else item
        private_file(self.config_dir / "config.json", json.dumps(value))
        private_file(self.config_dir / "runtime-python", str(self.config.python_bin) + "\n")

    def write_profile(self):
        private_file(self.profile / "config.yaml", yaml.safe_dump(self.profile_data))

    def context(self, generation="generation"):
        return {"HERDR_SOCKET_PATH": str(self.config.owner_socket), "HERDR_WORKSPACE_ID": "w-fixture",
                "HERDR_TAB_ID": "tab-fixture", "HERDR_PANE_ID": "pane-fixture",
                "HGH_OWNER_KEY": self.config.key, "HGH_GENERATION": generation,
                "HOME": str(Path.home()), "TERM": "xterm-256color"}

    def close(self):
        self.temp.cleanup()


class SocketServer:
    """A local protocol fixture. It never executes request argv or calls an upstream CLI."""

    def __init__(self, path, handler):
        self.path, self.handler = Path(path), handler
        self.requests, self.errors, self.clients = [], [], []
        self.stop = threading.Event()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(path))
        self.path.chmod(0o600)
        self.socket.listen(128)
        self.socket.settimeout(0.05)
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    def _accept(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.socket.accept()
            except (TimeoutError, OSError):
                continue
            thread = threading.Thread(target=self._reply, args=(connection,), daemon=True)
            self.clients.append(thread)
            thread.start()

    def _reply(self, connection):
        try:
            with connection:
                connection.settimeout(1)
                raw = bytearray()
                while b"\n" not in raw:
                    chunk = connection.recv(4096)
                    if not chunk:
                        return
                    raw.extend(chunk)
                    if len(raw) > 16 * 1024:
                        return
                request = json.loads(bytes(raw).split(b"\n")[0])
                self.requests.append(request)
                result = self.handler(request)
                if result is not None:
                    connection.sendall(result if isinstance(result, bytes) else json.dumps(result).encode() + b"\n")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as exc:
            self.errors.append(exc)

    def close(self):
        self.stop.set()
        self.socket.close()
        self.thread.join(timeout=3)
        for thread in self.clients:
            thread.join(timeout=3)
        self.path.unlink(missing_ok=True)
        if self.errors:
            raise AssertionError(self.errors)
