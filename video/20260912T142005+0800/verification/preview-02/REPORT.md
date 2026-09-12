# Visual preview 02 — verification record

Status: awaiting the user's Chrome review. This is a live web animation with an existing English draft soundtrack. No MP4 was recorded, rendered or published for this revision. Final rendering remains gated by `run.json`.

## Picture and typography

- Replaced Three.js cubies, gray geometry and perspective panels with original SVG/DOM signal paths, precise session outlines and flat color accents. Every animated position derives from the Remotion frame.
- The 11 scenes use one short title each, small aligned labels and plain subtitles without backgrounds. Playback controls sit outside the composition.
- Codex, Grok, Hermes, Claude Code, Pi, Herdr, Discord, Telegram and Slack use original publisher-supplied image bytes, fitted with `object-fit: contain`. Logos retain their original colors and intrinsic backgrounds. [Sources and rights](../../research/product-logo-sources.md) distinguish authentic provenance from commercial trademark permission.
- The official published Hexly mark/wordmark reveal is retained. A consumer-scoped vertical clipping fix preserves the full `y` descender without changing vendor files or the horizontal reveal. The fully expanded wordmark has **zero differing pixels** against the unmasked official component. The mark-only phase before 1.25 seconds also passed.

[All-scene contact sheet](../../public/review/contact-sheet.jpg) · [Full `y` descender](hexly-y-fixed.png) · [Desktop](desktop.png) · [Mobile](mobile.png)

## Checks performed

| Check | Result |
| --- | --- |
| Bun dependency installation, lint, TypeScript, production build | Passed; lint/typecheck/build rerun after the fullscreen fix |
| Timeline/story unit checks | 3 tests, 300 assertions passed |
| Published kit integrity | All 38 vendor/brand/font/license files match pinned revision |
| Original product image integrity | All 10 manifest assets match SHA-256, including the unused white Discord reference |
| Remotion stills | 11 native 1920 × 1080 scene frames and contact sheet inspected |
| Live Chrome review | All 11 scenes: loaded contained logos, text inside the frame, transparent captions, zero WebGL canvases |
| Complete playback | Reached frame 2,894 of 2,895 at 30 fps; 96.5-second composition |
| Mobile layout | 390 × 844; no horizontal overflow; caption and chapter controls passed |
| Fullscreen in headed Chrome | Space starts at frame zero, pauses and resumes; Escape exits |
| Dark system preference | Film remains light; the official Pi SVG stays visible |
| Browser errors / failed HTTP responses | None in the full scene/playback review |

The final Vite build emits its advisory for a JavaScript chunk over 500 kB. The minified bundle is 591.94 kB (184.65 kB gzip). The build succeeds.

The initial preview clock problem was fixed by memoizing Player input props so UI frame updates do not reset playback. The native space-key option depends on Remotion's built-in play button; the external-control preview now scopes its keyboard handler to fullscreen. The separate headed test exercises the actual controls and closes only its own browser instance.

Machine-readable evidence: [full browser review](browser.json), [headed fullscreen controls](headed-controls.json). Reproduce with `bun run review` and `bun run review:controls` while the local server runs. These commands take screenshots and exercise live animation; neither records a video.

## Production boundary

- All current files are inside `video/20260912T142005+0800/`.
- The rejected cubie draft is preserved in [its checkpoint](../../process/checkpoints/02-cubie-preview-rejected/checkpoint.json).
- Historical `video/20260912T102534+0800/` remains unchanged, with Git tree `23e9cf0dc1e3e246b77bafe4d1d9843dbd8cf323`; its previously recorded MP4 hashes were rechecked during the rework.
- The complete independent Hexly copy remains pinned to `e1b220a7643e8275134b0bff0a11d703c047abbe` (`@hexly/video-kit@1.0.0`). This revision does not modify the shared Hexly working tree, product code, workflows or release settings.
- The existing audio remains a draft. Final pronunciation, media mastering and MP4/media validation follow explicit approval of the web preview. This report does not claim a finished video or cleared blanket trademark rights.
