"""An optional, isolated TTY companion. Its failures never enter the Gateway loop."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import termios

RESTORE = b"\x1b[0m\x1b[?1004l\x1b[?2004l\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?25h\x1b[?1049l"


def restore_terminal(mode, *, failed=False):
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, mode)
    except (OSError, ValueError, termios.error):
        pass
    # Never wait for a terminal reader, including after a renderer dies mid-write.
    fd = None
    try:
        fd = os.open(os.ttyname(sys.stdout.fileno()), os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
        message = b"\r\nDashboard unavailable. Gateway supervision continues; use Herdr Status/Logs.\r\n" if failed else b""
        os.write(fd, RESTORE + message)
    except (OSError, ValueError):
        pass
    finally:
        if fd is not None:
            os.close(fd)


class Display:
    def __init__(self, process, lifetime, mode):
        self.process, self.lifetime, self.mode = process, lifetime, mode
        self.closed = False

    @classmethod
    def start(cls, config, env):
        parent = child = None
        try:
            if env.get("HGH_DASHBOARD") == "0" or env.get("TERM") == "dumb" or not (sys.stdin.isatty() and sys.stdout.isatty()):
                return None
            mode = termios.tcgetattr(sys.stdin.fileno())
            parent, child = socket.socketpair()
            parent.setblocking(False)
            child.setblocking(False)
            entry = Path(__file__).with_name("__main__.py")
            # No profile credentials or arbitrary user environment are needed by the monitor.
            allowed = {"HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "COLORTERM",
                       "NO_COLOR", "SSH_CONNECTION", "SSH_TTY", "TERM_PROGRAM"}
            child_env = {key: value for key, value in env.items() if key in allowed}
            process = subprocess.Popen([str(config.python_bin), "-I", "-B", str(entry), "--config",
                                        str(config.config_dir / "config.json"), "dashboard", "--parent-fd", str(child.fileno())],
                                       env=child_env, pass_fds=(child.fileno(),), close_fds=True, stderr=subprocess.DEVNULL,
                                       start_new_session=False)
            return cls(process, parent, mode)
        except Exception:
            if parent is not None:
                parent.close()
            return None
        finally:
            if child is not None:
                child.close()

    def poll(self):
        if self.closed:
            return False
        if self.process.poll() is not None:
            self.close(failed=True)
            return False
        try:
            request = self.lifetime.recv(64)
        except BlockingIOError:
            return False
        if not request:
            self.close(failed=True)
            return False
        # Only this direct child holds the other endpoint. No parent PID lookup or signals.
        return b"p" in request

    def close(self, *, failed=False):
        if self.closed:
            return
        self.closed = True
        # Popen owns an unreaped direct child; no PID search or process-group signaling.
        try:
            self.lifetime.close()
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=0.3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=0.3)
        finally:
            restore_terminal(self.mode, failed=failed)
