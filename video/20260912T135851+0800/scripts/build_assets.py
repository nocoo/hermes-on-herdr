"""Build static presentation assets from invented data; never contact a live agent."""

import argparse
import base64
from contextlib import ExitStack
from dataclasses import replace
import hashlib
from html import escape
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "src"))

from hermes_gateway_herdr.dashboard_demo import demo_snapshot
from hermes_gateway_herdr.dashboard_view import DashboardView, ViewState, theme_for
from hqtui import render_to_screen


def read_json(path):
    return json.loads((ROOT / path).read_text())


BRAND = read_json("research/brand-reference.json")
TOKENS = BRAND["tokens"]
CUBIES = read_json("fixtures/cubies.json")
CLI = read_json("fixtures/cli.json")["terminals"]


def data_uri(data, mime):
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def font_css():
    return "".join(
        f"@font-face{{font-family:'{name}';src:url('{data_uri((ROOT / path).read_bytes(), 'font/woff2')}');font-weight:100 900}}"
        for name, path in (
            ("Space Grotesk", "public/fonts/space-grotesk.woff2"),
            ("Geist Mono", "public/fonts/geist-mono.woff2"),
        )
    )


def text(x, y, value, size=28, color=None, mono=False, extra=""):
    family = "Geist Mono, Menlo, monospace" if mono else "Space Grotesk, sans-serif"
    return (
        f'<text xml:space="preserve" x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'fill="{color or TOKENS["ink"]}" {extra}>{escape(str(value))}</text>'
    )


def svg(title, body, width=1600, height=1000):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f"<title>{escape(title)}</title><style>{font_css()}</style>{body}</svg>\n"
    ).encode()


def panel_header(title, eyebrow, color):
    return (
        f'<rect width="1600" height="1000" rx="36" fill="{TOKENS["surface"]}"/>'
        f'<rect x="48" y="54" width="8" height="84" rx="4" fill="{color}"/>'
        + text(80, 77, eyebrow, 22, TOKENS["muted"], mono=True)
        + text(80, 132, title, 46, extra='font-weight="600"')
        + f'<path d="M80 171H1520" stroke="{TOKENS["line"]}"/>'
        + text(80, 940, "SYNTHETIC FIXTURE / NO LIVE SESSION DATA", 20, TOKENS["muted"], mono=True)
    )


def cli_panel(item):
    body = panel_header(item["title"], item["eyebrow"], CUBIES["palette"][item["color"]])
    for index, line in enumerate(item["lines"]):
        if len(line) > 78:
            raise ValueError(f"Fixture line exceeds the presentation width: {item['id']}")
        color = TOKENS["accent"] if line.startswith(("$", ">")) else TOKENS["ink"]
        body += text(92, 259 + index * 60, line, 30, color, mono=True)
    return svg(item["title"], body)


def monitor_panels():
    # Reuse the actual view, with no Config, Monitor, processes or socket probes.
    now = 1789203600
    snapshot = demo_snapshot(2, now=now)
    names = ("demo-m2", "demo-local")
    profiles = tuple(
        replace(
            profile,
            name=names[index],
            home=Path("/demo/profiles") / names[index],
            pid=42001 + index,
            pane="wDEMO:p5" if index == 0 else "",
            platforms=(("discord", "connected"),) if index == 0 else (),
            supervision="external" if index == 0 else "manual",
        )
        for index, profile in enumerate(snapshot.profiles)
    )
    snapshot = replace(
        snapshot,
        profiles=profiles,
        events=((now - 67, "demo-m2", "STARTING", ""), (now - 64, "demo-m2", "READY", "")),
    )
    output = {}
    for startup in (False, True):
        name = "monitor-startup" if startup else "monitor-ready"
        state = ViewState(selected="demo-m2", startup=startup, animation=False)
        view = DashboardView(state, session="demo-session", demo=True)
        screen = render_to_screen(
            100, 30, theme_for(state.theme), lambda ui: view.render(ui, snapshot, now=now)
        )
        if not screen.contains("DEMO") or not screen.contains("demo-m2"):
            raise AssertionError("Native demo identity/marker missing")
        title = "Open the monitor." if startup else "See the managed Gateway."
        body = panel_header(title, "NATIVE HQTUI / OFFLINE DEMO", CUBIES["palette"]["mint"])
        body += '<rect x="60" y="196" width="1480" height="672" rx="12" fill="#080c12"/>'
        for y in range(screen.height):
            x = 0
            while x < screen.width:
                cell = screen.cell(x, y)
                end = x + 1
                while end < screen.width and screen.cell(end, y)[1:] == cell[1:]:
                    end += 1
                content = "".join(screen.cell(i, y).char for i in range(x, end))
                px, py, length = 68 + x * 14.64, 204 + y * 21.6, (end - x) * 14.64
                fg = f"#{int(cell.fg or screen.theme.foreground) & 0xFFFFFF:06x}"
                bg = f"#{int(cell.bg or screen.theme.background) & 0xFFFFFF:06x}"
                body += f'<rect x="{px:.2f}" y="{py:.2f}" width="{length:.2f}" height="21.6" fill="{bg}"/>'
                body += text(
                    f"{px:.2f}", f"{py + 17:.2f}", content, 19, fg, mono=True,
                    extra=f'textLength="{length:.2f}" lengthAdjust="spacingAndGlyphs"',
                )
                x = end
        output[f"public/cli/{name}.svg"] = svg(title, body)
        output[f"public/cli/{name}.txt"] = (screen.text() + "\n").encode()
        output[f"public/cli/{name}.ansi"] = (screen.ansi() + "\x1b[0m\n").encode()
    return output


def face_texture(face):
    color = CUBIES["palette"][face["color"]]
    body = f'<rect width="512" height="512" rx="48" fill="{color}"/>'
    body += f'<rect x="30" y="30" width="452" height="452" rx="32" fill="none" stroke="{TOKENS["ink"]}" stroke-opacity=".1"/>'
    size = 50 if len(face["label"]) > 9 else 62
    body += text(256, 278, face["label"], size, extra='text-anchor="middle" font-weight="600"')
    body += text(256, 420, face["detail"], 20, TOKENS["ink"], mono=True, extra='text-anchor="middle"')
    return svg(face["label"] + " / cubie face texture", body, 512, 512)


def contact_sheet(title, items, outputs, *, columns, thumb_width, thumb_height):
    gap, margin, header = 30, 48, 150
    rows = (len(items) + columns - 1) // columns
    width = 2 * margin + columns * thumb_width + (columns - 1) * gap
    height = header + rows * (thumb_height + 52 + gap) + margin
    body = f'<rect width="{width}" height="{height}" fill="{TOKENS["page"]}"/>'
    body += text(margin, 66, title, 40, extra='font-weight="600"')
    body += text(margin, 109, "HERMES ON HERDR / ASSET PREPARATION / NO FINAL FILM", 19, TOKENS["muted"], mono=True)
    for index, (label, path) in enumerate(items):
        x = margin + (index % columns) * (thumb_width + gap)
        y = header + (index // columns) * (thumb_height + 52 + gap)
        body += f'<image href="{data_uri(outputs[path], "image/svg+xml")}" x="{x}" y="{y}" width="{thumb_width}" height="{thumb_height}" preserveAspectRatio="xMidYMid meet"/>'
        body += text(x, y + thumb_height + 31, label, 22)
    return svg(title, body, width, height)


def gallery(cli_items, face_items):
    def cards(items):
        return "".join(
            f'<figure><a href="{path}"><img src="{path}" alt="{escape(label, quote=True)}" loading="eager"></a>'
            f'<figcaption>{escape(label)}</figcaption></figure>' for label, path in items
        )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hermes on Herdr / asset preparation</title><style>
{font_css()}
*{{box-sizing:border-box}}body{{margin:0;background:{TOKENS['page']};color:{TOKENS['ink']};font-family:'Space Grotesk',sans-serif}}
main{{max-width:1600px;margin:auto;padding:64px 52px}}header{{display:flex;gap:28px;align-items:center;margin-bottom:40px}}
header img{{width:56px;height:56px}}h1{{font-size:clamp(28px,4vw,56px);letter-spacing:-2px;line-height:1.05;margin:12px 0 18px}}
.meta{{font-family:'Geist Mono',monospace;font-size:12px;letter-spacing:1px;color:{TOKENS['accent']}}}p{{font-size:18px;line-height:1.65;max-width:850px}}
nav{{display:flex;flex-wrap:wrap;gap:24px;margin:28px 0 42px}}a{{color:inherit;text-underline-offset:5px}}h2{{font-size:28px;margin:52px 0 24px}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}}.faces{{grid-template-columns:repeat(6,minmax(0,1fr))}}
figure{{margin:0}}figure img{{display:block;width:100%;height:auto;border-radius:18px}}figcaption{{padding:12px 2px;font-size:15px}}
.note{{color:{TOKENS['muted']};font-size:15px}}footer{{border-top:1px solid {TOKENS['line']};margin-top:58px;padding-top:24px}}
@media(max-width:900px){{main{{padding:32px 22px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.faces{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
@media(max-width:520px){{header{{gap:16px}}h1{{letter-spacing:-1px}}.grid{{grid-template-columns:1fr}}.faces{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
</style></head><body><main>
<header><img src="public/brand/hexly-favicon.svg" alt="Official Hexly favicon"><div><div class="meta">ENGLISH / ASSETS ONLY / KIT 1.0.0 REFERENCE</div><h1>Context is control.</h1></div></header>
<p>A preparation desk for the next Hermes on Herdr film. Synthetic terminal fixtures, original candy-colored face textures, and preserved upstream brand assets.</p>
<nav aria-label="Asset sections"><a href="#cli">Terminal fixtures</a><a href="#cubies">Cubie faces</a><a href="README.md">Rebuild notes</a><a href="LICENSES.md">Sources and licenses</a></nav>
<h2 id="cli">Terminal fixtures</h2><p class="note">Seven authored diagrams and CLI summaries; two native hqtui views with renamed offline demo data. No live task, message, profile or account was captured. The native monitor keeps its actual existing terminal theme.</p>
<section class="grid" aria-label="Terminal assets">{cards(cli_items)}</section>
<h2 id="cubies">Candy-colored cubie faces</h2><p class="note">18 square textures map to 27 cubies. Agent and channel labels are typography, not invented logos. The upstream Hermes SVG favicon is preserved separately as a Unicode wrapper; its documentation avatar is retained for source review only.</p>
<section class="grid faces" aria-label="Cubie face assets">{cards(face_items)}</section>
<footer><p>No narration, soundtrack, final video or template runtime is included.</p><p class="note">Hexly logo reveal and RedDot remain references to the shared library. Sources, hashes and known verification limits are recorded with this preparation.</p></footer>
</main></body></html>\n'''.encode()


def build():
    outputs = {}
    cli_items = []
    for item in CLI:
        path = f"public/cli/{item['id']}.svg"
        outputs[path] = cli_panel(item)
        heading = f"SYNTHETIC FIXTURE / {item['title']} / NOT A LIVE TRANSCRIPT\n\n"
        outputs[f"public/cli/{item['id']}.txt"] = (heading + "\n".join(item["lines"]) + "\n").encode()
        outputs[f"public/cli/{item['id']}.ansi"] = ("\x1b[38;2;191;92;60m" + heading + "\x1b[0m" + "\n".join(item["lines"]) + "\n").encode()
        cli_items.append((item["title"], path))
    # Fail if a later edit accidentally adds live discovery/probing to generation.
    with ExitStack() as stack:
        for target in ("socket.socket", "subprocess.Popen", "psutil.Process", "hermes_gateway_herdr.monitor.Monitor.__init__"):
            stack.enter_context(patch(target, side_effect=AssertionError("Live I/O forbidden in asset builder")))
        outputs.update(monitor_panels())
    for name, label in (("monitor-ready", "Native monitor / offline"), ("monitor-startup", "Native startup / offline")):
        cli_items.append((label, f"public/cli/{name}.svg"))
    face_items = []
    for face in CUBIES["faces"]:
        path = f"public/cubies/{face['id']}.svg"
        outputs[path] = face_texture(face)
        face_items.append((face["label"], path))
    outputs["public/review/cli-contact-sheet.svg"] = contact_sheet(
        "Terminal asset contact sheet", cli_items, outputs, columns=3, thumb_width=560, thumb_height=350
    )
    outputs["public/review/cubie-contact-sheet.svg"] = contact_sheet(
        "Cubie face contact sheet", face_items, outputs, columns=6, thumb_width=256, thumb_height=256
    )
    outputs["index.html"] = gallery(cli_items, face_items)
    assets = [
        {"id": Path(path).stem, "kind": "terminal-fixture", "file": path, "width": 1600, "height": 1000}
        for _, path in cli_items
    ] + [
        {"id": "face-" + Path(path).stem, "kind": "cubie-texture", "file": path, "width": 512, "height": 512}
        for _, path in face_items
    ]
    for item in assets:
        item["sha256"] = hashlib.sha256(outputs[item["file"]]).hexdigest()
    assets.extend({"id": s["id"], "kind": "preserved-upstream", "file": s["file"], "sha256": s["sha256"]}
                  for s in read_json("research/sources.lock.json")["sources"] if s["file"].startswith("public/brand/"))
    assets.extend(BRAND["references"])
    manifest = {
        "schemaVersion": 1, "phase": "asset-preparation", "templateStatus": read_json("run.json")["template"]["status"],
        "assets": assets, "cubieLayout": "fixtures/cubies.json", "storyboard": "fixtures/storyboard.json",
        "semanticFaceIds": [face["id"] for face in CUBIES["faces"]],
        "generatedFiles": [
            {"sha256": hashlib.sha256(data).hexdigest(), "file": path}
            for path, data in sorted(outputs.items())
        ],
        "nativeMonitor": {"source": "src/hermes_gateway_herdr/dashboard_view.py", "mode": "offline-demo", "columns": 100, "rows": 30},
    }
    outputs["asset-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare a deterministic rebuild without writing")
    parser.add_argument("--replay", help="Print a prepared fixture; never execute the displayed commands")
    parser.add_argument("--ansi", action="store_true", help="Use the fixture's terminal color stream")
    args = parser.parse_args()
    if args.replay:
        known = {item["id"] for item in CLI} | {"monitor-ready", "monitor-startup"}
        if args.replay not in known:
            parser.error("Unknown prepared fixture")
        suffix = "ansi" if args.ansi else "txt"
        sys.stdout.write((ROOT / f"public/cli/{args.replay}.{suffix}").read_text())
        return
    outputs = build()
    for relative, data in outputs.items():
        path = ROOT / relative
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Generated path escaped the preparation")
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise AssertionError(f"Rebuild differs: {relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"{'Verified' if args.check else 'Built'} {len(outputs)} deterministic files; no live I/O or video render")


if __name__ == "__main__":
    main()
