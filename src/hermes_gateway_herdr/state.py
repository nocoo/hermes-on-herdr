"""Private JSON state and fixed-inode flock leases (POSIX hosts only)."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import time
import uuid

from .errors import GatewayError

SCHEMA = 1
CONTROL_DIR = ".herdr-gateway-herdr"
DATA_FILES = frozenset({"binding.json", "intent.json", "pending.json", "runtime.json", "fuse.json"})
MAX_STATE_BYTES = 256 * 1024


def check_private(st: os.stat_result, *, directory: bool = False, allow_unlinked: bool = False) -> None:
    expected = 0o700 if directory else 0o600
    right_type = stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)
    if (not right_type or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != expected
            or (not directory and st.st_nlink not in ({0, 1} if allow_unlinked else {1}))):
        raise GatewayError("UNSAFE_PATH", "Expected a private, current-user-owned resource")


def validate_state(name: str, value: object) -> dict:
    if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != SCHEMA:
        raise GatewayError("STATE_SCHEMA", "Unsupported or damaged state schema")
    if name == "intent.json":
        if (type(value.get("revision")) is not int or value["revision"] < 0
                or value.get("desired") not in {"running", "paused"}
                or not isinstance(value.get("binding_id"), str)
                or type(value.get("reset_revision", 0)) is not int
                or not 0 <= value.get("reset_revision", 0) <= value["revision"]):
            raise GatewayError("STATE_SCHEMA", "Invalid persistent intent")
        history = value.get("requests", [])
        if (not isinstance(history, list) or len(history) > 64
                or any(not isinstance(item, dict) or not isinstance(item.get("id"), str)
                       or item.get("action") not in {"start", "resume", "stop", "pause", "restart"}
                       for item in history)):
            raise GatewayError("STATE_SCHEMA", "Invalid request history")
    if name in {"pending.json", "runtime.json"}:
        if not all(isinstance(value.get(key), str) and value[key]
                   for key in ("generation", "owner_key")):
            raise GatewayError("STATE_SCHEMA", "Missing ownership identity")
    if name == "fuse.json":
        if (type(value.get("fused")) is not bool
                or not isinstance(value.get("failures"), list)
                or not isinstance(value.get("restarts"), list)
                or type(value.get("streak", 0)) is not int or value.get("streak", 0) < 0
                or type(value.get("reset_revision", 0)) is not int or value.get("reset_revision", 0) < 0):
            raise GatewayError("STATE_SCHEMA", "Invalid retry budget")
        for stamp in value["failures"] + value["restarts"]:
            if type(stamp) not in (int, float) or not 0 <= stamp < float("inf"):
                raise GatewayError("STATE_SCHEMA", "Invalid retry timestamp")
    return value


class Lease:
    def __init__(self, fd: int):
        self.fd = fd

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            check_private(os.fstat(self.fd), directory=True)
        except (OSError, GatewayError) as exc:
            if hasattr(self, "fd"):
                os.close(self.fd)
            if isinstance(exc, GatewayError):
                raise
            raise GatewayError("SETUP_REQUIRED", "Private control directory is unavailable") from exc
        self._mutation_fd = None

    @classmethod
    def initialize(cls, path: Path, binding: dict):
        """Explicit setup only. A repeat setup never clears a pause or a fuse."""
        path = Path(path)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        store = cls(path)
        try:
            with store.mutation():
                old = store.read("binding.json")
                if old is not None:
                    if old != binding:
                        raise GatewayError("OWNERSHIP_CONFLICT", "Control directory is already bound")
                    store.read("intent.json", required=True)
                    return store
                # A partial/foreign installation must not silently gain new authority.
                if any(store.read(name) is not None for name in DATA_FILES - {"binding.json"}):
                    raise GatewayError("OWNERSHIP_CONFLICT", "Unbound state requires inspection")
                store.write("binding.json", binding)
                store.write("intent.json", {
                    "schema": SCHEMA, "binding_id": binding["binding_id"], "revision": 0,
                    "desired": "paused", "action": "pause", "request_id": str(uuid.uuid4()),
                    "reason": "initial_setup", "updated_at": time.time(), "maintenance_until": None,
                })
            return store
        except BaseException:
            store.close()
            raise

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _open(self, name: str, flags: int) -> int:
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
        try:
            # A reader may open the old inode immediately before an atomic replacement.
            # Its nlink then becomes zero; the opened, private snapshot is still valid.
            check_private(os.fstat(fd), allow_unlinked=name in DATA_FILES and flags & os.O_ACCMODE == os.O_RDONLY)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def lease(self, name: str = "supervisor.lock", timeout: float = 0, *, create: bool = True) -> Lease:
        if name not in {"mutation.lock", "supervisor.lock"}:
            raise ValueError("Unknown lock")
        try:
            fd = self._open(name, os.O_RDWR | (os.O_CREAT if create else 0))
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    actual = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
                    opened = os.fstat(fd)
                    if (actual.st_dev, actual.st_ino) != (opened.st_dev, opened.st_ino):
                        raise GatewayError("UNSAFE_PATH", "Lock inode changed")
                    return Lease(fd)
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise GatewayError("BUSY", "An owner holds the lock")
                    time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        except BaseException as exc:
            if "fd" in locals():
                os.close(fd)
            if isinstance(exc, FileNotFoundError) and not create:
                raise
            if isinstance(exc, OSError):
                raise GatewayError("IO_ERROR", "Cannot acquire ownership lock") from exc
            raise

    @contextmanager
    def mutation(self, timeout: float = 0.25):
        if self._mutation_fd is not None:
            raise RuntimeError("Mutation transactions must not be nested")
        with self.lease("mutation.lock", timeout) as lease:
            self._mutation_fd = lease.fd
            try:
                yield self
            finally:
                self._mutation_fd = None

    def lifetime_held(self) -> bool:
        try:
            with self.lease(create=False):
                return False
        except FileNotFoundError:
            return False
        except GatewayError as exc:
            if exc.code == "BUSY":
                return True
            raise

    def read(self, name: str, *, required: bool = False) -> dict | None:
        if name not in DATA_FILES:
            raise ValueError("Unknown state file")
        try:
            fd = self._open(name, os.O_RDONLY)
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(MAX_STATE_BYTES + 1)
            if len(raw) > MAX_STATE_BYTES:
                raise GatewayError("STATE_SCHEMA", "State exceeds the size limit")
            return validate_state(name, json.loads(raw))
        except FileNotFoundError as exc:
            if required:
                raise GatewayError("SETUP_REQUIRED", "Required state is missing") from exc
            return None
        except (ValueError, UnicodeDecodeError) as exc:
            raise GatewayError("STATE_SCHEMA", "Cannot decode persistent state") from exc
        except OSError as exc:
            raise GatewayError("UNSAFE_PATH", "Cannot safely read persistent state") from exc

    def write(self, name: str, value: dict) -> None:
        if self._mutation_fd is None:
            raise RuntimeError("State mutation requires mutation.lock")
        if name not in DATA_FILES:
            raise ValueError("Unknown state file")
        validate_state(name, value)
        raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode()
        if len(raw) > MAX_STATE_BYTES:
            raise GatewayError("STATE_SCHEMA", "State exceeds the size limit")
        self.read(name)  # Reject symlinks, foreign files and future schemas before replacing.
        temporary = f".{name}.{uuid.uuid4().hex}"
        try:
            fd = self._open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        except OSError as exc:
            raise GatewayError("IO_ERROR", "Persistent state could not be committed") from exc
        finally:
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def remove(self, name: str) -> None:
        if self._mutation_fd is None:
            raise RuntimeError("State mutation requires mutation.lock")
        if name not in {"pending.json", "runtime.json"}:
            raise ValueError("Durable intent, binding, fuse and locks must be preserved")
        if self.read(name) is not None:
            try:
                os.unlink(name, dir_fd=self.fd)
                os.fsync(self.fd)
            except OSError as exc:
                raise GatewayError("IO_ERROR", "State removal was not committed") from exc

    def intent(self) -> dict:
        intent = self.read("intent.json", required=True)
        binding = self.read("binding.json", required=True)
        if intent["binding_id"] != binding.get("binding_id"):
            raise GatewayError("OWNERSHIP_CONFLICT", "Intent belongs to another installation")
        return intent

    def set_intent(self, action: str, *, request_id: str | None = None, reason: str | None = None,
                   expected_revision: int | None = None) -> dict:
        if action not in {"start", "resume", "stop", "pause", "restart"}:
            raise ValueError("Unknown action")
        current = self.intent()
        history = current.get("requests", [])
        prior = history + [{"id": current.get("request_id"), "action": current.get("action")}]
        if request_id:
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 160:
                raise GatewayError("STALE_REQUEST", "Invalid request id")
            for item in prior:
                if item["id"] == request_id:
                    if item["action"] != action:
                        raise GatewayError("STALE_REQUEST", "Request id was used for a different action")
                    return current  # Never replay an old Resume over a newer Pause.
        if expected_revision is not None and expected_revision != current["revision"]:
            raise GatewayError("STALE_REQUEST", "Intent revision changed")
        if action == "restart" and current["desired"] != "running":
            raise GatewayError("PAUSED", "Resume explicitly before restarting")
        updated = dict(current, revision=current["revision"] + 1, action=action,
                       desired="paused" if action in {"stop", "pause"} else "running",
                       request_id=request_id or str(uuid.uuid4()), reason=reason or f"operator_{action}",
                       updated_at=time.time(), maintenance_until=None)
        updated["requests"] = (history + [{"id": updated["request_id"], "action": action}])[-64:]
        if action in {"start", "resume"}:
            # One durable write both resumes and authorizes a budget reset. No cross-file transaction.
            updated["reset_revision"] = updated["revision"]
        self.write("intent.json", updated)
        return updated
