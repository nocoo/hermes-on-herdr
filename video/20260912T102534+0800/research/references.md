# Reference inspection and design decisions

The source repository at the start of production was `nocoo/hermes-on-herdr`, commit `3f17a50370a77e2ed0ee57ca190da66be4addfca`. Its working tree was clean on `main`. No applicable `AGENTS.md` or `CLAUDE.md` existed in this repository or the checked ancestor directories. Product behavior was read from the current README, plugin manifest, profile/control/lifecycle documentation and implementation. No CI investigation was resumed.

The requested WB Beacon and Raven references were located as real local projects, not reconstructed from memory:

| Reference | Real local production | Verified movie |
| --- | --- | --- |
| WB Beacon / Signal–Glass | `/Users/nocoo/workspace/personal/workflow/project-videos/wb-beacon/20260905T140012+0800/` | `public/review/wb-beacon-signal-glass-v1.mp4`, 112 s, 1920×1080, 30 fps, H.264/AAC |
| Raven / Sunlit Courier | `/Users/nocoo/workspace/personal/workflow/project-videos/raven/20260905T130354+0800/` | `public/review/raven-sunlit-v1.mp4`, 107 s, 1920×1080, 30 fps, H.264/AAC |

`references.json` records movie hashes and inspected source files. Both contact sheets were viewed, both actual movies probed, and their Remotion, timeline, scene, narration and mastering source read. WB Beacon's useful engineering choices were full-canvas Three.js rendering, local assets, perspective screen panels, frame-based travel and identical composition props for selection and rendering. Its artwork, data, screenshots and music were not copied into this film. Raven provided the narrative rhythm: a recurring object, one idea per chapter, a question that resolves at the ending, clean bookends, and quiet music under measured speech. Its miniature islands and voice recordings were not reused.

The native reference specification—1080p, 30 fps, 16:9—fits this product. The new direction is **The Weekend Protocol**: petrol blue, brushed brass, mint status light, machined circular bases, a real door motif, CLI panels and a management topology. The green task signal recurs through the whole film. The final warm plate uses Hexly's official cream/terracotta identity while the product door and name remain visible.

The Hexly source was located at `/Users/nocoo/workspace/personal/hexly.ai`. Its official `BrandMark`, header typography, palette, favicon and product identity archive were inspected read-only. The direct website favicon endpoint returned HTTP 403; the pinned official GitHub SVG then succeeded and matched the local bytes. No third-party brand was substituted. Reference repositories were never edited. Workflow's pre-existing `caddy/Caddyfile` change was observed and left untouched.

Source-of-truth choices: the current README, `docs/13` §13.7 and `docs/14` describe the release's actual validation state; older design documents contain historical “not installed yet” statements. M2 is the user's organizational metaphor. Full control means the trusted same-user CLI/session environment, not a new ACL or sandbox. Startup honors persistent pause; no seamless upgrade or untested cold-start guarantee is advertised. Remote messaging is shown as an illustrative configured Hermes workflow, not as a new live end-to-end test.

All writes, tests, media generation and Git operations are confined to the current repository. The only delegated work was the Herdr Grok reviewer `promo-research` in newly created pane `w2X:p3`: read-only research, with one explicitly assigned temporary report file after terminal output truncation. The primary agent owns implementation, integration and the final commit.
