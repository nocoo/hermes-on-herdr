# Final verification — English film

Artifact: [hermes-on-herdr-context-en.mp4](../../public/review/hermes-on-herdr-context-en.mp4). The user approved the preview with subtitle-free bookends, then accepted the final video and requested its Finder location. No final visual changes followed that acceptance.

| Check | Result and evidence |
| --- | --- |
| Final streams | 1920 × 1080, 30 fps, 2,895 frames, 96.5 s; H.264 `yuvj420p`, stereo AAC 48 kHz; faststart. [ffprobe](ffprobe.json). |
| Artifact identity | 5,663,298 bytes; SHA-256 `bfb53aae6ebdf484cd8dfb8d757f738c0a712046a1ee8b361e2bd4b41d78e31a`. [Machine report](media.json). |
| Complete decode | Passed for both video and audio. Empty [decode error log](full-decode.log). |
| Black frames / silence | Zero black intervals; zero silence intervals at −50 dB for at least 0.35 s. [Detection log](black-silence.log). This detects blank frames or gaps, not speech correctness by itself. |
| Audio master | −16.03 LUFS, −1.70 dBTP. [Loudness log](loudness.log). All 20 WAV hashes, sample validity, audibility and shot boundaries passed. |
| Mux integrity | Compressed AAC packet SHA-256 matches the mastered M4A exactly. [Audio stream check](audio-stream.json). No second picture encode during the final remux. |
| Captions | One burned-in body layer; 18 complete body-sentence cues in SRT/VTT; no embedded duplicate track. Opening/closing captions absent in both sidecars and sampled subtitle pixel bands. |
| Actual picture | 17 native frames decoded from the delivered MP4, including narration inside each bookend, transitions, all chapters and the final frame. [Contact sheet](contact-sheet.jpg), [opening during speech](frames/decoded-01.png), [ending during speech](frames/decoded-15.png), [final frame](frames/decoded-17.png). Visually inspected: subtitle-free bookends and full Hexly `y` descender. |
| Presentations | 11 pages each in PDF/PPTX/ODP; frame hashes, page count and native speaker notes validated. [Slide mapping](../../public/slides/slides.json). |
| Project checks | `bun run lint`, `bun run typecheck`, `bun run test` (3 tests, 300 assertions) passed. Final `bun run build` passed with the final MP4 available in the built website. |
| Shared kit / logos | `bun run kit:check`: 38 immutable kit files and matching fonts/notices. `python3 scripts/fetch_logos.py --check`: all 10 recorded publisher images match, including the unused white Discord reference. |
| Product regression evidence | Existing production-run [plugin test log](../plugin-tests.txt): 167 tests passed. No product implementation or workflow change is included in this production. |
| Protected history | Old Chinese and English MP4 SHA-256 values match their recorded baseline. The protected Git tree is `23e9cf0dc1e3e246b77bafe4d1d9843dbd8cf323`. [Machine report](media.json). |

## Browser and speech review scope

The [pre-render Chrome report](../preview-02/REPORT.md) records all 11 scenes, a complete 96.5-second **live Remotion** playback, 390 × 844 layout, caption/chapter controls, fullscreen keyboard behavior, no browser errors, and the official fully expanded wordmark matching an unclipped reference pixel-for-pixel.

For the final MP4, headed Chrome verified subtitle counts of zero/one/zero in the opening/body/closing live frames, HTTP 206 range serving, native 1920 × 1080 / 96.5 s metadata and AAC decoding. Its native playback advanced through 19.9, 40.0, 60.0 and 79.963 seconds with no media error before the browser/page was closed. [Last recorded native playback state](chrome-playback-progress.json). The reason for that closure was not established; there is **no completed 96.5-second native Chrome automation report**. The earlier attempt had replaced the app DOM without disposing Remotion; the script was corrected to navigate directly to the MP4. Complete FFmpeg decoding and the user's subsequent explicit acceptance are separate completed checks.

The independent [ASR result](../asr-en.json) provides additional narration coverage, including the final “AI”. It is not a perfect transcript: product/technical names include recognizer substitutions such as “Herter” and “pain”, plus an extra “TN” near VPN. Source text, generated phonemes, WAV checks and timing records are retained; no claim of perfect recognition or a separate human listening audit is made.

The final website build reports Vite's advisory for a minified JavaScript chunk above 500 kB: 592.12 kB, 184.69 kB gzip. The build succeeds. No site deployment or new end-to-end remote channel/lifecycle integration is claimed by these film checks.

Reproduce media verification with `bun run verify` after installing the locked Python environment described in the [production README](../../README.md). `bun run review:final` runs the separate headed native-browser check against the local preview server.
