"""Responsive hqtui view. Rendering only consumes immutable telemetry snapshots."""

from dataclasses import dataclass
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vendor" / "hqtui"))

from hqtui import Layout, Panel, ScrollHandlers
from hqtui.color import Color
from hqtui.graphics import PlotOptions
from hqtui.theme import define_theme, resolve_theme
from hqtui.widgets.table import resolve_offset
import hqtui.widgets as w

from .monitor import Profile, text

THEMES = ("herdr", "nord", "high-contrast", "monochrome")
LAYOUTS = ("auto", "cards", "table")
INTERVALS = (2, 5, 10)
HERDR_THEME = define_theme(name="herdr", background=Color.hex(0x080C12), surface=Color.hex(0x0C131D),
                           muted=Color.hex(0x8092A6), border=Color.hex(0x263549),
                           title=Color.hex(0x7BDDE8), accent=Color.hex(0xE9BA73),
                           selection=Color.hex(0x20384B), warning=Color.hex(0xE9BA73))


def theme_for(name):
    return HERDR_THEME if name == "herdr" else resolve_theme(name)


def amount(value):
    if value is None:
        return "--"
    for divisor, unit in ((1073741824, "GiB"), (1048576, "MiB"), (1024, "KiB")):
        if value >= divisor:
            return f"{value / divisor:.1f} {unit}"
    return f"{value} B"


def percent(value):
    return "--" if value is None else f"{value:.1f}%"


def duration(seconds):
    seconds = max(0, int(seconds))
    if seconds >= 86400:
        return f"{seconds // 86400}d {seconds % 86400 // 3600:02}h"
    return f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"


def state_of(profile, now, interval, count):
    if profile.observed <= 0:
        return "SCANNING"
    # Background profiles are intentionally sampled over a bounded round-robin cycle.
    max_age = max(10, interval * 3) if profile.managed else max(15, interval * (count + 2))
    return "STALE" if now - profile.observed > max_age else profile.state


def state_color(state, theme):
    if state in {"READY", "RUNNING", "SHARED"}:
        return theme.success
    if state in {"UNKNOWN", "STALE", "DEGRADED", "FUSED", "ORPHAN"}:
        return theme.warning if state != "FUSED" else theme.danger
    return theme.muted if state in {"STOPPED", "PAUSED", "ABSENT", "DISABLED"} else theme.info


@dataclass
class ViewState:
    selected: str = ""
    layout: str = "auto"
    theme: str = "herdr"
    system: bool = True
    interval: int = 2
    filter: str = ""
    filtering: bool = False
    help: bool = False
    quiet: bool = False

    def rows(self, snapshot):
        return [p for p in snapshot.profiles if self.filter.lower() in p.name.lower()]

    def move(self, snapshot, delta):
        rows = self.rows(snapshot)
        if rows:
            index = next((i for i, p in enumerate(rows) if p.name == self.selected), 0)
            self.selected = rows[max(0, min(len(rows) - 1, index + delta))].name

    def key(self, event, snapshot):
        if self.filtering:
            if event.name in {"enter", "escape"}:
                self.filtering = False
            elif event.name == "backspace":
                self.filter = self.filter[:-1]
            elif event.char and event.char.isprintable() and not event.ctrl:
                self.filter = (self.filter + event.char)[:64]
            return
        if event.name in {"j", "down", "k", "up", "pagedown", "pageup"}:
            self.move(snapshot, {"j": 1, "down": 1, "k": -1, "up": -1, "pagedown": 8, "pageup": -8}[event.name])
        elif event.name == "home":
            self.move(snapshot, -len(snapshot.profiles))
        elif event.name == "end":
            self.move(snapshot, len(snapshot.profiles))
        elif event.name == "l":
            self.layout = LAYOUTS[(LAYOUTS.index(self.layout) + 1) % len(LAYOUTS)]
        elif event.name == "t":
            self.theme = THEMES[(THEMES.index(self.theme) + 1) % len(THEMES)]
        elif event.name == "s":
            self.system = not self.system
        elif event.name in {"+", "=", "-"}:
            index = INTERVALS.index(self.interval) + (-1 if event.name in {"+", "="} else 1)
            self.interval = INTERVALS[max(0, min(len(INTERVALS) - 1, index))]
        elif event.name == "/":
            self.filtering = True
        elif event.name == "escape":
            self.filter, self.help = "", False
        elif event.name in {"?", "f1"}:
            self.help = not self.help


class DashboardView:
    def __init__(self, state, *, session="default", embedded=False, demo=False):
        self.state, self.session, self.embedded, self.demo = state, text(session, 80), embedded, demo

    def render(self, ui, snapshot, *, now=None):
        now = time.time() if now is None else now
        state = self.state
        rows = state.rows(snapshot)
        owned = next((p for p in snapshot.profiles if p.managed), None)
        if owned is None:
            owned = Profile("Gateway", Path("/"), managed=True, error="Waiting for discovery")
        selected = next((p for p in rows if p.name == state.selected), rows[0] if rows else owned)
        count = len(snapshot.profiles)
        self._now, self._count = now, count
        width, height, theme = ui.width, ui.height, ui.theme
        healthy = sum(state_of(p, now, state.interval, count) in {"READY", "RUNNING", "SHARED"} for p in snapshot.profiles)

        def header(r):
            r.text(" HERMES", w.TextStyle(fg=theme.title, bold=True), Layout(size=9))
            r.text(" CONTROL", w.TextStyle(fg=theme.accent), Layout(size=9))
            r.text(f"  {healthy}/{count} online", w.TextStyle(fg=theme.muted), Layout(size=16))
            if width >= 90:
                r.text(f"{self.session} / local gateways", w.TextStyle(fg=theme.muted))
            r.text("DEMO " if self.demo else f"LIVE / {state.interval}s ",
                   w.TextStyle(fg=theme.warning if self.demo else theme.success, align="right"), Layout(size=12))
        ui.row(Layout(size=1, background=theme.surface), header)
        if height < 10 or width < 36:
            ui.text(f"{text(owned.name)} [HERDR] {self._status(owned)}")
            ui.label(f"{count} profiles / expand pane for details")
            return
        if state.quiet:
            ui.spacer(1)
            ui.heading(f" {text(owned.name)} / {self._status(owned)}")
            ui.label(" Dashboard hidden. Gateway supervision continues.")
            ui.label(" Press q to return to the dashboard.")
            ui.spacer()
            self._footer(ui)
            return
        ui.spacer(1)
        compact = width < 100 or height < 30
        hero_height = 8 if compact else min(17, max(12, height // 2 - 2))
        if count == 1 and not compact and not state.help and state.layout != "table":
            def single(r):
                self._profile_panel(r, owned, hero=True, size="2fr")
                def side(c):
                    if state.system:
                        self._system(c, snapshot, size=min(17, height // 2 - 2))
                        c.spacer(1)
                    c.panel(Panel(title=" ACTIVITY ", background=c.theme.surface), lambda p: self._activity_content(p, snapshot))
                r.column(Layout(size="1fr"), side)
            ui.row(Layout(gap=1), single)
            ui.spacer(1)
            self._footer(ui)
            return
        if state.help:
            self._help(ui)
        else:
            def top(r):
                self._profile_panel(r, owned, hero=True, size="2fr" if state.system and not compact else None)
                if state.system and not compact:
                    self._system(r, snapshot)
            ui.row(Layout(size=min(hero_height, max(5, height - 9)), gap=1), top)
            ui.spacer(1)
            if state.filter or state.filtering:
                ui.text(f" Filter: /{text(state.filter, 64)}{'_' if state.filtering else ''}  ({len(rows)}/{count})",
                        w.TextStyle(fg=theme.accent))
            mode = "cards" if state.layout == "cards" or (state.layout == "auto" and count <= 2) else "table"
            if compact:
                mode = "table"
            if mode == "cards" and rows:
                self._cards(ui, rows, selected, snapshot)
            else:
                def bottom(r):
                    self._table(r, rows, selected, snapshot, size="3fr" if not compact else None)
                    if not compact:
                        def details(p):
                            self._profile_content(p, selected, graphs=False)
                            if p.height >= 12:
                                p.spacer(1)
                                self._activity_content(p, snapshot)
                        r.panel(Panel(title=" INSPECT / " + text(selected.name), size="2fr",
                                      background=theme.surface), details)
                ui.row(Layout(gap=1), bottom)
            if compact and state.system and height >= 24:
                ui.text(f" Host CPU {percent(snapshot.host_cpu)}  RAM {amount(snapshot.host_used)} / {amount(snapshot.host_total)}",
                        w.TextStyle(fg=theme.muted))
        ui.spacer(1)
        self._footer(ui)

    def _status(self, profile):
        return state_of(profile, self._now, self.state.interval, self._count)

    def _profile_panel(self, ui, profile, *, hero=False, size=None):
        theme = ui.theme
        label = f" {text(profile.name)} {' / HERDR MANAGED' if profile.managed else '/ GATEWAY'} "
        ui.panel(Panel(title=label, subtitle=" PINNED " if hero else "", size=size,
                       border_color=theme.accent if profile.managed else theme.border,
                       title_color=theme.accent if profile.managed else theme.title,
                       subtitle_color=theme.accent, background=theme.surface),
                 lambda p: self._profile_content(p, profile, graphs=True))

    def _profile_content(self, p, profile, *, graphs=False):
        theme, status = p.theme, self._status(profile)
        usable = status not in {"STALE", "UNKNOWN", "SCANNING"}
        cpu, rss, active = (profile.cpu, profile.rss, profile.active) if usable else (None, None, None)
        def headline(r):
            r.text(status, w.TextStyle(fg=state_color(status, theme), bold=True), Layout(size=12))
            hint = f"{active} active" if active is not None else "activity --"
            r.text(hint, w.TextStyle(fg=theme.foreground))
            age = f"seen {max(0, int(self._now - profile.observed))}s ago" if profile.observed else "pending sample"
            r.text(age, w.TextStyle(fg=theme.muted, align="right"), Layout(size=18))
        p.row(Layout(size=1), headline)
        links = "  /  ".join(f"{name} {value}" for name, value in profile.platforms) if usable else "Connection status unavailable"
        if profile.shared_from:
            links = f"Shared Gateway via {profile.shared_from}; metrics belong to that process"
        p.text(text(links or "No live platform data", 200), w.TextStyle(fg=theme.info if usable else theme.muted))
        up = duration(self._now - profile.started) if profile.started and usable else "--"
        p.label(f"PID {profile.pid or '--'}   up {up}   {profile.pane or profile.supervision}")
        if p.height >= 6:
            p.spacer(1)
        p.text(f"CPU {percent(cpu):>7}    RSS {amount(rss):>10}    Agents {active if active is not None else '--'}",
               w.TextStyle(fg=theme.foreground, bold=True))
        if profile.error:
            p.text(text(profile.error), w.TextStyle(fg=theme.warning))
        if graphs and p.height >= 10:
            p.spacer(1)
            def plots(r):
                self._graph(r, "CPU / one core", profile.cpu_history, theme.success, upper=10)
                self._graph(r, "RSS / MiB", profile.memory_history, theme.secondary)
            p.row(Layout(gap=2), plots)
        elif p.height >= 8:
            p.spacer(1)
            p.label("Lifecycle: Herdr plugin actions" if profile.managed else "Lifecycle: external to this plugin")

    def _graph(self, ui, label, values, color, *, upper=None):
        def content(p):
            p.text(label, w.TextStyle(fg=p.theme.muted))
            if len(values) < 2:
                p.label("Collecting samples..." if not values else "Waiting for next sample...")
                return
            minimum = 0 if upper else max(0, math.floor(min(values) * .95))
            maximum = max(upper or 1, math.ceil(max(values) / 10) * 10)
            mode = "braille" if p.capabilities.braille else "ascii"
            p.graph(w.GraphOptions(values=values[-90:], plot=PlotOptions(min=minimum, max=maximum, color=color,
                                                                       fill=upper is not None, fill_alpha=.15, mode=mode),
                                   axis=True, axis_format=lambda v: f"{v:.0f}"))
        ui.column(Layout(), content)

    def _system(self, ui, snapshot, *, size="1fr"):
        def content(p):
            p.text("HOST / CPU", w.TextStyle(fg=p.theme.muted))
            if snapshot.host_cpu is not None:
                p.meter(w.MeterOptions(value=snapshot.host_cpu / 100, text=percent(snapshot.host_cpu), color=p.theme.success))
            else:
                p.label("CPU -- / waiting for sample")
            p.spacer(1)
            p.text(f"MEMORY  {amount(snapshot.host_used)} / {amount(snapshot.host_total)}")
            if snapshot.host_total:
                p.meter(w.MeterOptions(value=snapshot.host_used / snapshot.host_total, color=p.theme.primary))
            if p.height >= 10:
                p.spacer(1)
                self._graph(p, "Host CPU / recent samples", snapshot.host_history, p.theme.success, upper=100)
            p.label(f"sample {self.state.interval}s / discovery 30s")
        ui.panel(Panel(title=" SYSTEM ", subtitle=" LIGHTWEIGHT ", size=size, background=ui.theme.surface), content)

    def _cards(self, ui, rows, selected, snapshot):
        others = [p for p in rows if not p.managed]
        if not others:
            ui.panel(Panel(title=" ACTIVITY ", background=ui.theme.surface), lambda p: self._activity_content(p, snapshot))
            return
        index = next((i for i, p in enumerate(others) if p.name == selected.name), 0)
        # Cards page through a fleet rather than shrinking every profile into an unreadable tile.
        visible = others[(index // 2) * 2:(index // 2) * 2 + 2]
        def cards(r):
            for profile in visible:
                self._profile_panel(r, profile, size="2fr" if len(visible) == 1 else None)
            if len(visible) == 1:
                r.panel(Panel(title=" ACTIVITY ", size="1fr", background=r.theme.surface), lambda p: self._activity_content(p, snapshot))
        ui.row(Layout(gap=1), cards)

    def _table(self, ui, rows, selected, snapshot, *, size=None):
        def content(p):
            if not rows:
                p.label("No matching profiles. Esc clears the filter.")
                return
            columns = [w.TableColumn("PROFILE", width="2fr"), w.TableColumn("GATEWAY", width=11),
                       w.TableColumn("CPU", width=7, align="right"), w.TableColumn("RSS", width=10, align="right")]
            if p.width >= 70:
                columns += [w.TableColumn("AGENTS", width=6, align="right"), w.TableColumn("SOURCE", width=10),
                            w.TableColumn("SEEN", width=6, align="right")]
            if p.width < 50:
                columns = columns[:2]
            selected_index = next((i for i, item in enumerate(rows) if item.name == selected.name), 0)
            offset = resolve_offset(None, selected_index, max(0, p.height - 1), len(rows), True)
            table_rows = []
            for profile in rows:
                status = self._status(profile)
                live = status not in {"STALE", "UNKNOWN", "SCANNING"}
                cells = [f"{'* ' if profile.managed else '  '}{text(profile.name)}", status,
                         percent(profile.cpu if live else None), amount(profile.rss if live else None)]
                cells += [str(profile.active) if live and profile.active is not None else "--",
                          "HERDR" if profile.managed else profile.shared_from or profile.supervision,
                          f"{max(0, int(self._now - profile.observed))}s" if profile.observed else "--"]
                table_rows.append(w.TableRow(cells[:len(columns)], cell_colors=(p.theme.accent if profile.managed else p.theme.foreground,
                                                                               state_color(status, p.theme))))
            def choose(row):
                if offset + row < len(rows):
                    self.state.selected = rows[offset + row].name
            p.table(w.TableOptions(rows=table_rows, columns=columns, selected=selected_index, offset=offset,
                                    zebra=True, scrollbar=True),
                    ScrollHandlers(on_scroll=lambda delta: self.state.move(snapshot, delta), on_select_row=choose))
        ui.panel(Panel(title=f" PROFILES / {len(rows)} ", subtitle=" * HERDR ", size=size,
                       background=ui.theme.surface), content)

    def _activity_content(self, p, snapshot):
        p.label("OBSERVED STATE CHANGES")
        p.spacer(1)
        if not snapshot.events:
            p.label("Waiting for the first sample...")
        for stamp, name, state, code in snapshot.events[-max(1, p.height - 4):]:
            clock = time.strftime("%H:%M:%S", time.localtime(stamp))
            p.text(f"{clock}  {text(name, 24):<16} {text(state, 14)} {text(code, 32)}",
                   w.TextStyle(fg=state_color(state, p.theme)))
        p.spacer()
        p.label("Metadata only / message contents stay private")

    def _footer(self, ui):
        items = [w.StatusItem("Help", "?"), w.StatusItem("Layout", "l"), w.StatusItem("Theme", "t"),
                 w.StatusItem("System", "s"), w.StatusItem("Select", "j/k"), w.StatusItem("Filter", "/")]
        if ui.width >= 110:
            items.extend([w.StatusItem("Rate", "+/-"), w.StatusItem("Hide" if self.embedded else "Quit", "q")])
        ui.status_bar(w.StatusBarOptions(items=items, right=[w.StatusItem(f"{self.state.layout} / {self.state.interval}s")]))

    def _help(self, ui):
        def content(p):
            p.heading("HERMES CONTROL / KEYBOARD")
            for line in ("j / k, arrows     Select a profile", "PgUp / PgDn       Move through a larger fleet",
                         "Home / End        First / last profile", "/, then Enter     Filter profile names; Esc clears",
                         "l                 Layout: auto / cards / table", "t                 Theme: herdr / nord / high-contrast / monochrome",
                         "s                 Toggle lightweight system sampling", "+ / -             Sample faster / slower: 2s / 5s / 10s",
                         "q                 Hide / show this view" if self.embedded else "q / Ctrl+C        Close the monitor",
                         "Ctrl+C            Pause the managed Gateway" if self.embedded else "",
                         "", "The pinned profile belongs to Herdr. Other profiles are observed only.",
                         "CPU is per Gateway process (100% = one core); RSS excludes descendants.",
                         "SHARED means another Gateway serves that profile; resources are not duplicated.",
                         "Graphs keep 90 observed samples. Background profiles are sampled in rotation."):
                p.text(line)
        ui.panel(Panel(title=" HELP / ? or Esc to close ", background=ui.theme.surface), content)
