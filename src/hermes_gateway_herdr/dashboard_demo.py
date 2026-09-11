"""Deterministic offline presentation data; never mixed with live monitoring."""

import math
from pathlib import Path

from .monitor import Profile, Snapshot


def demo_snapshot(count=2, *, now=1789203600):
    if not 1 <= count <= 1000:
        raise ValueError("Demo profile count must be between 1 and 1000")
    rows = []
    for i in range(count):
        name = "cherry" if i == 0 else "default" if i == 1 else f"agent-{i:02}"
        cpu = tuple(max(.1, 2 + (i % 7) * 1.3 + math.sin(n / 5 + i) * 1.4 +
                        (12 * math.exp(-((n - 54) / 5) ** 2))) for n in range(90))
        memory = tuple(140 + i * 11 + n * .12 + math.sin(n / 9 + i) * 3 for n in range(90))
        state = "READY" if i == 0 else "DEGRADED" if i % 7 == 6 else "STOPPED" if i > 1 and i % 5 == 4 else "RUNNING"
        live = state != "STOPPED"
        rows.append(Profile(name, Path("/demo/profiles") / name, managed=i == 0, state=state,
                            pid=42100 + i * 3 if live else None, started=now - 4567 - i * 1500 if live else None,
                            supervision="external" if i == 0 else "launchd", cpu=cpu[-1] if live else None,
                            rss=int(memory[-1] * 1048576) if live else None, active=(0 if i % 3 else 1) if live else None,
                            platforms=(("discord" if i == 0 else "telegram", "retrying" if state == "DEGRADED" else "connected"),) if live else (),
                            observed=now - (i % 4), error="PLATFORM_RETRY" if state == "DEGRADED" else "",
                            cpu_history=cpu if live else (), memory_history=memory if live else (),
                            pane="w20:p3" if i == 0 else ""))
    events = ((now - 67, "cherry", "STARTING", ""), (now - 64, "cherry", "READY", ""))
    if count > 1:
        events += ((now - 60, "default", "RUNNING", ""),)
    if count > 6:
        events += ((now - 10, "agent-06", "DEGRADED", "PLATFORM_RETRY"),)
    history = tuple(8 + math.sin(n / 8) * 3 + 6 * math.exp(-((n - 48) / 7) ** 2) for n in range(90))
    return Snapshot(tuple(rows), now, history[-1], int(8.53 * 1073741824), 32 * 1073741824, history, events)
