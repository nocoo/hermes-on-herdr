# Context is control — English animation preview

Visual revision 02 replaces the rejected Three.js cubies with original 2D signal paths, exact publisher-provided product icons, short titles, and transparent subtitles. It uses the measured 96.5-second English draft soundtrack.

The user requested Chrome review before any video recording or final MP4 render. This directory is awaiting that review; no final MP4 has been rendered or published. The previous cubie draft is preserved in [its checkpoint](process/checkpoints/02-cubie-preview-rejected/checkpoint.json). The historical production at `../20260912T102534+0800/` is unchanged.

```sh
bun install --frozen-lockfile
bun run dev
```

Open <http://127.0.0.1:7460/?preview=2>. Play, pause, scrub, jump chapters, toggle captions, and use fullscreen. In fullscreen, Space plays/pauses and Escape exits. Controls sit outside the picture. The preview defaults to a live cover frame and restarts at frame zero on first play.

```sh
bun run kit:check
python3 scripts/fetch_logos.py --check
bun run lint
bun run typecheck
bun run test
bun run build
bun run stills
bun run review
bun run review:controls
```

`bun run review` needs the local preview server. It checks every chapter in Chrome, intact product images and text bounds, transparent subtitles, mobile layout, captions/chapter controls, the complete real-time playback, and pixel equivalence of the expanded Hexly wordmark with an unmasked reference. It saves screenshots and JSON under `verification/preview-02/`. It does not record a video.

`bun run review:controls` opens a separate headed Chrome instance to exercise fullscreen play, pause, resume and Escape, and the light composition under a dark system preference. It closes its own browser after the check. See the [preview verification report](verification/preview-02/REPORT.md).

`bun run sample` and `bun run render` intentionally stop while `run.json` records an unapproved review gate. Only explicit user approval allows that gate to be marked approved. The existing voice files remain draft; final pronunciation, media mastering, export and publication remain after approval.

- [Storyboard](research/storyboard-02.md)
- [English narration](public/audio/narration-en.md), [SRT](public/audio/narration-en.srt), [VTT](public/audio/narration-en.vtt)
- [Current contact sheet](public/review/contact-sheet.jpg)
- [Logo sources and rights boundaries](research/product-logo-sources.md), [exact file hashes](research/product-logos.lock.json)
- [Official publisher links](public/logos/SOURCES.md)
- [Voice provenance](research/voice-sources.lock.json)

The entire `@hexly/video-kit@1.0.0` copy is pinned to published Hexly commit `e1b220a7643e8275134b0bff0a11d703c047abbe`. Its [README](vendor/hexly-video-kit/README.md), [CREDITS](vendor/hexly-video-kit/CREDITS.md), vendor package and licensed fonts remain intact. No current Hexly working-tree files are read or written. The official reveal is used through its published public API; one locally scoped CSS fix expands only the vertical clipping bounds so the wordmark's `y` is not cut off.

The preview uses Bun 1.4.0, Remotion 4.0.520 and the installed Google Chrome. The original Kokoro source and soundtrack scripts are retained for later audio work. No product code, workflow, release configuration or other repository was changed.
