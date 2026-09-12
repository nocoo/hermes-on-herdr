# Credits and licenses

The Hexly Video Kit implementation is MIT-licensed; see [LICENSE](LICENSE).
Dependency and asset licenses apply separately. This package contains no newly
generated logo, third-party illustration, music, speech or product-specific film.

## Hexly identity

The official mark paths, proportions, wordmark typography, colors and red-dot
motif come from `nocoo/hexly.ai` at
`e8dbbca8a25ca25215acbe22d241f403235096c8`: `Icon.tsx`, `Header.tsx`,
`src/styles/base.css` and `public/favicon.svg`. The owner authorized reuse for
this shared Hexly template system. Preserve the identity and attribution; the
code license does not imply endorsement of unrelated products using the mark.

Exact sources, unchanged font checksums and subset provenance are recorded in
[`brand-source.json`](brand-source.json). All five templates use these same assets
and tokens. CSS dimensional objects are original geometric scene code; the mark
is presented on a separate front-facing plane, never perspective-distorted.

## Fonts

| Font | Source | License |
| --- | --- | --- |
| Space Grotesk Variable | The site's `@fontsource-variable/space-grotesk@5.3.0` Latin variable WOFF2 | SIL OFL 1.1; `public/video-kit/1.0.0/hexly/space-grotesk-OFL.txt` |
| Geist Mono Variable | The site's `@fontsource-variable/geist-mono@5.3.0` Latin variable WOFF2 | SIL OFL 1.1; `public/video-kit/1.0.0/hexly/geist-mono-OFL.txt` |
| Noto Sans SC, loaded as Journey CJK | Same family as the site's Chinese font; source `google/fonts` commit `a85815a42757630ce188fdad368c2dfc444d4773`, `ofl/notosanssc/NotoSansSC[wght].ttf` | SIL OFL 1.1; Adobe copyright, Reserved Font Name “Source”; `public/video-kit/1.0.0/hexly/journey-cjk-OFL.txt` |

The Noto subset contains 7,613 code points: GB2312 plus current catalogue/template
text. `scripts/subset-font.py` records the reproducible subset process in the
brand manifest. Keep the OFL notices with distributed fonts. New text outside
the subset needs a reviewed subset update; do not silently swap in another font.

## Software

- React, Vite, Zod, PptxGenJS, JSZip and pdf-lib use MIT licenses; Sharp uses
  Apache-2.0. Preserve each installed package's notices when redistributing it.
- Remotion 4.0.520 is **not MIT**. It uses the Remotion License: eligible
  individuals, companies with up to three employees and nonprofit organizations
  may use its free terms; other organizations need the applicable company
  license. Review the installed `remotion/LICENSE.md` and
  [current Remotion licensing](https://www.remotion.dev/license) for your use.
- Offline Chromium and FFmpeg are external tools with their own licenses; they
  are not copied into the site or this package's static assets.

PptxGenJS 4.0.1's published package lists an unused `image-size@^1.2.1` dependency
affected by `GHSA-5p2g-fcmc-qvqq` and `GHSA-w3rx-r6r6-pgpr`; even the latest
image-size 2.0.2 is affected. `vendor/pptxgenjs-4.0.1-hexly.1.tgz` preserves all
upstream code, types and MIT license bytes, removing only this unused dependency
from package.json and labeling the local version. The upstream package integrity,
archive hash and unchanged-file hashes are in `vendor/pptxgenjs-source.json`.
Regenerate with `python3 packages/video-kit/scripts/vendor-pptx.py`; it rejects
new code references to the removed dependency. No security advisory is ignored.
Return to the registry package when upstream removes or fixes that dependency,
then verify a real PPTX export and the full locked-dependency scan.
