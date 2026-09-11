"""Export an actual hqtui framebuffer using deterministic, offline demo profiles."""

import argparse
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hermes_gateway_herdr.dashboard_demo import demo_snapshot
from hermes_gateway_herdr.dashboard_view import DashboardView, ViewState, theme_for
from hqtui import render_to_screen
from hqtui.buffer import Attrs


def fixed_cell_html(screen):
    """Like a real terminal, fallback fonts cannot change a glyph's cell width."""
    cells = []
    for y in range(screen.height):
        for x in range(screen.width):
            cell = screen.cell(x, y)
            if not cell.char:
                continue
            style = (f"left:{x * 9}px;top:{y * 18}px;color:#{cell.fg & 0xffffff:06x};"
                     f"background:#{cell.bg & 0xffffff:06x};font-weight:{700 if cell.attrs & Attrs.BOLD else 400}")
            cells.append(f'<span style="{style}">{escape(cell.char)}</span>')
    return ("<!doctype html><meta charset='utf-8'><title>hermes on herdr / offline demo</title>"
            "<style>body{margin:0;padding:18px;background:#080c12}"
            "main{position:relative;font:15px/18px Menlo,monospace;font-variant-ligatures:none}"
            "span{position:absolute;display:block;width:9px;height:18px;white-space:pre;overflow:hidden}</style>"
            f'<main style="width:{screen.width * 9}px;height:{screen.height * 18}px">' + "".join(cells) + "</main>")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=int, default=2)
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=44)
    parser.add_argument("--layout", choices=("auto", "cards", "table"), default="auto")
    parser.add_argument("--selected", default="cherry")
    parser.add_argument("--startup", action="store_true", help="Preview the default Gateway startup page")
    parser.add_argument("--pose", type=int, choices=(0, 1, 2), default=0, help="Caduceus glow phase for a still preview")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 20 <= args.width <= 300 or not 8 <= args.height <= 100:
        parser.error("Preview size must be 20..300 columns and 8..100 rows")
    data = demo_snapshot(args.profiles)
    view = DashboardView(ViewState(selected=args.selected, layout=args.layout, startup=args.startup), embedded=True, demo=True)
    screen = render_to_screen(args.width, args.height, theme_for("herdr"),
                              lambda ui: view.render(ui, data, now=data.updated, pose=args.pose))
    args.output.write_text(fixed_cell_html(screen))
    print(f"Rendered {args.profiles} demo profiles at {args.width}x{args.height}: {args.output}")


if __name__ == "__main__":
    main()
