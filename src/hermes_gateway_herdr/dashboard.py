"""Terminal dashboard runner; the Gateway supervisor never imports this module."""

from dataclasses import asdict, replace
import json
import os
import select
import stat
import sys
import tempfile
import termios
import threading
import time

from .dashboard_demo import demo_snapshot
from .dashboard_view import DashboardView, INTERVALS, LAYOUTS, MOTION_FPS, THEMES, ViewState, mascot_pose, theme_for
from .display import restore_terminal
from .errors import GatewayError
from .monitor import Monitor, Snapshot
from .paths import json_object, private_bytes

from hqtui import App, AppOptions, render_to_screen

PREFERENCE_KEYS = ("layout", "theme", "system", "interval", "animation")


def preferences(state):
    return {"schema": 1, **{key: getattr(state, key) for key in PREFERENCE_KEYS}}


def load_preferences(config):
    state = ViewState(selected=config.profile_id)
    try:
        data = json_object(private_bytes(config.config_dir / "dashboard.json", 4096))
        if (type(data.get("schema")) is int and data["schema"] == 1
                and data.get("layout") in LAYOUTS and data.get("theme") in THEMES
                and type(data.get("system")) is bool and type(data.get("interval")) is int and data["interval"] in INTERVALS
                and type(data.get("animation", True)) is bool):
            for key in PREFERENCE_KEYS:
                setattr(state, key, data.get(key, getattr(state, key)))
    except (GatewayError, OSError, ValueError, TypeError):
        pass
    return state


def save_preferences(config, state):
    path = config.config_dir / "dashboard.json"
    temporary = None
    try:
        if os.path.lexists(path):
            private_bytes(path, 4096)  # Do not overwrite a symlink, shared file or foreign object.
        fd, temporary = tempfile.mkstemp(prefix=".dashboard-", dir=config.config_dir)
        with os.fdopen(fd, "w") as stream:
            json.dump(preferences(state), stream)
            stream.write("\n")
        os.replace(temporary, path)
        return True
    except (GatewayError, OSError, ValueError):
        return False
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def parent_alive(fd):
    if fd is None:
        return True
    try:
        ready, _, _ = select.select([fd], [], [], 0)
        return not ready or bool(os.read(fd, 1))
    except (OSError, ValueError):
        return False


def run_dashboard(config, *, demo_profiles=None, snapshot=False, json_output=False,
                  width=100, height=30, parent_fd=None, startup=False):
    if not 20 <= width <= 300 or not 8 <= height <= 100 or (demo_profiles is not None and not 1 <= demo_profiles <= 1000):
        raise GatewayError("INVALID_ARGUMENT")
    embedded = parent_fd is not None
    if embedded and (parent_fd < 3 or not stat.S_ISSOCK(os.fstat(parent_fd).st_mode)):
        raise GatewayError("INVALID_ARGUMENT", "An embedded dashboard requires its private supervisor channel")
    if not parent_alive(parent_fd):
        return 0
    state = ViewState(selected="cherry") if demo_profiles is not None else load_preferences(config)
    def control(action):
        try:
            os.write(parent_fd, b"s" if action == "start" else b"p")
        except (OSError, ValueError):
            state.notice = "Gateway controls unavailable."

    # --startup remains accepted for older launchers; every launch opens the full dashboard.
    view = DashboardView(state, session=config.owner_session, embedded=embedded,
                         demo=demo_profiles is not None, control=control)
    monitor = Monitor(config, host=state.system) if demo_profiles is None else None

    def collect():
        if monitor is None:
            return demo_snapshot(demo_profiles, now=time.time())
        monitor.selected, monitor.host = state.selected, state.system
        return monitor.collect()

    if snapshot or json_output or not (sys.stdin.isatty() and sys.stdout.isatty()):
        data = collect()
        if json_output:
            print(json.dumps({"schema": 1, "demo": demo_profiles is not None, **asdict(data)}, default=str, allow_nan=False))
        else:
            screen = render_to_screen(width, height, theme_for(state.theme), lambda ui: view.render(ui, data))
            print(screen.text())
        return 0

    # Rendering and socket/disk sampling cannot block one another. Only one sampler exists.
    data = {"snapshot": Snapshot(), "focused": True, "pose": 0}
    stopped, wake = threading.Event(), threading.Event()
    app = App(AppOptions(theme=theme_for(state.theme), fps=MOTION_FPS, remote_fps=MOTION_FPS, always_render=False,
                         quit_keys=(), focus_navigation=False))
    app.render(lambda frame: view.render(frame.ui, data["snapshot"], pose=data["pose"]))
    # hqtui enables all pointer motion by default; only clicks and wheel events
    # are useful here. Avoid repainting whenever a pointer crosses the pane.
    app.on("frame", lambda stats: app.terminal.write("\x1b[?1003l\x1b[?1002l\x1b[?1000h\x1b[?1006h")
           if stats.frame == 0 and app.capabilities.mouse else None)
    mode = termios.tcgetattr(sys.stdin.fileno())

    def lifetime():
        # A blocking wait costs no polling CPU. Parent death also exits a renderer
        # blocked in terminal output or sampling; it cannot leave an orphan TUI.
        try:
            select.select([parent_fd], [], [])
        except (OSError, ValueError):
            pass
        try:
            restore_terminal(mode)
        finally:
            os._exit(0)

    def sampling():
        last_started = float("-inf")
        animating, motion_started = False, 0
        while not stopped.is_set():
            now = time.monotonic()
            visible = data["focused"]
            motion = visible and state.animation and view.has_mascot(app.width, app.height)
            if motion and not animating:
                motion_started = now
            animating = motion
            pose, next_pose = mascot_pose(now - motion_started) if motion else (0, float("inf"))
            if pose != data["pose"]:
                data["pose"] = pose
                if visible:
                    app.invalidate()
            interval = state.interval if visible else 10
            remaining = last_started + interval - now
            if remaining > 0:
                # Animation shares this wait, never the sampling deadline. Resting,
                # compact views add no animation wakeups or RPC calls.
                wake.wait(max(0.001, min(remaining, next_pose)))
                wake.clear()
                continue
            last_started = time.monotonic()
            try:
                data["snapshot"] = collect()
            except Exception:
                old = data["snapshot"]
                data["snapshot"] = replace(old, error="COLLECTOR_UNAVAILABLE", profiles=tuple(
                    replace(p, state="UNKNOWN", cpu=None, rss=None, active=None, platforms=(), error="COLLECTOR_UNAVAILABLE")
                    for p in old.profiles))
            if data["focused"]:
                app.invalidate()

    saved_preferences = preferences(state)

    def changed():
        nonlocal saved_preferences
        current = preferences(state)
        if current != saved_preferences:
            if current["theme"] != saved_preferences["theme"]:
                app.set_theme(theme_for(state.theme))
            if monitor is not None:
                if save_preferences(config, state):
                    state.notice = ""
                else:
                    state.notice = "Could not save preferences."
            saved_preferences = preferences(state)
        wake.set()

    def key(event):
        if event.key == "ctrl+c":
            if embedded:
                control("pause")
            else:
                app.quit()
            return
        if event.name == "q" and not state.filtering:
            if embedded:
                state.help = False
            else:
                app.quit()
            wake.set()
            return
        if embedded and event.name == "enter" and not state.filtering:
            control("start")
            wake.set()
            return
        state.key(event, data["snapshot"])
        changed()

    def focus(event):
        data["focused"] = event.focused
        wake.set()
        if event.focused:
            app.invalidate()

    app.on("key", key)
    app.on("mouse", lambda event: changed())
    app.on("focus", focus)
    app.on("resize", lambda size: wake.set())
    worker = threading.Thread(target=sampling, daemon=True, name="profile-monitor")
    if embedded:
        threading.Thread(target=lifetime, daemon=True, name="dashboard-lifetime").start()
    worker.start()
    try:
        app.start()
        return 0
    except (OSError, ValueError, RuntimeError):
        return 30
    finally:
        stopped.set()
        wake.set()
        worker.join(timeout=0.3)
        # hqtui restores screen/modes normally; also restore input if its final write failed.
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, mode)
        except (OSError, termios.error):
            pass
