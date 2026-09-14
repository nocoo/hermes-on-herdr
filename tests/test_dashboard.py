from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

from hermes_gateway_herdr import dashboard
from hermes_gateway_herdr.dashboard_view import DashboardView, ViewState, theme_for
from hermes_gateway_herdr.display import Display
from helpers import Fixture, ROOT, Terminal, json_lines, private_file, wait_until


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config
        self.path = self.config.config_dir / "dashboard.json"

    def test_demo_text_and_json_never_construct_a_live_monitor_or_write_preferences(self):
        before = set(self.fixture.root.rglob("*"))
        with patch.object(dashboard, "Monitor", side_effect=AssertionError("live monitor in demo")):
            for as_json in (False, True):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(0, dashboard.run_dashboard(self.config, demo_profiles=2,
                                                               json_output=as_json, snapshot=True))
                rendered = output.getvalue()
                self.assertNotIn("\x1b", rendered)
                if as_json:
                    data = json.loads(rendered)
                    self.assertTrue(data["demo"])
                    self.assertEqual(2, len(data["profiles"]))
                else:
                    self.assertIn("DEMO", rendered)
                    self.assertIn("HERDR MANAGED", rendered)
        self.assertEqual(before, set(self.fixture.root.rglob("*")))

    def test_preferences_are_private_atomic_and_only_persist_presentation_settings(self):
        state = ViewState(layout="table", theme="nord", system=False, interval=10,
                          animation=False, filter="private-filter", selected="another", help=True)
        self.assertTrue(dashboard.save_preferences(self.config, state))
        self.assertEqual(0o600, stat.S_IMODE(self.path.stat().st_mode))
        self.assertEqual({"schema": 1, "layout": "table", "theme": "nord", "system": False, "interval": 10,
                          "animation": False},
                         json.loads(self.path.read_text()))
        loaded = dashboard.load_preferences(self.config)
        self.assertEqual(dashboard.preferences(state), dashboard.preferences(loaded))
        self.assertEqual((self.config.profile_id, "", False),
                         (loaded.selected, loaded.filter, loaded.help))
        with patch.object(dashboard.os, "replace", side_effect=OSError("fixture full disk")):
            self.assertFalse(dashboard.save_preferences(self.config, ViewState()))
        self.assertEqual(dashboard.preferences(loaded), json.loads(self.path.read_text()))
        self.assertEqual([], list(self.config.config_dir.glob(".dashboard-*")))

    def test_existing_preferences_keep_settings_and_ignore_obsolete_auto_open(self):
        old = {"schema": 1, "layout": "table", "theme": "nord", "system": False, "interval": 10}
        private_file(self.path, json.dumps(old))
        self.assertEqual(dict(old, animation=True), dashboard.preferences(dashboard.load_preferences(self.config)))
        for value in (False, True, "obsolete"):
            private_file(self.path, json.dumps(dict(old, auto_open=value)))
            self.assertEqual(dict(old, animation=True), dashboard.preferences(dashboard.load_preferences(self.config)))
        private_file(self.path, json.dumps(dict(old, animation="false")))
        self.assertEqual(dashboard.preferences(ViewState()), dashboard.preferences(dashboard.load_preferences(self.config)))

    def test_malformed_or_unsafe_preferences_fall_back_without_overwriting_foreign_files(self):
        baseline = dashboard.preferences(ViewState())
        for raw in ('{"schema":', '{"schema":true}', '{"schema":1,"interval":1e999}', '[]', "x" * 4097):
            private_file(self.path, raw)
            self.assertEqual(baseline, dashboard.preferences(dashboard.load_preferences(self.config)))
        target = self.fixture.root / "preference-target"
        private_file(target, "unchanged")
        self.path.unlink()
        self.path.symlink_to(target)
        self.assertEqual(baseline, dashboard.preferences(dashboard.load_preferences(self.config)))
        self.assertFalse(dashboard.save_preferences(self.config, ViewState()))
        self.assertEqual("unchanged", target.read_text())
        self.path.unlink()
        private_file(self.path, "{}")
        self.path.chmod(0o644)
        self.assertFalse(dashboard.save_preferences(self.config, ViewState()))

    def test_non_tty_cli_prints_one_frame_and_rejects_invalid_dimensions(self):
        argv = [str(ROOT / "bin" / "hermes-gateway-herdr"), "--config", str(self.config.config_dir / "config.json"),
                "dashboard", "--demo-profiles", "20"]
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(b"DEMO", result.stdout)
        self.assertNotIn(b"\x1b", result.stdout)
        self.assertFalse(self.config.state_dir.exists())
        startup = subprocess.run([*argv, "--startup"], stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
        self.assertEqual(0, startup.returncode, startup.stderr)
        self.assertNotIn(b"Open the monitoring dashboard?", startup.stdout)
        self.assertIn(b"SYSTEM", startup.stdout)
        result = subprocess.run([*argv, "--width", "10"], capture_output=True, timeout=3)
        self.assertEqual(20, result.returncode)
        self.assertEqual("INVALID_ARGUMENT", json.loads(result.stdout)["code"])

    def test_display_only_starts_in_an_eligible_tty_with_a_minimal_environment(self):
        with patch("hermes_gateway_herdr.display.subprocess.Popen") as launch:
            self.assertIsNone(Display.start(self.config, {"TERM": "dumb"}))
            with patch("hermes_gateway_herdr.display.sys.stdin.isatty", return_value=False):
                self.assertIsNone(Display.start(self.config, {"TERM": "xterm"}))
            launch.assert_not_called()
        terminal = Terminal()
        self.addCleanup(terminal.close)
        stream = Mock()
        stream.isatty.return_value, stream.fileno.return_value = True, terminal.slave
        process = Mock()
        process.poll.return_value = None
        env = dict(self.fixture.context(), OPENAI_API_KEY="fixture-sentinel", PYTHONPATH="/bad", HERMES_HOME="/wrong", HGH_DASHBOARD="0")
        with patch("hermes_gateway_herdr.display.sys.stdin", stream), patch("hermes_gateway_herdr.display.sys.stdout", stream), \
                patch("hermes_gateway_herdr.display.subprocess.Popen", return_value=process) as launch:
            display = Display.start(self.config, env)
            self.assertIsNotNone(display)
            options = launch.call_args.kwargs
            self.assertTrue(options["close_fds"])
            self.assertFalse(options["start_new_session"])
            self.assertEqual(1, len(options["pass_fds"]))
            self.assertFalse(set(options["env"]) & {"OPENAI_API_KEY", "PYTHONPATH", "HERMES_HOME", "HGH_OWNER_KEY"})
            display.close()
            process.wait.assert_called_once_with(timeout=0.3)


class DashboardTerminalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config
        self.terminal = Terminal()
        self.addCleanup(self.terminal.close)
        self.process = None
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        error = self.process.stderr.read()
        self.process.stderr.close()
        self.assertEqual(b"", error)

    def start(self, *, mode="normal", parent=None):
        if parent is None:
            argv = [str(Path(__file__).with_name("process_fixture.py")), "dashboard",
                    str(self.config.config_dir / "config.json"), mode]
            extra = {}
        else:
            argv = [str(ROOT / "src" / "hermes_gateway_herdr" / "__main__.py"), "--config",
                    str(self.config.config_dir / "config.json"), "dashboard", "--demo-profiles", "2",
                    "--parent-fd", str(parent.fileno())]
            extra = {"pass_fds": (parent.fileno(),)}
        self.process = subprocess.Popen([sys.executable, "-I", "-B", *argv], env=self.fixture.context(),
                                        stdin=self.terminal.slave, stdout=self.terminal.slave,
                                        stderr=subprocess.PIPE, start_new_session=True, **extra)

    def expect(self, text):
        wait_until(lambda: self.terminal.contains(text))

    def samples(self):
        return json_lines(self.fixture.root / "samples.jsonl")

    def frames(self):
        return json_lines(self.fixture.root / "frames.jsonl")

    def quit(self):
        self.terminal.send(b"q")
        # Drain the terminal while its normal teardown writes the last frame.
        wait_until(lambda: self.terminal.read() is not None and self.process.poll() is not None)
        self.assertEqual(0, self.process.returncode)
        self.assertTrue(self.terminal.restored())

    def test_filter_q_is_text_and_standalone_quit_restores_the_terminal(self):
        self.start()
        self.expect("HERDR MANAGED")
        self.terminal.send(b"/quiet\r")
        self.expect("No matching profiles")
        self.assertIsNone(self.process.poll())
        self.terminal.send(b"\x1b")
        time.sleep(1.1)  # A lone ESC is decoded after the terminal's input deadline.
        self.quit()
        self.assertFalse(self.config.state_dir.exists())

    def test_real_keyboard_preferences_resize_and_help(self):
        self.start()
        self.expect("HERDR MANAGED")
        wait_until(lambda: b"\x1b[?1003l\x1b[?1002l\x1b[?1000h\x1b[?1006h" in self.terminal.read())
        self.terminal.send(b"llts--")
        path = self.config.config_dir / "dashboard.json"
        expected = {"schema": 1, "layout": "table", "theme": "nord", "system": False, "interval": 10,
                    "animation": True}
        wait_until(lambda: path.exists() and json.loads(path.read_text()) == expected)
        self.terminal.resize(64, 20)
        self.process.send_signal(signal.SIGWINCH)
        self.terminal.send(b"?")
        self.expect("KEYBOARD")
        self.quit()
        self.assertEqual(expected, json.loads(path.read_text()))

    def test_input_flood_cannot_accelerate_profile_sampling(self):
        self.start()
        self.expect("HERDR MANAGED")
        wait_until(lambda: self.samples())
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            self.terminal.send(b"jkttssaa--++")
            self.terminal.read()
            time.sleep(0.04)
        samples = self.samples()
        self.assertGreaterEqual(len(samples), 2)
        self.assertLessEqual(len(samples), 3)
        for a, b in zip(samples, samples[1:]):
            self.assertGreaterEqual(b["time"] - a["time"], 1.9)
        self.quit()

    def test_focus_loss_slows_sampling_and_focus_return_resumes_it(self):
        self.start(mode="motion")
        self.expect("HERDR MANAGED")
        wait_until(lambda: self.samples())
        self.terminal.send(b"\x1b[O")
        time.sleep(0.4)
        frames = len(self.frames())
        time.sleep(1.8)
        self.assertEqual(frames, len(self.frames()))
        self.assertEqual(1, len(self.samples()))
        self.terminal.send(b"\x1b[I")
        wait_until(lambda: len(self.samples()) == 2)
        self.quit()

    def test_animation_does_not_sample_and_static_mode_stops_its_frames(self):
        path = self.config.config_dir / "dashboard.json"
        private_file(path, json.dumps(dashboard.preferences(ViewState(interval=10))))
        self.start(mode="motion")
        self.expect("HERDR MANAGED")
        wait_until(lambda: len(self.frames()) >= 5, timeout=3)
        self.assertEqual(1, len(self.samples()))
        self.terminal.send(b"a")
        wait_until(lambda: json.loads(path.read_text())["animation"] is False)
        time.sleep(0.4)
        frames = len(self.frames())
        time.sleep(0.8)
        self.assertEqual(frames, len(self.frames()))
        self.terminal.send(b"a")
        wait_until(lambda: len(self.frames()) >= frames + 3, timeout=2)
        self.assertEqual(1, len(self.samples()))
        self.quit()

    def test_collector_exception_is_visible_and_does_not_crash_the_view(self):
        self.start(mode="error")
        self.expect("HERDR MANAGED")
        self.expect("Monitoring unavailable")
        self.expect("COLLECTOR_UNAVAILABLE")
        self.assertIsNone(self.process.poll())
        self.quit()

    def test_startup_always_opens_full_dashboard_even_with_legacy_auto_open_false(self):
        path = self.config.config_dir / "dashboard.json"
        old = dict(dashboard.preferences(ViewState()), auto_open=False)
        private_file(path, json.dumps(old))
        self.start(mode="startup")
        self.expect("SYSTEM")
        wait_until(lambda: self.samples())
        self.assertTrue(all(not s["managed_only"] and s["host"] for s in self.samples()))
        self.assertFalse(self.terminal.contains("Open the monitoring dashboard?"))
        self.assertFalse(self.terminal.contains("Always open on startup"))
        self.assertEqual(old, json.loads(path.read_text()))
        self.quit()

    def test_embedded_mouse_buttons_send_start_and_pause_to_the_private_parent_channel(self):
        from hqtui import render_to_screen
        parent, child = socket.socketpair()
        self.addCleanup(parent.close)
        self.addCleanup(child.close)
        self.start(parent=child)
        child.close()
        self.expect("Start [Enter]")
        self.expect("SYSTEM")
        view = DashboardView(ViewState(), embedded=True, demo=True)
        screen = render_to_screen(120, 36, theme_for("herdr"), lambda ui: view.render(ui, dashboard.demo_snapshot(2)))
        buttons = [hit.rect for hit in screen.regions if hit.on_click]
        self.assertEqual(2, len(buttons))
        parent.settimeout(2)
        for rect, expected in zip(buttons, (b"s", b"p")):
            self.terminal.send(f"\x1b[<0;{rect.x + 1};{rect.y + 1}M\x1b[<0;{rect.x + 1};{rect.y + 1}m".encode())
            self.assertEqual(expected, parent.recv(1))
        self.assertIsNone(self.process.poll())
        self.assertFalse(self.config.state_dir.exists())

    def test_unsaved_preferences_report_failure_without_overwriting_foreign_file(self):
        path = self.config.config_dir / "dashboard.json"
        target = self.fixture.root / "foreign-preferences"
        private_file(target, "unchanged")
        path.symlink_to(target)
        self.start(mode="startup")
        self.expect("SYSTEM")
        self.terminal.send(b"t")
        self.expect("Could not save preferences.")
        self.assertEqual("unchanged", target.read_text())
        self.quit()

    def test_embedded_keyboard_controls_keep_dashboard_open_and_only_use_private_parent_channel(self):
        parent, child = socket.socketpair()
        self.addCleanup(parent.close)
        self.addCleanup(child.close)
        self.start(parent=child)
        child.close()
        self.expect("HERDR MANAGED")
        self.expect("SYSTEM")
        self.assertFalse(self.terminal.contains("Open the monitoring dashboard?"))
        self.terminal.send(b"\r")
        parent.settimeout(2)
        self.assertEqual(b"s", parent.recv(1))
        self.terminal.send(b"q")
        parent.settimeout(0.05)
        with self.assertRaises(TimeoutError):
            parent.recv(1)
        self.assertIsNone(self.process.poll())
        self.terminal.send(b"\x03")
        parent.settimeout(2)
        self.assertEqual(b"p", parent.recv(1))
        self.assertIsNone(self.process.poll())
        before = time.monotonic()
        parent.close()
        self.assertEqual(0, self.process.wait(timeout=2))
        self.assertLess(time.monotonic() - before, 1)
        self.assertTrue(self.terminal.restored())

    def test_parent_eof_exits_even_when_terminal_output_is_blocked(self):
        self.terminal.resize(300, 100)
        self.terminal.stop_draining()
        parent, child = socket.socketpair()
        self.addCleanup(parent.close)
        self.addCleanup(child.close)
        self.start(parent=child)
        child.close()
        # Never read the master: even entering raw mode can wait for TTY output.
        wait_until(lambda: select.select([self.terminal.master], [], [], 0)[0])
        time.sleep(0.15)
        self.assertIsNone(self.process.poll())
        before = time.monotonic()
        parent.close()
        self.assertEqual(0, self.process.wait(timeout=2))
        self.assertLess(time.monotonic() - before, 1)
        self.assertTrue(self.terminal.restored())
