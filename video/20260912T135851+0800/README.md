# Context is control: asset preparation

Reusable English assets for the next **Hermes on Herdr** film. This is a static preparation archive: it contains no narration, music, final video, or imported Hexly template runtime.

Open [the asset gallery](index.html), [terminal contact sheet](public/review/cli-contact-sheet.png), or [cubie contact sheet](public/review/cubie-contact-sheet.png).

- Nine terminal assets: seven clearly fictional CLI/concept fixtures and two native hqtui views generated from offline demo data. Each has SVG, plain-text and ANSI exports.
- Eighteen square cubie face textures, mapped to all 27 positions of a complete 3-by-3 cube.
- Nine untimed storyboard beats with English short copy, source evidence and required visible qualifications.
- Unmodified upstream Hermes SVG favicon and documentation PNG reference, plus the official Hexly favicon. Source URLs, licenses and SHA-256 hashes accompany each imported file.

The only writable scope is this dated directory. The old `video/20260912T102534+0800/` archive, product code, workflows and the Hexly repository remain untouched by this preparation.

## Rebuild and inspect

From this directory, use Python 3.12 and the pinned dependency lock. The monitor builder imports the existing repository view and its vendored hqtui; it does not construct a live monitor, load private configuration, contact a socket, or start an agent.

```sh
uv venv --python 3.12 .venv
UV_CACHE_DIR=.cache/uv uv pip install --python .venv/bin/python --require-hashes -r requirements.lock
.venv/bin/python -I -B scripts/fetch_sources.py
.venv/bin/python -I -B scripts/build_assets.py
bun install --frozen-lockfile
bun run preview:assets
.venv/bin/python -I -B scripts/verify_assets.py
```

`fetch_sources.py` verifies every existing source and only restores missing files from pinned HTTPS URLs; it refuses different bytes. `build_assets.py --check` compares an in-memory rebuild without writing. The preview script captures static sheets and desktop/mobile gallery viewports in an isolated Chrome profile under `.cache/`. Set `ASSET_CHROME_PATH` if Chrome is installed elsewhere.

For a local browser preview, open `index.html`, or serve this directory:

```sh
python3 -m http.server 7444 --bind 127.0.0.1
```

The fixture replay command prints prepared text or terminal colors. It never executes any displayed command:

```sh
.venv/bin/python -I -B scripts/build_assets.py --replay codex
.venv/bin/python -I -B scripts/build_assets.py --replay monitor-ready --ansi
```

## Source files and consumption

| File | Role |
| --- | --- |
| [asset-manifest.json](asset-manifest.json) | Asset IDs, dimensions, output hashes and upstream references |
| [fixtures/cli.json](fixtures/cli.json) | Invented CLI tasks, messages and presentation summaries |
| [fixtures/cubies.json](fixtures/cubies.json) | Face identities, original candy palette, future material settings and 27 positions |
| [fixtures/storyboard.json](fixtures/storyboard.json) | English short copy, visual actions, evidence and mandatory qualifications |
| [research/brand-reference.json](research/brand-reference.json) | Exact Hexly brand values and references to the shared reveal/RedDot |
| [research/sources.lock.json](research/sources.lock.json) | Immutable public source URLs and full hashes |
| [research/local-sources.json](research/local-sources.json) | Local renderer source hashes and protected old MP4 hashes |
| [LICENSES.md](LICENSES.md) | Imported asset licensing and identity distinctions |
| [verification/REPORT.md](verification/REPORT.md) | Checks, preview evidence and scope limits |

SVG panels are authored at 1600 × 1000; cubie textures are natively 512 × 512. Place complete panels in a future 1920 × 1080 composition with their aspect ratio preserved. They are separate assets, not cropped video frames. The two native monitor views retain the actual application's terminal theme; the surrounding gallery and authored fixtures use light Hexly colors.

All displayed tasks, status samples, handles and chat messages are invented. `wDEMO` is a visual fixture marker and must never be passed to Herdr. The `herdr agent list` panel is an authored summary; the live command returns JSON. Named coding-agent panels are not exact reproductions of their UI. No real agent conversation was recorded.

## Template handoff

**Published reference: @hexly/video-kit 1.0.0.** The Hexly coordinator supplied `e1b220a7643e8275134b0bff0a11d703c047abbe`; remote main and the peeled `v0.6.0` tag were independently checked against it. The committed README/API were reviewed read-only. This preparation contains no runtime adapter. A previous public schema fetch returned HTTP 403; no schema validation is claimed from that endpoint.

The manifest references the published `HexlyReveal`/`LogoReveal` and `RedDot` exports. The favicon is a reference asset, not a substitute end-slate mark. Full package consumption and the newly resumed English film belong to a separate production directory pinned to this SHA. No draft template was copied or rewritten here.

## Narrative boundaries

The opening is the missing **pane/socket/caller context** of an independently running Hermes. A dedicated trusted Profile is explicitly bound to the current Herdr session; messages arrive through Hermes's existing channels, while the control connection remains local.

Keep the storyboard's required visible captions in any later film. Channel credentials and permitted messaging identities need configuration. The host, Herdr and Gateway must remain online and reach messaging/model services. Discord connectivity has recorded plugin evidence; Telegram/Slack integrations and a fresh complete message-to-pane round trip are not independently verified here. Session binding is an ownership/control scope, **not an OS sandbox**: the local terminal retains the user's UID permissions.
