# Asset sources and licenses

All CLI tasks, messages, pane handles, status samples, face labels, layout data and English copy in this preparation are original synthetic material. No real conversation, token, user account or recording was copied. Agent and channel names identify the tools being discussed; the typographic labels are not claimed to be their logos.

The complete imported-file inventory, exact URLs, sizes and SHA-256 hashes is in [sources.lock.json](research/sources.lock.json). Original license files are preserved without alteration.

| Asset | Authority and pinned source | License / usage |
| --- | --- | --- |
| [Hermes SVG favicon](public/brand/hermes-favicon.svg) | [NousResearch/hermes-agent, website/static/img/favicon.svg](https://github.com/NousResearch/hermes-agent/blob/b7ac3ba1cdf89f94dfe86de27e01358b194f4053/website/static/img/favicon.svg) | Repository [MIT license](research/hermes-LICENSE.txt), Copyright 2025 Nous Research |
| [Hermes docs navbar reference](research/hermes-docs-navbar.png) | [Same upstream revision, website/static/img/logo.png](https://github.com/NousResearch/hermes-agent/blob/b7ac3ba1cdf89f94dfe86de27e01358b194f4053/website/static/img/logo.png) | Same MIT repository license; preserved original raster for research only |
| [Hexly favicon](public/brand/hexly-favicon.svg) | [nocoo/hexly.ai, public/favicon.svg](https://github.com/nocoo/hexly.ai/blob/e1b220a7643e8275134b0bff0a11d703c047abbe/public/favicon.svg) | [MIT](research/hexly-LICENSE.txt), Copyright 2026 Zheng Li; brand use requested by the project owner |
| [Space Grotesk](public/fonts/space-grotesk.woff2) | `@fontsource-variable/space-grotesk@5.3.0`, Latin variable font | [SIL OFL 1.1](public/fonts/space-grotesk-OFL.txt) |
| [Geist Mono](public/fonts/geist-mono.woff2) | `@fontsource-variable/geist-mono@5.3.0`, Latin variable font | [SIL OFL 1.1](public/fonts/geist-mono-OFL.txt) |
| Native offline monitor views | Existing [dashboard renderer](../../src/hermes_gateway_herdr/dashboard_view.py) and [vendored hqtui](../../vendor/README.md), pinned hqtui `d9a841494bab910403737a8c791d6d96ef52e878` | Existing project renderer; upstream hqtui [MIT attribution](../../vendor/hqtui/LICENSE) retained in this repository |

## Hermes icon distinction

The verified upstream SVG is **a favicon containing the Unicode character `⚕`**, not a separately drawn vector logo. Its SHA-256 is `c4d55805bda8e16072ed77c0725176ab2218a9e628d1ba776a6048a39c28f751`. Its appearance can depend on the system font. It is retained verbatim as an authoritative SVG reference, not substituted for the brand logo.

The docs navbar references a 1772 × 1799 PNG, SHA-256 `2eaff911b9da9b1f1fcc81adb02f4992bb9ea6b781f4dd048cd79349927ddb7a`. Visual inspection shows a monochrome avatar, so the filename alone does not establish it as a standalone Hermes product mark. Its original bytes are retained under research and are **not used on a cubie or in the film**. Hermes is represented by ordinary typography. No tracing, invented SVG geometry or vector-logo claim was made. The MIT license covers repository content; it does not separately grant trademark rights or assert endorsement of this plugin.

## Hexly identity

Brand values reference the existing official header, SVG mark and stylesheet at the recorded remote revision. The wordmark's terracotta period (`#bf5c3c`) differs from the existing family `RedDot` component (`#bc7252`, with its official highlight/glow). Both are documented in [brand-reference.json](research/brand-reference.json). No red-dot replacement graphic or shared reveal implementation is authored here.

The candy colors belong to this production's original art direction; they are not additional official brand tokens. The closing animation remains a reference to the Hexly kit's published mark-first reveal. The unrelated `zheng li.` FamilyBrand is not used.

## Coding-agent and channel references

- Codex: [OpenAI repository](https://github.com/openai/codex) and [CLI documentation](https://developers.openai.com/codex/cli/).
- Claude Code: [CLI reference](https://code.claude.com/docs/en/cli-reference).
- Pi: [coding-agent package](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent).
- Grok: the named [Herdr coding-agent integration](https://herdr.dev); this preparation makes no claim to reproduce an official xAI CLI interface.
- Hermes platforms: [upstream implementations](https://github.com/NousResearch/hermes-agent/tree/b7ac3ba1cdf89f94dfe86de27e01358b194f4053/plugins/platforms). Discord, Telegram and Slack are ordinary name labels here; no third-party platform artwork was copied.

No voice or music is present. Voice selection, commercial redistribution evidence and final audio mastering remain outside this preparation.
