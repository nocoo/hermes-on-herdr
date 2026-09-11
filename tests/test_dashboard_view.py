from dataclasses import replace
import hashlib
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from hermes_gateway_herdr.dashboard_demo import demo_snapshot
from hermes_gateway_herdr.dashboard_view import CADUCEUS, DashboardView, ViewState, mascot_pose, theme_for
from hqtui import render_to_screen
from hqtui.input import KeyEvent


class DashboardViewTests(TestCase):
    def render(self, count=2, width=160, height=44, *, state=None, data=None, now=None, embedded=False, pose=0):
        data = data or demo_snapshot(count)
        state = state or ViewState(selected="cherry")
        view = DashboardView(state, demo=True, embedded=embedded)
        return render_to_screen(width, height, theme_for(state.theme),
                                lambda ui: view.render(ui, data, now=now or data.updated, pose=pose))

    def test_uses_the_unmodified_pinned_hqtui_library(self):
        root = Path(__file__).resolve().parents[1] / "vendor" / "hqtui"
        origin = json.loads((root / "ORIGIN.json").read_text())
        for name, expected in origin["sha256"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected, name)

    def test_small_profile_counts_use_cards_and_larger_fleets_use_a_table(self):
        for count in (1, 2):
            screen = self.render(count)
            self.assertTrue(screen.contains("ACTIVITY"))
            self.assertFalse(screen.contains("PROFILES /"))
            self.assertTrue(screen.contains("CPU / one core"))
        screen = self.render(20)
        self.assertTrue(screen.contains("PROFILES / 20"))
        self.assertTrue(screen.contains("INSPECT / cherry"))

    def test_pinned_profile_remains_prominent_even_when_selecting_or_filtering_another(self):
        state = ViewState(selected="agent-12", filter="agent-12")
        screen = self.render(20, state=state)
        self.assertTrue(screen.contains("cherry  / HERDR MANAGED"))
        self.assertTrue(screen.contains("INSPECT / agent-12"))
        x, y = screen.find("cherry")
        self.assertLess(y, 8)
        self.assertEqual(screen.cell(x, y).fg, theme_for(state.theme).accent)

    def test_layouts_remain_usable_at_narrow_and_short_terminal_sizes(self):
        for count in (1, 2, 25):
            for width, height in ((24, 10), (40, 16), (64, 20), (80, 24), (99, 34),
                                  (100, 30), (100, 33), (100, 34), (131, 64), (160, 44)):
                with self.subTest(count=count, width=width, height=height):
                    screen = self.render(count, width, height)
                    self.assertEqual(len(screen.text().split("\n")), height)
                    self.assertTrue(screen.contains("cherry"))
                    if width >= 40:
                        self.assertTrue(screen.contains("Help"))
                        self.assertTrue(screen.contains("READY"))
                    for hit in screen.regions:
                        self.assertGreaterEqual(hit.rect.x, 0)
                        self.assertLessEqual(hit.rect.x + hit.rect.width, width)
                        self.assertLessEqual(hit.rect.y + hit.rect.height, height)

    def test_end_selection_and_clicks_use_the_scrolled_row_not_the_first_page(self):
        data = demo_snapshot(100)
        state = ViewState(selected="cherry")
        state.key(KeyEvent("end", "end"), data)
        self.assertEqual(state.selected, "agent-99")
        screen = self.render(100, 80, 24, state=state, data=data)
        self.assertTrue(screen.contains("agent-99"))
        table = next(hit for hit in screen.regions if hit.on_click)
        table.on_click(1, table.rect.height - 1, "left")
        self.assertEqual(state.selected, "agent-99")

    def test_filter_editing_does_not_trigger_shortcuts_and_selection_survives_reordering(self):
        data = demo_snapshot(20)
        state = ViewState(selected="agent-12")
        state.key(KeyEvent("/", "/"), data)
        for char in "agent-12":
            state.key(KeyEvent(char, char, char=char), data)
        self.assertEqual((state.filter, state.theme, state.layout), ("agent-12", "herdr", "auto"))
        state.key(KeyEvent("enter", "enter"), data)
        shuffled = replace(data, profiles=tuple(reversed(data.profiles)))
        self.assertTrue(self.render(20, state=state, data=shuffled).contains("INSPECT / agent-12"))
        state.key(KeyEvent("escape", "escape"), data)
        self.assertEqual(state.filter, "")

    def test_old_observations_never_display_ready_or_connected_or_live_resource_values(self):
        data = demo_snapshot(2)
        screen = self.render(data=data, now=data.updated + 120)
        self.assertTrue(screen.contains("STALE"))
        self.assertTrue(screen.contains("0/2 online"))
        self.assertFalse(screen.contains("discord connected"))
        self.assertFalse(screen.contains("149.3 MiB"))

    def test_single_profile_filter_and_collector_error_are_visible(self):
        self.assertTrue(self.render(1, state=ViewState(filter="no-match")).contains("No matching profiles"))
        self.assertTrue(self.render(1, state=ViewState(filtering=True)).contains("Filter: /_"))
        data = replace(demo_snapshot(1), error="COLLECTOR_UNAVAILABLE")
        self.assertTrue(self.render(data=data).contains("Monitoring unavailable"))

    def test_layout_theme_rate_and_system_controls_change_the_actual_view(self):
        data = demo_snapshot(2)
        state = ViewState(selected="cherry")
        for key in ("l", "l", "t", "s", "-"):
            state.key(KeyEvent(key, key), data)
        screen = self.render(state=state, data=data)
        self.assertEqual((state.layout, state.theme, state.system, state.interval), ("table", "nord", False, 5))
        self.assertTrue(screen.contains("PROFILES / 2"))
        self.assertFalse(screen.contains("LIGHTWEIGHT"))
        self.assertTrue(screen.contains("table / 5s"))

    def test_many_profile_cards_page_to_selected_profile_without_losing_the_pin(self):
        state = ViewState(selected="agent-49", layout="cards")
        screen = self.render(50, state=state)
        self.assertTrue(screen.contains("agent-49"))
        self.assertTrue(screen.contains("HERDR MANAGED"))
        self.assertFalse(screen.contains("agent-02"))

    def test_empty_filter_quiet_help_and_unavailable_states_have_clear_output(self):
        for state, expected in ((ViewState(filter="no-match"), "No matching profiles"),
                                (ViewState(quiet=True), "supervision continues"),
                                (ViewState(help=True), "hermes on herdr / KEYBOARD")):
            self.assertTrue(self.render(20, state=state).contains(expected))
        data = demo_snapshot(1)
        bad = replace(data.profiles[0], state="UNKNOWN", observed=data.updated, cpu=None, rss=None,
                      platforms=(), error="OWNER_UNAVAILABLE")
        screen = self.render(data=replace(data, profiles=(bad,)))
        self.assertTrue(screen.contains("OWNER_UNAVAILABLE"))
        self.assertFalse(screen.contains("discord connected"))

    def test_demo_marker_and_stop_semantics_are_visible(self):
        self.assertTrue(self.render().contains("DEMO"))
        narrow = self.render(width=80, height=24, embedded=True)
        self.assertTrue(narrow.contains("Hide"))
        self.assertEqual(narrow.find("DEMO")[1], narrow.height - 1)
        standalone = self.render(state=ViewState(help=True))
        embedded = self.render(state=ViewState(help=True), embedded=True)
        self.assertTrue(standalone.contains("Close the monitor"))
        self.assertTrue(embedded.contains("Pause the managed Gateway"))

    def test_caduceus_is_intact_above_system_without_a_separate_header(self):
        for count in (1, 2, 25):
            for width, height in ((100, 34), (131, 64), (160, 44)):
                with self.subTest(count=count, width=width, height=height):
                    screen = self.render(count, width, height)
                    self.assertEqual(screen.find("HERDR MANAGED")[1], 0)
                    self.assertEqual(screen.find("hermes on herdr")[1], 0)
                    x, y = screen.find(CADUCEUS[2])
                    self.assertGreater(x, width // 2)
                    for offset, line in enumerate(CADUCEUS):
                        actual = "".join(screen.cell(x + i, y - 2 + offset).char for i in range(len(line)))
                        self.assertEqual(line, actual)
                    self.assertGreater(screen.find("SYSTEM")[1], y - 2 + len(CADUCEUS))
                    self.assertFalse(screen.contains("TALARIA"))

    def test_animation_changes_only_art_colors_and_preserves_every_glyph(self):
        data = demo_snapshot(2)
        still = self.render(data=data)
        self.assertTrue(still.contains("hermes on herdr"))
        x0, y0 = still.find(CADUCEUS[2])
        for pose in (1, 2):
            animated = self.render(data=data, pose=pose)
            changed = [(x, y) for y in range(still.height) for x in range(still.width)
                       if still.cell(x, y) != animated.cell(x, y)]
            self.assertGreater(len(changed), 0)
            self.assertLessEqual(len(changed), sum(map(len, CADUCEUS)))
            self.assertTrue(all(x0 <= x < x0 + len(CADUCEUS[2]) and y0 - 2 <= y < y0 - 2 + len(CADUCEUS)
                                for x, y in changed))
            self.assertEqual(still.text(), animated.text())
        for width, height in ((80, 24), (160, 30)):
            self.assertEqual(self.render(width=width, height=height, data=data).text(),
                             self.render(width=width, height=height, data=data, pose=1).text())

    def test_static_motion_preference_and_help_keep_the_view_still(self):
        data = demo_snapshot(2)
        state = ViewState()
        state.key(KeyEvent("a", "a"), data)
        self.assertFalse(state.animation)
        self.assertEqual(self.render(state=state, data=data).buffer.fg,
                         self.render(state=state, data=data, pose=1).buffer.fg)
        self.assertTrue(self.render(state=state).contains("Motion off"))
        state.help = True
        self.assertTrue(self.render(state=state).contains("Toggle the caduceus glow"))

    def test_animation_sleeps_through_its_rest_and_repeats_without_drift(self):
        self.assertEqual((0, 0.25), mascot_pose(0))
        self.assertEqual((1, 0.25), mascot_pose(0.25))
        self.assertEqual((2, 0.25), mascot_pose(0.75))
        self.assertEqual((0, 10), mascot_pose(2))
        self.assertEqual((0, 4), mascot_pose(8))
        self.assertEqual(mascot_pose(0.25), mascot_pose(1200.25))

    def test_animation_reuses_the_view_and_preserves_clicks_themes_and_resizing(self):
        data = demo_snapshot(50)
        state = ViewState(selected="cherry")
        view = DashboardView(state, demo=True)
        def draw(width=160, height=44, pose=0):
            return render_to_screen(width, height, theme_for(state.theme),
                                    lambda ui: view.render(ui, data, now=data.updated, pose=pose))
        draw()
        with patch.object(view, "_content", side_effect=AssertionError("Rebuilt profiles during a glow frame")):
            cached = draw(pose=1)
        table = next(hit for hit in cached.regions if hit.on_click)
        table.on_click(1, 2, "left")
        self.assertNotEqual("cherry", state.selected)
        self.assertTrue(draw().contains("INSPECT / " + state.selected))
        for width, height, theme in ((80, 24, "nord"), (100, 34, "monochrome"), (160, 44, "herdr")):
            state.theme = theme
            actual = draw(width, height, pose=2)
            fresh = self.render(50, width, height, state=state, data=data, pose=2)
            for field in ("chars", "fg", "bg", "attrs"):
                self.assertEqual(getattr(fresh.buffer, field), getattr(actual.buffer, field))

    def test_cached_views_refresh_new_telemetry_and_expire_old_status(self):
        data = demo_snapshot(1)
        view = DashboardView(ViewState(), demo=True)
        def draw(snapshot, now):
            return render_to_screen(160, 44, theme_for("herdr"),
                                    lambda ui: view.render(ui, snapshot, now=now))
        draw(data, data.updated)
        changed = replace(data, profiles=(replace(data.profiles[0], state="DEGRADED", rss=42 * 1048576),))
        current = draw(changed, data.updated)
        self.assertTrue(current.contains("DEGRADED"))
        self.assertTrue(current.contains("42.0 MiB"))
        expired = draw(changed, data.updated + 120)
        self.assertTrue(expired.contains("STALE"))
        self.assertFalse(expired.contains("discord connected"))
        self.assertFalse(expired.contains("42.0 MiB"))
        self.assertTrue(draw(changed, data.updated).contains("DEGRADED"))
