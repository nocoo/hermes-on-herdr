"""Short, owner-scoped reconciliation; only the pane supervisor launches a Gateway."""

import os
import time
import uuid

from .config import Config, ID_PATTERN, PLUGIN_ID, preflight
from .errors import GatewayError
from .identity import capture, public_identity, same_process
from .lifecycle import effective_budget
from .rpc import Herdr, RemoteError, control_query, decode_object, profile_in_use, supervisor_socket
from .state import Store


def identifier(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise GatewayError("PROTOCOL_ERROR", "Missing or invalid resource identity")
    return value


def pane_identity(value):
    if not isinstance(value, dict):
        raise GatewayError("PROTOCOL_ERROR", "Missing pane identity")
    return {key: identifier(value.get(key)) for key in ("workspace_id", "tab_id", "pane_id", "terminal_id")}


class Controller:
    def __init__(self, config: Config, *, check=None, herdr=None, budget: float = 4.5):
        self.config = config
        self.herdr = herdr or Herdr(config)
        self.deadline = time.monotonic() + budget
        self.check = check or (lambda config: preflight(config, deadline=self.deadline))
        self.checked = False
        self.herdr.deadline = self.deadline
        self.creator = uuid.uuid4().hex
        self.identity = capture(os.getpid())

    def _check(self):
        if not self.checked:
            self._remaining()
            self.check(self.config)
            self.checked = True

    def _remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise GatewayError("PENDING", "Controller deadline exhausted")
        return min(2, remaining)

    def _binding(self, store):
        self.config.check_binding(store.read("binding.json", required=True))

    def _runtime(self, store):
        runtime = store.read("runtime.json")
        if runtime is not None:
            if runtime["owner_key"] != self.config.key:
                raise GatewayError("OWNERSHIP_CONFLICT")
            identifier(runtime.get("instance_nonce"))
            pane_identity(runtime.get("pane"))
            if not isinstance(runtime.get("supervisor"), dict):
                raise GatewayError("STATE_SCHEMA")
        return runtime

    def _pending(self, store):
        pending = store.read("pending.json")
        if pending is not None:
            if pending["owner_key"] != self.config.key:
                raise GatewayError("OWNERSHIP_CONFLICT")
            if (pending.get("phase") not in {"reserved", "workspace_requested", "workspace_known", "pane_requested", "pane_known"}
                    or type(pending.get("intent_revision")) is not int):
                raise GatewayError("STATE_SCHEMA")
        return pending

    @staticmethod
    def _live_records(runtime):
        if runtime is None:
            return []
        records = [runtime.get("supervisor"), runtime.get("gateway"), *runtime.get("descendants", [])]
        return [record for record in records if record and same_process(record)]

    def _verify(self, runtime):
        self.herdr.available()
        response = control_query(supervisor_socket(self.config), "status", timeout=self._remaining())
        if (response.get("kind") != "hermes-gateway-herdr"
                or any(response.get(key) != runtime[key] for key in ("owner_key", "generation", "instance_nonce"))
                or response.get("supervisor") != public_identity(runtime["supervisor"])
                or not same_process(runtime["supervisor"])):
            raise GatewayError("UNKNOWN", "Supervisor identity does not match the ledger")
        pane = self.herdr.membership(runtime["pane"], runtime["supervisor"])
        reported_pane = pane_identity(response.get("pane"))
        if any(reported_pane[key] != pane[key] for key in ("workspace_id", "tab_id", "pane_id")):
            raise GatewayError("ENV_STALE")
        gateway = response.get("gateway")
        if gateway is not None:
            if gateway != public_identity(runtime.get("gateway")) or not same_process(gateway):
                raise GatewayError("UNKNOWN", "Child changed during observation")
        elif runtime.get("gateway") and same_process(runtime["gateway"]):
            raise GatewayError("UNKNOWN", "Live child is missing from supervisor status")
        # Project onto a fixed public contract; never expose arbitrary socket payloads.
        fields = ("state", "desired", "intent_revision", "applied_revision", "fused", "reason", "last_exit",
                  "last_probe", "recovery", "dropped_log_chunks")
        result = {key: response.get(key) for key in fields}
        result.update(schema=1, owner_key=self.config.key, generation=runtime["generation"],
                      pane=pane, supervisor=public_identity(runtime["supervisor"]), gateway=gateway)
        return result

    def _notify(self, intent, runtime):
        if runtime is None or not same_process(runtime["supervisor"]):
            return False
        if intent["desired"] != "paused" and intent.get("action") != "restart":
            return False
        try:
            control_query(supervisor_socket(self.config), "stop" if intent["desired"] == "paused" else "restart",
                          timeout=min(0.3, self._remaining()), request_id=intent["request_id"],
                          owner_key=self.config.key, generation=runtime["generation"], intent_revision=intent["revision"])
            return True
        except GatewayError:
            # Intent was already fsynced; the owner also polls it, including after controller death.
            return False

    @staticmethod
    def _summary(intent, state, **fields):
        return {"schema": 1, "state": state, "desired": intent["desired"],
                "intent_revision": intent["revision"], "recovery": "next_owner_event", **fields}

    def status(self):
        with Store(self.config.state_dir) as store:
            self._binding(store)
            intent, runtime, pending = store.intent(), self._runtime(store), self._pending(store)
            budget = effective_budget(intent, store.read("fuse.json"))
            held = store.lifetime_held()
            live = self._live_records(runtime)
            if held and runtime:
                try:
                    return self._verify(runtime)
                except GatewayError as exc:
                    return self._summary(intent, "UNKNOWN", code=exc.code, lifetime_held=True)
            if live or held or (runtime and runtime.get("spawn_pending")):
                state = "ORPHAN" if not held and runtime and runtime.get("gateway") in live else "UNKNOWN"
            elif intent["desired"] == "paused":
                state = "PAUSED"
            elif budget["fused"]:
                state = "FUSED"
            elif pending:
                state = "PENDING" if pending["phase"] in {"reserved", "workspace_known", "pane_known"} else "PENDING_UNKNOWN"
            else:
                state = "ABSENT"
            if state in {"ABSENT", "PAUSED"}:
                try:
                    if profile_in_use(self.config, timeout=self._remaining()):
                        state = "UNKNOWN"
                except GatewayError:
                    state = "UNKNOWN"
            return self._summary(intent, state, lifetime_held=held, fused=budget["fused"], reason=budget.get("reason"),
                                 generation=runtime["generation"] if runtime else pending["generation"] if pending else None,
                                 last_error=runtime.get("last_error") if runtime else None)

    def action(self, action, env, *, request_id=None, expected_revision=None):
        self.config.check_context(env)
        with Store(self.config.state_dir) as store:
            self._binding(store)
            if action in {"start", "resume", "restart"}:
                self._check()
            with store.mutation():
                intent = store.set_intent(action, request_id=request_id, expected_revision=expected_revision)
            # Do not undo a successful Pause if optional diagnostics are damaged.
            try:
                runtime = self._runtime(store)
                notified = self._notify(intent, runtime)
            except GatewayError:
                notified = False
            if intent["desired"] == "paused":
                return self._summary(intent, "ACCEPTED", accepted=True, notified=notified)
        try:
            result = self.ensure(env)
        except GatewayError as exc:
            return self._summary(intent, "ACCEPTED", accepted=True, code=exc.code)
        result.update(accepted=True)
        return result

    def _relevant(self, env, source, runtime, pending):
        if source != "event":
            return True
        event = env.get("HERDR_PLUGIN_EVENT")
        if event == "workspace.focused":
            return True
        if event not in {"pane.exited", "pane.closed"}:
            return False
        raw = env.get("HERDR_PLUGIN_EVENT_JSON", "")
        if not isinstance(raw, str) or len(raw.encode()) > 16384:
            raise GatewayError("PROTOCOL_ERROR")
        payload = decode_object(raw.encode())
        data = payload.get("data")
        if payload.get("event") != event or not isinstance(data, dict):
            raise GatewayError("PROTOCOL_ERROR")
        pane = data.get("pane_id")
        # Focus context is unrelated to the pane in an exit event.
        return bool(pane and any(record and record.get("pane", {}).get("pane_id") == pane for record in (runtime, pending)))

    def ensure(self, env, *, source="manual"):
        self.config.check_context(env)
        with Store(self.config.state_dir) as store:
            self._binding(store)
            with store.mutation():
                intent, runtime, pending = store.intent(), self._runtime(store), self._pending(store)
                if not self._relevant(env, source, runtime, pending):
                    return self._summary(intent, "IGNORED")
                budget = effective_budget(intent, store.read("fuse.json"))
                held = store.lifetime_held()
            if intent["desired"] == "paused":
                self._notify(intent, runtime)
                live = self._live_records(runtime)
                return self._summary(intent, "DRAINING" if held else "UNKNOWN" if live else "PAUSED")
            if budget["fused"]:
                return self._summary(intent, "FUSED", reason=budget.get("reason"))
            self.herdr.available()
            if not self.herdr.enabled():
                return self._summary(intent, "DISABLED")
            if held:
                if runtime is None:
                    return self._summary(intent, "UNKNOWN", code="LIFETIME_WITHOUT_RUNTIME")
                try:
                    observed = self._verify(runtime)
                except GatewayError as exc:
                    return self._summary(intent, "UNKNOWN", code=exc.code)
                with store.mutation():
                    current = self._runtime(store)
                    if (store.intent()["revision"] != intent["revision"] or current is None
                            or current["instance_nonce"] != runtime["instance_nonce"] or not store.lifetime_held()):
                        return self._summary(store.intent(), "BUSY")
                    if current["pane"] != observed["pane"] or current.get("ownership_source") == "created":
                        current.update(pane=observed["pane"], ownership_source="verified_ledger", updated_at=time.time())
                        store.write("runtime.json", current)
                self._notify(intent, runtime)
                return observed
            live = self._live_records(runtime)
            if live or (runtime and runtime.get("spawn_pending")):
                return self._summary(intent, "ORPHAN" if runtime and runtime.get("gateway") in live else "UNKNOWN")
            if pending and pending["intent_revision"] == intent["revision"]:
                # Only pre-send phases can be taken over after proven controller death.
                if (pending["phase"] not in {"reserved", "workspace_known"} or not pending.get("controller")
                        or same_process(pending["controller"])):
                    return self._summary(intent, "PENDING_UNKNOWN" if pending["phase"].endswith("requested") else "PENDING",
                                         generation=pending["generation"])
            self._check()
            self._remaining()
            if profile_in_use(self.config, timeout=self._remaining()):
                return self._summary(intent, "UNKNOWN", code="PROFILE_IN_USE")
            # Reuse only a workspace recorded by a previous generation; labels are never authority.
            workspace = None
            known = runtime["pane"]["workspace_id"] if runtime else pending.get("workspace_id") if pending else None
            if known:
                snapshot = self.herdr.call("session.snapshot").get("snapshot")
                if not isinstance(snapshot, dict) or not isinstance(snapshot.get("workspaces"), list):
                    raise GatewayError("PROTOCOL_ERROR")
                if any(isinstance(item, dict) and item.get("workspace_id") == known for item in snapshot["workspaces"]):
                    workspace = known
            with store.mutation():
                current_intent, current_pending, current_runtime = store.intent(), self._pending(store), self._runtime(store)
                if (current_intent["revision"] != intent["revision"] or current_intent["desired"] != "running"
                        or effective_budget(current_intent, store.read("fuse.json"))["fused"]
                        or current_pending != pending or current_runtime != runtime or store.lifetime_held()
                        or self._live_records(current_runtime)):
                    return self._summary(current_intent, "BUSY")
                if pending and pending["intent_revision"] == intent["revision"]:
                    ticket = dict(pending, creator=self.creator, controller=self.identity)
                else:
                    ticket = {"schema": 1, "owner_key": self.config.key, "generation": uuid.uuid4().hex,
                              "intent_revision": intent["revision"], "phase": "workspace_known" if workspace else "reserved",
                              "request_id": uuid.uuid4().hex, "creator": self.creator, "controller": self.identity,
                              "workspace_id": workspace, "created_at": time.time()}
                    if pending:
                        # Revocation precedes any new request. Delayed old panes fail their ticket check.
                        ticket["revoked"] = {key: pending.get(key) for key in ("generation", "phase", "workspace_id", "pane")}
                store.write("pending.json", ticket)
            return self._create(store, ticket)

    def _advance(self, store, ticket, phase, **fields):
        with store.mutation():
            current, intent = self._pending(store), store.intent()
            if current is None and self._runtime(store) and self._runtime(store)["generation"] == ticket["generation"]:
                return None  # The supervisor already consumed the ticket and registered R0.
            if (current is None or current["generation"] != ticket["generation"] or current.get("creator") != self.creator
                    or current["phase"] != ticket["phase"] or intent["revision"] != ticket["intent_revision"]
                    or intent["desired"] != "running"):
                raise GatewayError("STALE_REQUEST", "Creation ticket changed")
            updated = dict(current, phase=phase, **fields)
            store.write("pending.json", updated)
            return updated

    def _create(self, store, ticket):
        try:
            if ticket["phase"] == "reserved":
                self._remaining()
                ticket = self._advance(store, ticket, "workspace_requested", request_id=uuid.uuid4().hex)
                result = self.herdr.call("workspace.create", {"label": "Hermes Control", "cwd": str(self.config.agent_cwd), "focus": False},
                                         request_id=ticket["request_id"])
                workspace = result.get("workspace")
                workspace_id = identifier(workspace.get("workspace_id") if isinstance(workspace, dict) else None)
                ticket = self._advance(store, ticket, "workspace_known", workspace_id=workspace_id)
            self._remaining()
            ticket = self._advance(store, ticket, "pane_requested", request_id=uuid.uuid4().hex)
            result = self.herdr.call("plugin.pane.open", {
                "plugin_id": PLUGIN_ID, "entrypoint": "gateway", "placement": "tab", "workspace_id": ticket["workspace_id"],
                "cwd": str(self.config.plugin_root), "focus": False,
                "env": {"HGH_OWNER_KEY": self.config.key, "HGH_GENERATION": ticket["generation"]},
            }, request_id=ticket["request_id"])
            plugin_pane = result.get("plugin_pane")
            if (not isinstance(plugin_pane, dict) or plugin_pane.get("plugin_id") != PLUGIN_ID
                    or plugin_pane.get("entrypoint") != "gateway"):
                raise GatewayError("PROTOCOL_ERROR")
            pane = pane_identity(plugin_pane.get("pane"))
            if pane["workspace_id"] != ticket["workspace_id"]:
                raise GatewayError("PROTOCOL_ERROR")
            updated = self._advance(store, ticket, "pane_known", pane=pane)
            if updated is None:
                intent = store.intent()
                return self._summary(intent, "STARTING" if intent["desired"] == "running" else "DRAINING", generation=ticket["generation"])
            return self._summary(store.intent(), "PENDING", generation=ticket["generation"])
        except RemoteError as exc:
            # The pinned API can return some errors after mutation. Revoke this generation
            # before retrying even an explicit rejection; never assume an error rolls it back.
            with store.mutation():
                current = self._pending(store)
                if current and current["generation"] == ticket["generation"]:
                    current["last_error"] = "HERDR_REJECTED"
                    store.write("pending.json", current)
            return self._summary(store.intent(), "PENDING_UNKNOWN", code=exc.code, generation=ticket["generation"])
        except GatewayError as exc:
            if exc.code == "STALE_REQUEST":
                return self._summary(store.intent(), "CANCELLED", generation=ticket["generation"])
            if exc.code in {"RPC_UNAVAILABLE", "PROTOCOL_ERROR", "PENDING"}:
                return self._summary(store.intent(), "PENDING_UNKNOWN", generation=ticket["generation"], code=exc.code)
            raise
