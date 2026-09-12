# Context is control — English film

[Watch or download the final MP4](public/review/hermes-on-herdr-context-en.mp4): **96.5 seconds · 1920 × 1080 · 30 fps · English narration · 5,663,298 bytes**. The user approved the live Chrome preview, requested subtitle-free opening and closing plates, and accepted the finished film. Body subtitles have no background; the bookends retain their narration without subtitles.

The approved direction uses original 2D signal paths, authentic product icons, short titles and bright Hexly typography. It explains the missing session context of an independent Hermes, the trusted profile explicitly bound by the plugin, and familiar messaging channels leading to a local Herdr control path. The narration retains the same-user permission and integration-testing qualifications.

The previous cubie draft is preserved in [its checkpoint](process/checkpoints/02-cubie-preview-rejected/checkpoint.json), and the approved web preview in [its checkpoint](process/checkpoints/03-approved-web-preview/checkpoint.json). The historical production at `../20260912T102534+0800/` is unchanged. All work in this run stays inside this directory.

## Preview and rebuild

Use Bun 1.4.0, Node, Python 3.12 (tested with 3.12.14), uv, FFmpeg/ffprobe and Google Chrome. The checked-in soundtrack, fonts and images allow website builds and video rendering without fetching a voice model. All Remotion packages are pinned to 4.0.520; Zod is pinned to 4.4.3.

```sh
bun install --frozen-lockfile
bun run dev
```

Open <http://127.0.0.1:7460/> for the live composition and MP4 playback/download links. Play, pause, scrub, jump chapters, toggle captions, and use fullscreen. Space plays/pauses and Escape exits fullscreen. Controls sit outside the picture. A production website is generated in `website/` with `bun run build`.

```sh
bun run kit:check
python3 scripts/fetch_logos.py --check
bun run lint
bun run typecheck
bun run test
bun run build
bun run stills
bun run render
```

`bun run render` renders all 2,895 frames, then muxes the mastered AAC soundtrack without another picture encode. It outputs H.264/AAC with faststart. Body captions are burned into the picture once; separate SRT/VTT are provided without an embedded subtitle track that could create overlapping captions. `CHROME_PATH` can select a browser and `RENDER_CONCURRENCY` defaults to 3.

For verification, slides, or speech regeneration, install the pinned Python environment:

```sh
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python requirements.lock
bun run slides
bun run verify
bun run build
```

To regenerate speech, run `bun run voice`, then `bun run sound`, followed by render, slides, verification and build. The narration script fetches only the pinned, hash-verified Kokoro files in [the voice manifest](research/voice-sources.lock.json). A model download is about 327 MB and stays in the ignored cache. Regeneration on different libraries or hardware need not be byte-identical; the delivered audio and checksums preserve this approved master.

`bun run review`, `bun run review:controls`, and `bun run review:final` require the local server and installed Chrome. They exercise scene layout and live playback, fullscreen controls, and native MP4 playback respectively. See the [final verification report](verification/final/REPORT.md) for the actual outcomes, including the interrupted final native-browser automation. `run.json` retains the explicit approval that releases the rendering gate.

## Deliverables and evidence

- [Storyboard](research/storyboard-02.md)
- [English narration](public/audio/narration-en.md), [SRT](public/audio/narration-en.srt), [VTT](public/audio/narration-en.vtt)
- [Contact sheet decoded from the final MP4](verification/final/contact-sheet.jpg), [clean scene frames](public/review/stills/), [poster](public/review/poster.png)
- [PDF](public/slides/hermes-context-en.pdf), [PPTX](public/slides/hermes-context-en.pptx), [ODP](public/slides/hermes-context-en.odp), [speaker notes](public/slides/speaker-notes-en.md): 11 pages, with editable native notes in PPTX/ODP
- [Credits and licenses](CREDITS.md), [production log](PRODUCTION.md), [verification report](verification/final/REPORT.md), [artifact checksums](SHA256SUMS)
- [Logo sources and rights boundaries](research/product-logo-sources.md), [exact file hashes](research/product-logos.lock.json)
- [Official publisher links](public/logos/SOURCES.md)
- [Voice provenance](research/voice-sources.lock.json)

## Shared template and storage

The entire `@hexly/video-kit@1.0.0` copy is pinned to published Hexly commit `e1b220a7643e8275134b0bff0a11d703c047abbe`. Its [README](vendor/hexly-video-kit/README.md), [CREDITS](vendor/hexly-video-kit/CREDITS.md), vendor package and licensed fonts remain intact. No current Hexly working-tree files are read or written. The official reveal is used through its published public API; one locally scoped CSS fix expands only the vertical clipping bounds so the wordmark's `y` is not cut off.

The MP4 is small enough for ordinary Git; no LFS or separate Release asset is required. Meaningful checkpoints, the initial subtitle-mux attempt, final media, WAV sources, scripts and evidence are retained. Existing repository ignores keep dependencies, the model cache, rebuildable website/render bundles and raw render intermediates out of the commit; those local files are not deleted. No product code, workflow, release configuration or other repository is changed by this production.
