# Sources, permissions and attribution

Production: **The Weekend Protocol / 周末交接**, 2026-09-12, for Zheng Li's **hermes on herdr**, a Hexly AI project. Both editions use newly generated synthetic narration. No human recording, celebrity voice, voice clone, stock movie, stock music or third-party product logo was harvested for the film.

## Narration

| Edition | Engine / preset | Published permission and source | Attribution |
| --- | --- | --- | --- |
| 中文 | Kokoro 0.9.4; `hexgrad/Kokoro-82M-v1.1-zh`; **zf_001** | [Official model card](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh), **Apache-2.0**; revision `01e7505bd6a7a2ac4975463114c3a7650a9f7218` | Kokoro / hexgrad; Chinese dataset provider acknowledged by the publisher: LongMaoData |
| English | Kokoro 0.9.4; `hexgrad/Kokoro-82M`; **af_heart** | [Official model card](https://huggingface.co/hexgrad/Kokoro-82M), **Apache-2.0**; revision `f3ff3571791e39611d31c381e3a41a3af07b4987` | Kokoro / hexgrad |

The model publisher explicitly permits production use: “With Apache-licensed weights, Kokoro can be deployed anywhere from production environments to personal projects,” and “Kokoro has been deployed in numerous projects and commercial APIs. We welcome the deployment of the model in real use cases.” Apache 2.0 grants commercial use, reproduction and distribution of the licensed work and derivatives. The preset tensors are distributed in these same licensed model repositories. There is no noncommercial or output-redistribution restriction in the published model license. These films synthesize the owner's original script locally using those presets; they do not redistribute any example recordings.

For Chinese, the publisher states: “The Chinese data was freely and permissively granted to us by LongMaoData, a professional dataset company.” For v1.0, the publisher states that training used “permissive/non-copyrighted audio data,” including public-domain, licensed and synthetic audio. These are **the publisher's provenance statements**, not a separately obtained contract with an individual speaker. `zf_001` and `af_heart` are preset identifiers; no real performer is identified or claimed to have endorsed this product. This production does not assert exclusive copyright over a synthetic voice or claim a Microsoft/OpenAI voice license.

The permission basis is the published commercial TTS/model license, not a claim that an unknown online recording is public domain. The [saved model cards](research/licenses/) and [Apache 2.0 text](research/licenses/Kokoro-Apache-2.0.txt) preserve the evidence. The [independent review](research/grok-review.md) and [integration decisions](research/review-decisions.md) distinguish the license from the publisher's dataset statements. General license warranty and trademark exclusions still apply; they are not represented as additional rights.

Each sentence has a WAV and adjacent JSON in `public/audio/zh/` or `public/audio/en/`, recording the exact script, spoken spelling, engine, preset, pinned model revision, model/config/preset URLs and SHA-256 values, synthesis time, sample count, gain, and resulting audio SHA-256. `scripts/narrate.py` uses `weights_only=True` model loading through Kokoro and never downloads example speech. `Herdr` is spoken as “Herder” and `Hexly AI` as “Hex lee A I”; the written brand remains unchanged. The website footer identifies the narration as synthetic.

The reference films used Edge TTS. Their audio and their service-permission assumptions were **not reused**. macOS bundled voices, scraped media, and noncommercial/unknown-license Piper voices were also not used. Rendering the checked-in assets makes no speech-service request.

## Visuals, fonts and score

| Asset | Source / license | Use and attribution |
| --- | --- | --- |
| Product master | This repository's `logo.png`, `assets/brand/source.json`; owner-authorized product artwork | Transparent master copied byte-for-byte to `public/brand/product.png`. The original 3D brass door is an animation interpretation; it does not replace the canonical logo. |
| Hexly brand | Owner's `nocoo/hexly.ai`, commit `e8dbbca8a25ca25215acbe22d241f403235096c8`, `src/components/Icon.tsx#BrandMark`, `src/components/Header.tsx`, `src/styles/base.css`, `public/favicon.svg` | Official hexagon geometry, Space Grotesk wordmark and cream/terracotta palette; authorized by the user's explicit Hexly ending request. [Pinned official SVG](https://raw.githubusercontent.com/nocoo/hexly.ai/e8dbbca8a25ca25215acbe22d241f403235096c8/public/favicon.svg) matched the local file. |
| Monitor image | This repository's `docs/evidence/dashboard-two.png` | Owner's offline demonstration screenshot, copied intact; explicitly labeled as demo data. The video preserves its native 1476:828 aspect ratio. |
| 3D scene, terminals, message panel | Newly authored in `src/art/` | Original geometry and canvas artwork created for the repository owner. Agent product names are descriptive text; no third-party logos or endorsement claims. |
| Space Grotesk | [Fontsource / Space Grotesk](https://fontsource.org/fonts/space-grotesk); SIL OFL 1.1 | Local variable WOFF2, copied from the owner's installed licensed font package; OFL retained under `public/fonts/`. |
| Geist Mono | [Fontsource / Geist Mono](https://fontsource.org/fonts/geist-mono); SIL OFL 1.1 | Local variable WOFF2 and OFL retained under `public/fonts/`. |
| Noto Sans SC | [Google Fonts source](https://github.com/google/fonts/tree/main/ofl/notosanssc); SIL OFL 1.1 | Local subset generated from the official variable TTF, with source/output hashes and OFL in `public/fonts/`; no system font is required for the film. |
| The Weekend Protocol (music) | `scripts/soundtrack.py` | Original oscillator-based composition for the owner: 96 BPM, E minor/G major, pads, bass, bell delays and seeded noise. No samples, loops or third-party melody. Lossless source: `public/audio/music.wav`; attribution and hash: `music.json`. |
| Remotion 4.0.520 | [Remotion license](research/licenses/Remotion-4.0.520.md) | Used for this individual owner's personal project under the free license, which expressly includes commercial videos by individuals. Remotion's source is not relicensed by this repository. |
| React, Three.js, React Three Fiber, Vite | Their packages' MIT licenses | Installed at locked versions; not separately copied into authored source. A built browser bundle retains dependency license notices. |

All owner-created production work remains with the project owner. This list documents permission for the supplied films and project; it does not grant ownership of third-party trademarks. Full-resolution source images are fitted with their original aspect, never forcibly cropped into 16:9. The 1920×1080 scene itself is natively authored at 16:9.
