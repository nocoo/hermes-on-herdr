"""Measure the real embedded TUI against isolated fake Gateways, never installed services."""

import argparse
from contextlib import ExitStack
from dataclasses import replace
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import psutil

from hermes_gateway_herdr.dashboard_demo import demo_snapshot
from hermes_gateway_herdr.dashboard_view import DashboardView, ViewState, theme_for
from hermes_gateway_herdr.identity import capture
from hqtui import render_to_screen
from helpers import SocketServer, Terminal, wait_until
from test_rpc import gateway_payloads
from test_supervisor import SupervisorTests


def cpu_time(process):
    value = process.cpu_times()
    return value.user + value.system


def measure(process, terminal, seconds):
    before, output, started = cpu_time(process), terminal.bytes_received, time.monotonic()
    memory = []
    while time.monotonic() - started < seconds:
        memory.append(process.memory_info().rss)
        time.sleep(0.25)
    elapsed = time.monotonic() - started
    return {"seconds": round(elapsed, 3), "cpu_percent_one_core": round((cpu_time(process) - before) / elapsed * 100, 3),
            "rss_mib_median": round(statistics.median(memory) / 1048576, 2),
            "rss_mib_peak": round(max(memory) / 1048576, 2),
            "tty_bytes_per_second": round((terminal.bytes_received - output) / elapsed, 1)}


def embedded(profiles, width, height, seconds):
    with ExitStack() as cleanup:
        terminal = Terminal(width, height)
        cleanup.callback(terminal.close)
        # Reuse the same verified fixture lifecycle as the integration tests.
        case = SupervisorTests()
        case.setUp()
        cleanup.callback(case.doCleanups)
        original_context = case.fixture.context
        case.fixture.context = lambda generation="generation": dict(original_context(generation), COLORTERM="truecolor")
        peer = capture(os.getpid())
        servers = []
        for index in range(1, profiles):
            name = "default" if index == 1 else f"agent-{index:03}"
            home = case.fixture.root if index == 1 else case.fixture.root / "profiles" / name
            home.mkdir(mode=0o700, exist_ok=True)
            scoped = replace(case.config, profile_id=name, profile_home=home)
            identity, status = gateway_payloads(scoped, peer)
            def answer(request, identity=identity, status=status):
                payload = identity if request["verb"] == "identify" else dict(status, answered_at=time.time())
                return {"protocol": 1, "id": request["id"], "ok": True, "result": payload}
            server = SocketServer(home / "gateway.sock", answer)
            cleanup.callback(server.close)
            servers.append(server)
        case.start({"limits": {"poll": 0.05, "probe": 2, "ready": 5, "owner_grace": 3}}, terminal=terminal)
        child = case.wait_child()
        wait_until(lambda: terminal.contains("HERMES") and case.store.read("runtime.json")["state"] == "READY", timeout=8)
        renderers = [p for p in psutil.Process(case.process.pid).children() if p.pid != child["pid"]]
        if len(renderers) != 1:
            raise RuntimeError("Expected exactly one isolated renderer")
        renderer = renderers[0]
        time.sleep(6)  # Warm imports, native identity probes, CPU deltas and the first graphs.
        foreground = measure(renderer, terminal, seconds)
        sampled = sum(bool(s.requests) for s in servers)
        requests = sum(len(s.requests) for s in servers)
        terminal.send(b"q")
        wait_until(lambda: terminal.contains("Dashboard hidden"))
        time.sleep(0.25)
        hidden = measure(renderer, terminal, seconds)
        started = time.monotonic()
        case.action("pause", send=False)
        if case.process.wait(timeout=3) != 0 or not terminal.restored():
            raise RuntimeError("Fixture supervisor did not stop and restore its terminal")
        result = {"profiles": profiles, "terminal": [width, height], "foreground": foreground, "hidden": hidden,
                  "background_profiles_seen_during_foreground": sampled, "background_native_requests": requests,
                  "fixture_pause_seconds": round(time.monotonic() - started, 3)}
        print(json.dumps(result), flush=True)
        return result


def render_cost(count, width, height):
    snapshot = demo_snapshot(count)
    view = DashboardView(ViewState(selected="cherry"), demo=True)
    durations = []
    for _ in range(32):
        started = time.perf_counter()
        render_to_screen(width, height, theme_for("herdr"), lambda ui: view.render(ui, snapshot, now=snapshot.updated))
        durations.append((time.perf_counter() - started) * 1000)
    values = sorted(durations[1:])
    return {"profiles": count, "terminal": [width, height], "median_ms": round(statistics.median(values), 3),
            "p95_ms": round(values[int(len(values) * .95)], 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", nargs="+", type=int, default=[2, 50])
    parser.add_argument("--seconds", type=int, default=20, help="Steady-state window for each foreground/hidden phase")
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=44)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (not all(2 <= n <= 100 for n in args.profiles) or not 10 <= args.seconds <= 60
            or not 40 <= args.width <= 300 or not 16 <= args.height <= 100):
        parser.error("Use 2..100 profiles, 10..60 seconds and a 40..300 by 16..100 terminal")
    result = {"schema": 1, "platform": platform.system(), "architecture": platform.machine(),
              "python": platform.python_version(), "hqtui_commit": "d9a841494bab910403737a8c791d6d96ef52e878",
              "scope": "Actual embedded TUI process, real PTY, local fixture RPC and process metrics; backend fixtures excluded.",
              "fixture_note": "One supervised fake Gateway; other profile sockets are served by the benchmark process. No installed services are used.",
              "embedded": [embedded(count, args.width, args.height, args.seconds) for count in args.profiles],
              "render_only": [render_cost(count, args.width, args.height) for count in (1, 2, 50, 1000)]}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved offline benchmark: {args.output}", flush=True)


if __name__ == "__main__":
    main()
