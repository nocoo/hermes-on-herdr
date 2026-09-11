from dataclasses import replace
import hashlib
import json
from pathlib import Path
from unittest import TestCase

from hermes_gateway_herdr.dashboard_demo import demo_snapshot
from hermes_gateway_herdr.dashboard_view import DashboardView, ViewState, theme_for
from hqtui import render_to_screen
from hqtui.input import KeyEvent


class DashboardViewTests(TestCase):
    def render(self, count=2, width=160, height=44, *, state=None, data=None, now=None, embedded=False):
        data = data or demo_snapshot(count)
        state = state or ViewState(selected="cherry")
        view = DashboardView(state, demo=True, embedded=embedded)
        return render_to_screen(width, height, theme_for(state.theme),
                                lambda ui: view.render(ui, data, now=now or data.updated))

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
        self.assertLess(y, 4)
        self.assertEqual(screen.cell(x, y).fg, theme_for(state.theme).accent)

    def test_layouts_remain_usable_at_narrow_and_short_terminal_sizes(self):
        for count in (1, 2, 25):
            for width, height in ((24, 10), (40, 16), (64, 20), (80, 24), (100, 30), (160, 44)):
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
                                (ViewState(help=True), "HERMES CONTROL / KEYBOARD")):
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
        self.assertGreater(narrow.find("DEMO")[0], 70)
        standalone = self.render(state=ViewState(help=True))
        embedded = self.render(state=ViewState(help=True), embedded=True)
        self.assertTrue(standalone.contains("Close the monitor"))
        self.assertTrue(embedded.contains("Pause the managed Gateway"))
