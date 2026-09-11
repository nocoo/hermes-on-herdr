"""The pane process owns one foreground Gateway and keeps all waits bounded."""

import json
import os
import queue
import random
import selectors
import signal
import socket
import subprocess
import threading
import time
import uuid

from .config import Config, ID_PATTERN, preflight
from .errors import GatewayError
from .event_log import EventLog
from .identity import capture, descendants, public_identity, same_process, signal_verified
from .lifecycle import Limits, effective_budget, empty_budget, exit_action, retry_budget
from .rpc import GatewayProbe, Herdr, check_peer, check_socket, decode_object, profile_in_use, supervisor_socket
from .state import Store, check_private


class Supervisor:
    def __init__(self, config: Config, env: dict, *, limits: Limits = Limits(),
                 launch=subprocess.Popen, check=preflight, herdr=None, probe=None):
        self.config, self.env, self.limits = config, dict(env), limits
        self.launch, self.check = launch, check
        self.herdr = herdr or Herdr(config, timeout=limits.rpc)
        self.probe = probe or GatewayProbe(config, interval=limits.ready_spacing, timeout=limits.rpc)
        self.selector = selectors.DefaultSelector()
        self.clients = {}
        self.listener = self.socket_inode = self.store = self.lease = self.log = None
        self.created_socket_dir = False
        self.identity = capture(os.getpid())
        self.generation = env.get("HGH_GENERATION", "")
        self.nonce = uuid.uuid4().hex
        self.path = supervisor_socket(config)
        self.runtime = None
        self.child = self.child_identity = None
        self.owned = {}
        self.termination = None
        self.sent = set()
        self.exit_code = None
        self.child_revision = self.restart_revision = 0
        self.shutdown = False
        self.signal_received = None
        self.results = queue.Queue(maxsize=1)
        self.worker = None
        self.next_probe = self.next_track = self.retry_at = 0
        self.owner_lost = self.ready_since = None
        self.outcome = 0

    def _validate_ticket(self):
        self.config.check_binding(self.store.read("binding.json", required=True))
        intent = self.store.intent()
        pending = self.store.read("pending.json", required=True)
        if (pending["owner_key"] != self.config.key or pending["generation"] != self.generation
                or pending.get("phase") not in {"pane_requested", "pane_known"}
                or pending.get("intent_revision") != intent["revision"] or intent["desired"] != "running"
                or effective_budget(intent, self.store.read("fuse.json"))["fused"]):
            raise GatewayError("STALE_REQUEST", "Pane launch ticket has been revoked")
        return intent

    def _open_socket(self):
        try:
            self.path.parent.mkdir(mode=0o700)
            self.created_socket_dir = True
        except FileExistsError:
            pass
        check_private(self.path.parent.lstat(), directory=True)
        if self.path.exists() or self.path.is_symlink():
            check_socket(self.path)
            previous = self.path.lstat()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as candidate:
                candidate.settimeout(self.limits.rpc)
                try:
                    candidate.connect(str(self.path))
                except (ConnectionRefusedError, FileNotFoundError):
                    current = self.path.lstat()
                    if (current.st_dev, current.st_ino) != (previous.st_dev, previous.st_ino):
                        raise GatewayError("UNKNOWN", "Supervisor socket changed")
                    self.path.unlink()
                except OSError as exc:
                    raise GatewayError("UNKNOWN", "Existing supervisor socket is not verifiable") from exc
                else:
                    raise GatewayError("UNKNOWN", "Another process answers the supervisor socket")
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(self.path))
        self.path.chmod(0o600)
        info = self.path.lstat()
        self.socket_inode = (info.st_dev, info.st_ino)
        self.listener.listen(32)
        self.listener.setblocking(False)
        self.selector.register(self.listener, selectors.EVENT_READ, "listen")

    def _claim(self):
        context = self.config.check_context(self.env, pane=True)
        if self.env.get("HGH_OWNER_KEY") != self.config.key or not ID_PATTERN.fullmatch(self.generation):
            raise GatewayError("INVALID_IDENTITY", "Supervisor requires a current pane ticket")
        self.store = Store(self.config.state_dir)
        self.lease = self.store.lease()
        with self.store.mutation():
            self._validate_ticket()
            old = self.store.read("runtime.json")
            if old:
                if old.get("spawn_pending"):
                    raise GatewayError("UNKNOWN", "An earlier spawn has an unknown result")
                for key in ("supervisor", "gateway"):
                    if old.get(key) and same_process(old[key]):
                        raise GatewayError("UNKNOWN", "An older runtime is still alive")
                if any(same_process(record) for record in old.get("descendants", [])):
                    raise GatewayError("UNKNOWN", "Older Gateway tasks are still alive")
        pane = {key: context[f"HERDR_{key.upper()}"] for key in ("workspace_id", "tab_id", "pane_id")}
        self.herdr.deadline = time.monotonic() + self.limits.r0
        self.herdr.available()
        if not self.herdr.enabled():
            raise GatewayError("DISABLED", "Plugin is disabled or unlinked")
        pane = self.herdr.membership(pane, self.identity)
        self._open_socket()
        with self.store.mutation():
            intent = self._validate_ticket()
            self.runtime = {
                "schema": 1, "owner_key": self.config.key, "generation": self.generation,
                "instance_nonce": self.nonce, "applied_revision": intent["revision"], "state": "STARTING",
                "pane": pane, "supervisor": self.identity, "gateway": None, "descendants": [],
                "last_probe": None, "last_exit": None, "retry_at": None, "ownership_source": "created",
                "spawn_pending": False,
            }
            self._persist()
            self.store.remove("pending.json")
        self.log = EventLog(self.config.state_dir / "logs")
        self.log.event("supervisor_started", generation=self.generation, pid=self.identity["pid"])

    def _persist(self):
        self.runtime["updated_at"] = time.time()
        self.store.write("runtime.json", self.runtime)

    def _save(self, **fields):
        with self.store.mutation():
            current = self.store.read("runtime.json", required=True)
            if current.get("instance_nonce") != self.nonce:
                raise GatewayError("OWNERSHIP_CONFLICT", "Runtime ownership changed")
            # Preserve a controller's verified handoff adoption marker.
            self.runtime["ownership_source"] = current.get("ownership_source", "created")
            self.runtime.update(fields)
            self._persist()

    def public_status(self):
        intent = self.store.intent()
        budget = effective_budget(intent, self.store.read("fuse.json"))
        return {
            "schema": 1, "kind": "hermes-gateway-herdr", "owner_key": self.config.key,
            "generation": self.generation, "instance_nonce": self.nonce, "pane": self.runtime["pane"],
            "supervisor": public_identity(self.identity), "gateway": public_identity(self.child_identity),
            "state": self.runtime["state"], "desired": intent["desired"], "intent_revision": intent["revision"],
            "applied_revision": self.runtime["applied_revision"], "fused": budget["fused"],
            "reason": budget.get("reason"), "last_exit": self.runtime.get("last_exit"),
            "last_probe": self.runtime.get("last_probe"), "recovery": "next_owner_event",
            "dropped_log_chunks": self.log.dropped if self.log else 0,
        }

    def _request(self, request):
        if (type(request.get("protocol")) is not int or request["protocol"] != 1
                or not isinstance(request.get("id"), str) or not 1 <= len(request["id"]) <= 160):
            raise GatewayError("PROTOCOL_ERROR")
        verb = request.get("verb")
        if verb not in {"identify", "status", "stop", "restart"}:
            raise GatewayError("UNSUPPORTED_VERB")
        allowed = {"protocol", "id", "verb"}
        if verb in {"stop", "restart"}:
            allowed |= {"owner_key", "generation", "intent_revision"}
            intent = self.store.intent()
            if (request.get("owner_key") != self.config.key or request.get("generation") != self.generation
                    or type(request.get("intent_revision")) is not int
                    or request["intent_revision"] != intent["revision"] or request["id"] != intent["request_id"]
                    or (verb == "stop" and intent["desired"] != "paused")
                    or (verb == "restart" and (intent["desired"] != "running" or intent["action"] != "restart"))):
                raise GatewayError("STALE_REQUEST")
        if set(request) - allowed:
            raise GatewayError("PROTOCOL_ERROR")
        if verb in {"identify", "status"}:
            return self.public_status()
        # The main loop observes durable intent independently of this ACK. There is no second signal path.
        return {"accepted": True, "intent_revision": intent["revision"]}

    def _close_client(self, connection):
        self.clients.pop(connection, None)
        try:
            self.selector.unregister(connection)
        except KeyError:
            pass
        connection.close()

    def _io(self, timeout):
        for key, mask in self.selector.select(timeout):
            if key.data == "listen":
                connection, _ = self.listener.accept()
                if len(self.clients) >= 32:
                    connection.close()
                    continue
                try:
                    check_peer(connection)
                except GatewayError:
                    connection.close()
                    continue
                connection.setblocking(False)
                self.clients[connection] = {"input": bytearray(), "output": b"",
                                            "deadline": time.monotonic() + self.limits.rpc}
                self.selector.register(connection, selectors.EVENT_READ, "client")
            elif key.data == "pipe":
                try:
                    data = os.read(key.fd, 16384)
                except BlockingIOError:
                    continue
                if data:
                    self.log.raw(data)
                else:
                    self.selector.unregister(key.fileobj)
                    key.fileobj.close()
            else:
                connection, state = key.fileobj, self.clients[key.fileobj]
                try:
                    if mask & selectors.EVENT_READ:
                        chunk = connection.recv(16385 - len(state["input"]))
                        state["input"].extend(chunk)
                        if not chunk or len(state["input"]) > 16384:
                            self._close_client(connection)
                            continue
                        if b"\n" in state["input"]:
                            request_id = None
                            try:
                                line, extra = bytes(state["input"]).split(b"\n", 1)
                                if extra.strip():
                                    raise GatewayError("PROTOCOL_ERROR")
                                request = decode_object(line)
                                if isinstance(request.get("id"), str) and len(request["id"]) <= 160:
                                    request_id = request["id"]
                                result = self._request(request)
                                response = {"ok": True, "code": "OK", "result": result}
                            except GatewayError as exc:
                                response = {"ok": False, "code": exc.code, "result": {}}
                            response.update(protocol=1, id=request_id)
                            state["output"] = json.dumps(response, allow_nan=False).encode() + b"\n"
                            if len(state["output"]) > 65536:
                                self._close_client(connection)
                                continue
                            state["deadline"] = time.monotonic() + self.limits.rpc
                            self.selector.modify(connection, selectors.EVENT_WRITE, "client")
                    elif mask & selectors.EVENT_WRITE:
                        written = connection.send(state["output"])
                        state["output"] = state["output"][written:]
                        if not state["output"]:
                            self._close_client(connection)
                except (OSError, ValueError):
                    self._close_client(connection)
        for connection, state in list(self.clients.items()):
            if time.monotonic() >= state["deadline"]:
                self._close_client(connection)

    def _inspect(self, child, pane):
        result = {"child": child, "owner": False}
        try:
            self.herdr.deadline = time.monotonic() + self.limits.rpc
            self.herdr.available()
            if not self.herdr.enabled():
                raise GatewayError("DISABLED")
            result.update(owner=True, pane=self.herdr.membership(pane, self.identity))
            if child is None:
                self.check(self.config)
                if profile_in_use(self.config, timeout=self.limits.rpc):
                    raise GatewayError("OWNERSHIP_CONFLICT")
            else:
                result["probe"] = self.probe.inspect(child)
        except GatewayError as exc:
            result["error"] = exc.code
        except Exception:
            result["error"] = "INSPECTION_FAILED"
        self.results.put(result)

    def _schedule_inspection(self, now):
        if self.worker is not None or self.termination or self.shutdown or now < max(self.next_probe, self.retry_at):
            return
        child = self.child_identity
        self.worker = threading.Thread(target=self._inspect, args=(child, dict(self.runtime["pane"])),
                                       daemon=True, name="gateway-probe")
        self.worker.start()

    def _collect_inspection(self, now):
        try:
            result = self.results.get_nowait()
        except queue.Empty:
            return
        self.worker = None
        self.next_probe = now + self.limits.probe
        # Results from an exited child cannot grant readiness or start a replacement.
        if result["child"] != self.child_identity or self.termination or self.shutdown:
            return
        error = result.get("error")
        if error == "DISABLED":
            with self.store.mutation():
                self.store.set_intent("pause", reason="plugin_disabled")
            self.shutdown = True
            return
        if not result["owner"]:
            self.owner_lost = now if self.owner_lost is None else self.owner_lost
            self._save(state="UNKNOWN")
            if error in {"ENV_STALE", "PANE_MISMATCH", "OWNERSHIP_CONFLICT", "UNSUPPORTED_VERSION"}:
                self.shutdown = True
            return
        self.owner_lost = None
        if error and self.child is None:
            self._fuse(error)
            return
        self.runtime["pane"] = result["pane"]
        if self.child is None:
            self._spawn()
        else:
            probe = result.get("probe", {"level": 0, "state": "DEGRADED", "operational": False})
            if error:
                probe["code"] = error
            probe["observed_at"] = time.time()
            self.ready_since = (self.ready_since if self.ready_since is not None else now) if probe["level"] == 2 else None
            state = probe["state"]
            if state == "STARTING" and now - self.spawned_at >= self.limits.ready:
                state = "DEGRADED"
            self._save(state=state, last_probe=probe)
            if self.ready_since is not None and now - self.ready_since >= self.limits.reset_ready:
                with self.store.mutation():
                    budget = empty_budget(self.store.intent().get("reset_revision", 0))
                    self.store.write("fuse.json", budget)
                self.ready_since = now

    def _spawn(self):
        with self.store.mutation():
            intent = self.store.intent()
            budget = effective_budget(intent, self.store.read("fuse.json"))
            if intent["desired"] != "running" or budget["fused"] or self.shutdown:
                return
            current = self.store.read("runtime.json", required=True)
            if current.get("instance_nonce") != self.nonce or self.child is not None or self._alive_owned():
                raise GatewayError("OWNERSHIP_CONFLICT")
            if profile_in_use(self.config, probe_socket=False):
                raise GatewayError("OWNERSHIP_CONFLICT")
            # A crash between Popen and recording its PID must block blind replacement.
            self.runtime["spawn_pending"] = True
            self._persist()
            try:
                self.child = self.launch(self.config.gateway_argv(), stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.config.agent_cwd,
                                         env=self.config.child_env(self.env), close_fds=True, start_new_session=False, umask=0o077)
            except OSError as exc:
                self.runtime.update(spawn_pending=False, state="FUSED")
                budget.update(fused=True, reason="SPAWN_FAILED", updated_at=time.time())
                self.store.write("fuse.json", budget)
                self._persist()
                raise GatewayError("SPAWN_FAILED") from exc
            self.child_identity = capture(self.child.pid)
            # An immediate exit can be reaped normally; a live process with unreadable identity is fatal.
            if self.child_identity is not None:
                if (self.child_identity["ppid"] != self.identity["pid"]
                        or self.child_identity["sid"] != self.identity["sid"]):
                    raise GatewayError("INVALID_IDENTITY", "Gateway is outside the pane session")
            self.child_revision = self.restart_revision = intent["revision"]
            self.spawned_at = time.monotonic()
            self.exit_code = None
            self.runtime.update(gateway=self.child_identity, descendants=[], applied_revision=intent["revision"],
                                state="STARTING", last_probe=None, retry_at=None, spawn_pending=False)
            self._persist()
        for stream in (self.child.stdout, self.child.stderr):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, "pipe")
        self.next_probe = self.next_track = 0
        self.ready_since = None
        self.log.event("child_started", generation=self.generation, pid=self.child.pid, revision=self.child_revision)

    @staticmethod
    def _process_key(record):
        return (record["pid"], record["start_fingerprint"]["boot"], record["start_fingerprint"]["value"])

    def _track(self):
        if self.child_identity:
            for record in descendants(self.child_identity):
                self.owned[self._process_key(record)] = record
        self.owned = {key: record for key, record in self.owned.items() if same_process(record)}
        records = list(self.owned.values())
        if self.runtime["descendants"] != records:
            self._save(descendants=records)

    def _alive_owned(self):
        return [record for record in self.owned.values() if same_process(record)]

    def _signal_all(self, signum):
        records = self._alive_owned()
        if self.child_identity and same_process(self.child_identity):
            records.append(self.child_identity)
        for record in records:
            key = (*self._process_key(record), signum)
            if key not in self.sent:
                signal_verified(record, signum)
                self.sent.add(key)

    def _terminate(self, kind, now):
        if self.termination is not None and (kind == "restart" or self.termination["kind"] != "restart"):
            return
        self._track()
        self.termination = {"kind": kind, "stage": "drain" if kind == "restart" else "term",
                            "deadline": now + (self.limits.restart if kind == "restart" else self.limits.stop)}
        if kind == "restart":
            if self.child_identity:
                signal_verified(self.child_identity, signal.SIGUSR1)
        else:
            self._signal_all(signal.SIGTERM)
        self._save(state="DRAINING")

    def _advance_termination(self, now):
        if not self.termination:
            return
        self._track()
        stage = self.termination["stage"]
        if stage != "drain":
            self._signal_all(signal.SIGTERM if stage == "term" else signal.SIGKILL)
        if now >= self.termination["deadline"] and (self.exit_code is None or self._alive_owned()):
            if stage == "kill":
                raise GatewayError("STOP_FAILED", "Verified tasks did not exit before the deadline")
            self.termination.update(stage="term" if stage == "drain" else "kill",
                                    deadline=now + (self.limits.stop if stage == "drain" else self.limits.kill))
            self.log.event("forced_termination", generation=self.generation, stage=self.termination["stage"])
            self._signal_all(signal.SIGTERM if stage == "drain" else signal.SIGKILL)

    def _fuse(self, reason):
        with self.store.mutation():
            budget = effective_budget(self.store.intent(), self.store.read("fuse.json"))
            budget.update(fused=True, reason=reason, updated_at=time.time())
            self.store.write("fuse.json", budget)
            self.runtime.update(state="FUSED")
            self._persist()
        self.log.event("fused", generation=self.generation, code=reason)

    def _finish_exit(self, now):
        code = self.exit_code
        kind = self.termination["kind"] if self.termination else None
        self.runtime["last_exit"] = {"code": code, "at": time.time(), "revision": self.child_revision,
                                     "forced": bool(self.termination and self.termination["stage"] == "kill")}
        # Old descendant pipes must not survive into a new child generation.
        for stream in (self.child.stdout, self.child.stderr):
            if not stream.closed:
                try:
                    self.selector.unregister(stream)
                except KeyError:
                    pass
                stream.close()
        self.child = self.child_identity = None
        self.termination = None
        self.owned.clear()
        self.sent.clear()
        self.ready_since = None
        with self.store.mutation():
            intent = self.store.intent()
            policy_code = 0 if kind in {"stop", "shutdown"} else 75 if kind == "restart" and code <= 0 else code
            action = "stop" if self.shutdown else exit_action(policy_code, intent, self.child_revision)
            budget = effective_budget(intent, self.store.read("fuse.json"))
            if action == "pause":
                intent = self.store.set_intent("pause", reason="observed_clean_exit")
            elif action == "fuse":
                budget.update(fused=True, reason=f"EXIT_{code}", updated_at=time.time())
            elif action == "retry":
                budget, delay = retry_budget(budget, policy_code, time.time(), self.limits, random.uniform(-0.2, 0.2))
                self.retry_at = now + delay
                budget["retry_not_before"] = time.time() + delay
            self.store.write("fuse.json", budget)
            state = "FUSED" if budget["fused"] else "PAUSED" if intent["desired"] == "paused" else "BACKOFF"
            self.runtime.update(state=state, gateway=None, descendants=[], applied_revision=intent["revision"],
                                retry_at=budget.get("retry_not_before"))
            self._persist()
        self.next_probe = self.retry_at
        self.log.event("child_exited", generation=self.generation, code=code, state=state)

    def _tick(self):
        now = time.monotonic()
        received, self.signal_received = self.signal_received, None
        if received == signal.SIGINT:
            with self.store.mutation():
                self.store.set_intent("pause", reason="supervisor_interrupt")
        elif received is not None:
            self.shutdown = True
        intent = self.store.intent()
        budget = effective_budget(intent, self.store.read("fuse.json"))
        if self.owner_lost is not None and now - self.owner_lost >= self.limits.owner_grace:
            self.shutdown = True
        if self.child:
            if now >= self.next_track:
                # ponytail: polling misses tasks reparented between scans; OS containment needs its own host validation.
                self._track()
                self.next_track = now + 0.2
            if self.shutdown or intent["desired"] == "paused" or budget["fused"]:
                self._terminate("shutdown" if self.shutdown else "stop", now)
            elif intent["action"] == "restart" and intent["revision"] > self.restart_revision:
                self.restart_revision = intent["revision"]
                self._terminate("restart", now)
                self._save(applied_revision=intent["revision"])
            self.exit_code = self.child.poll()
            if self.exit_code is not None:
                if self._alive_owned():
                    if not self.termination or self.termination["stage"] == "drain":
                        self._terminate("exited", now)
                else:
                    self._finish_exit(now)
            self._advance_termination(now)
        elif self.shutdown or intent["desired"] == "paused" or budget["fused"]:
            self._save(state="FUSED" if budget["fused"] else "PAUSED" if intent["desired"] == "paused" else "ABSENT")
            return False
        self._collect_inspection(now)
        self._schedule_inspection(now)
        return True

    def _emergency_cleanup(self):
        if not self.child:
            return
        # Persistence/probe failures must not abandon a child, even when no state write can succeed.
        try:
            if self.child_identity is None:
                self.child_identity = capture(self.child.pid)
            if self.child_identity:
                for record in descendants(self.child_identity):
                    self.owned[self._process_key(record)] = record
            for signum, duration in ((signal.SIGTERM, self.limits.stop), (signal.SIGKILL, self.limits.kill)):
                self._signal_all(signum)
                deadline = time.monotonic() + duration
                while time.monotonic() < deadline:
                    if self.child.poll() is not None and not self._alive_owned():
                        return
                    self._io(self.limits.poll)
            self.outcome = 30
        except Exception:
            self.outcome = 30

    def run(self):
        previous = {}
        try:
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                previous[signum] = signal.signal(signum, lambda number, _: setattr(self, "signal_received", number))
            self._claim()
            budget = effective_budget(self.store.intent(), self.store.read("fuse.json"))
            self.retry_at = time.monotonic() + min(self.limits.backoff[-1], max(0, budget.get("retry_not_before", 0) - time.time()))
            while self._tick():
                self._io(self.limits.poll)
        except Exception as exc:
            self.outcome = exc.exit_code if isinstance(exc, GatewayError) else 30
            if self.log:
                self.log.event("supervisor_error", generation=self.generation,
                               code=exc.code if isinstance(exc, GatewayError) else "IO_ERROR")
            self._emergency_cleanup()
            if self.runtime:
                try:
                    self._save(state="UNKNOWN", last_error=exc.code if isinstance(exc, GatewayError) else "IO_ERROR")
                except GatewayError:
                    pass
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
            for key in list(self.selector.get_map().values()):
                self.selector.unregister(key.fileobj)
                key.fileobj.close()
            self.selector.close()
            if self.socket_inode:
                try:
                    info = self.path.lstat()
                    if (info.st_dev, info.st_ino) == self.socket_inode:
                        self.path.unlink()
                except FileNotFoundError:
                    pass
            if self.created_socket_dir:
                try:
                    self.path.parent.rmdir()
                except OSError:
                    pass
            if self.log:
                self.log.close()
            if self.lease:
                self.lease.close()
            if self.store:
                self.store.close()
        return self.outcome
