"""Exit decisions and retry budgets shared by the supervisor and its tests."""

from dataclasses import dataclass
from .identity import boot_fingerprint


@dataclass(frozen=True)
class Limits:
    poll: float = 0.05
    rpc: float = 2
    probe: float = 5
    ready_spacing: float = 1
    ready: float = 90
    r0: float = 5
    owner_grace: float = 20
    stop: float = 25
    kill: float = 5
    restart: float = 210
    restart_spacing: float = 1
    reset_ready: float = 300
    failure_window: float = 300
    failure_limit: int = 6
    restart_window: float = 60
    restart_limit: int = 5
    backoff: tuple[float, ...] = (1, 2, 4, 8, 16, 30)


def empty_budget(reset_revision: int = 0) -> dict:
    return {"schema": 1, "fused": False, "reason": None, "failures": [], "restarts": [],
            "streak": 0, "boot": boot_fingerprint(), "reset_revision": reset_revision}


def effective_budget(intent: dict, stored: dict | None) -> dict:
    revision = intent.get("reset_revision", 0)
    if stored is None or stored.get("reset_revision", 0) < revision:
        return empty_budget(revision)
    return stored


def exit_action(code: int, intent: dict, child_revision: int) -> str:
    if intent["desired"] == "paused":
        return "stop"
    if code == 0:
        return "retry" if intent["revision"] > child_revision else "pause"
    if code in (75, 1) or code < 0:
        return "retry"
    return "fuse"


def retry_budget(previous: dict | None, code: int, now: float, limits: Limits, jitter: float = 0) -> tuple[dict, float]:
    budget = dict(previous or empty_budget())
    # Keep future stamps after a wall-clock rollback; a clock change must not unlock a fuse.
    budget["failures"] = [stamp for stamp in budget["failures"] if now - stamp <= limits.failure_window]
    budget["restarts"] = [stamp for stamp in budget["restarts"] if now - stamp <= limits.restart_window]
    if budget["fused"]:
        return budget, 0
    if code == 0:
        return budget, limits.restart_spacing
    if code == 75:
        budget["restarts"].append(now)
        delay = limits.restart_spacing
        if len(budget["restarts"]) >= limits.restart_limit:
            budget.update(fused=True, reason="RESTART_STORM")
    else:
        budget["failures"].append(now)
        budget["streak"] = budget.get("streak", 0) + 1
        delay = limits.backoff[min(budget["streak"] - 1, len(limits.backoff) - 1)]
        delay = min(limits.backoff[-1], delay * (1 + max(-0.2, min(0.2, jitter))))
        if len(budget["failures"]) >= limits.failure_limit:
            budget.update(fused=True, reason="CRASH_LOOP")
    budget["updated_at"] = now
    return budget, delay
