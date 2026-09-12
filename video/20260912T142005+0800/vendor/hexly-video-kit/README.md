# Hexly Video Kit

Five expressions of the same Hexly identity. One project configuration drives a
Remotion timeline, an interactive browser preview, and a paginated deck.

**Version 1.0.0** · [Online library](https://hexly.ai/videos) ·
[Family rules](../../docs/16-video-kit.md) · [Credits and licenses](CREDITS.md)

| Template | Composition ID | Use and composition |
| --- | --- | --- |
| Launch | `Hexly-launch` | Product launches; generous left-aligned type and layered paper cards. |
| Studio | `Hexly-studio` | Technical stories; softly lit dimensional objects in the same paper/terracotta palette. |
| Editorial | `Hexly-editorial` | Research and longer explanations; rules, folios, figures and denser copy. |
| Pulse | `Hexly-pulse` | Data and status updates; bounded panels with sourced facts. Catalogue facts are explicitly snapshots, not live health. |
| Essential | `Hexly-essential` | Short brand announcements; centered typography and quiet negative space. |

Every template supports Intro, Title, Chapter, Content, CTA, LogoReveal and
Outro. The supplied 33-second film is a seven-component sampler, not an authored
product advertisement. Reorder or repeat scene kinds with unique IDs to compose
a longer film. Landscape is 1920 × 1080 at 30 fps; portrait is 1080 × 1920.

## Run the previews

From the hexly.ai repository, with Bun 1.4.0 and the checked-in lockfile:

```sh
bun install --frozen-lockfile
bun run dev                         # https://index.dev.hexly.ai/videos
bun run video:dev                   # http://127.0.0.1:7440, standalone Vite demo
bun run video:studio                # http://localhost:7441, five Remotion compositions
bun run video:build                 # standalone production Vite build
```

The standalone demo uses `examples/hexly.json`. It can switch all five templates
between Video and Deck. The main site adapts its existing project catalogue via
`src/model/videos.ts`: selecting a project supplies its real name, bilingual
summary, source logo, links, technology list and dated facts to every template.
An optional PNG/JPEG/WebP screenshot stays in the browser. Downloading the setup
includes that image and the selected format/motion preference in the film JSON.

The site lazily loads the preview player. It never runs a server renderer.
Download links labeled as standard samples always refer to the prebuilt Hexly
sampler; use the downloaded project setup for your own final film or deck.

## Render video and real slides

Install FFmpeg (`ffmpeg` and `ffprobe`) and Chromium/Chrome for offline rendering.
The renderer uses the local macOS Chrome when present; otherwise Remotion uses
its managed browser. `CHROME_PATH` can select an installed executable.

```sh
# One real catalogue project, all artifacts. Choose a fresh output directory.
bun run video:render -- --project pew --template studio --locale zh \
  --mode all --scale 1 --out /tmp/pew-studio-production

# Reproduce the content, screenshot and settings downloaded from /videos.
bun run video:render -- --props /path/to/pew-studio.json \
  --mode deck --scale 1 --out /tmp/pew-studio-deck

# Supply a screenshot directly without changing the catalogue.
bun run video:render -- --project bogo --template launch \
  --screenshot /path/to/screenshot.png --mode all --out /tmp/bogo-launch

# All five standard examples, or use --example editorial for just one.
bun run video:examples -- --mode all --out /tmp/hexly-five-examples
```

`--mode all|video|deck|stills` selects exports. `--scale 0.5` is the default
960 × 540 preview; `--scale 1` renders full resolution. Each output contains a
template subdirectory:

```text
studio/
  sample.mp4           # all/video: H.264, yuv420p, BT.709, 30 fps, silent
  deck.pptx            # all/deck: image-backed slides with editable speaker notes
  deck.pdf             # all/deck: matching image-backed PDF pages
  frames/*.png         # every scene, settled and readable
  poster.webp
  contact-sheet.webp
  decoded-frame.png    # all/video: decoded from the actual MP4
  render.json          # dimensions, timeline, props SHA-256, artifact hashes
```

PPTX/PDF preserve the rendered composition as an image. Slide elements are not
individually editable. PPTX has editable native speaker notes containing scene
text, CTA URL and project evidence; PDF has image pages, not tagged/selectable
text. The browser also exposes a readable scene transcript. These are real
PPTX/PDF exports, not renamed images or promises of later conversion.

Output directories are never overwritten. The root wrapper copies only the
selected project's public images and licensed fonts into ignored `.video-work/`.
The package renderer accepts `--props` and `--public-dir` for independent projects:

```sh
bun packages/video-kit/scripts/render.ts --props /path/to/film.json \
  --public-dir /path/to/film-public --mode all --out /tmp/film-output
```

Place `public/video-kit/1.0.0/hexly/` from this package under that public directory
alongside the project's referenced images. HTTPS images are supported, but local
images make offline renders reproducible.

## Configuration and API

`src/schema.ts` owns validation. The site serves JSON Schema documents at
[`/videos/film-v1.schema.json`](https://hexly.ai/videos/film-v1.schema.json) and
[`/videos/manifest-v1.schema.json`](https://hexly.ai/videos/manifest-v1.schema.json).
Use `parseFilm()` for runtime validation; it additionally rejects duplicate scene
IDs and CTA scenes without an HTTPS destination.

| Field | Contract |
| --- | --- |
| `schemaVersion` | `1` |
| `template` | `launch`, `studio`, `editorial`, `pulse`, `essential` |
| `format`, `fps`, `motion` | `landscape` or `portrait`; `30`; `full` or `reduced` |
| `project` | `id`, `name`, `summary`, HTTPS `repository`, nullable `website`, optional `logo`/`screenshot`, evidenced `colors`, `technologies`, labeled `facts`, `sourceNote` |
| `scenes` | 1–24 scenes; each has unique `id`, `kind`, 4–30 second `duration`, `title`, `eyebrow`, `body`, optional `link` |

Text limits and asset constraints are in the schema. Break long editorial
material across scenes. Each scene's duration includes its entrance and reading
hold. Motion is deterministic from the frame number; there are no random or
wall-clock-driven effects.

```tsx
import { Film, createProjectFilm, durationFor, dimensions } from '@hexly/video-kit';
import { VideoPreview } from '@hexly/video-kit/player';
import '@hexly/video-kit/site.css';
import project from './project.json';

const config = createProjectFilm(project, 'studio', 'en');
// A single change also changes the deck layout:
const editorial = { ...config, template: 'editorial' as const };

// Remotion Composition / Sequence can render Film with this config.
// Metadata: durationFor(config), dimensions(config.format), config.fps.
export const Preview = () => <VideoPreview config={editorial} view="deck" />;
```

`VideoPreview` accepts `config`, `locale`, `view`, `onView`, `onConfigChange` and
optional `clip`/`poster`. Controlled `view` switches video and paginated deck.
An optional clip must depict that exact config; the site keeps the standard
sampler separate from project previews.

The main export also provides `Intro`, `Title`, `Chapter`, `Content`, `CTA`,
`LogoReveal`, `Outro`, `BrandMark`, `BrandLockup`, `HexlyReveal`, `RedDot`,
`family`, `hexly`, `palettes`, `themes`, `ease`, `entrance` and `revealState`.
Scene components take `SceneProps` (title, eyebrow/body/link, template, motion,
project, index and optional custom children). Render them inside Remotion's
composition context. Browser code imports the player separately; it must never
import `scripts/render.ts` or the offline rendering/export dependencies.

## Publication and downstream projects

This is a private Bun workspace package, published in the **hexly.ai Git
repository**, not on npm. Pin the complete published commit SHA. Keep a clean,
dedicated checkout at that revision and refer to its `packages/video-kit` via a
file dependency or copy the complete package, including fonts, vendor archive,
credits and licenses, into a consumer workspace.

The shared boundary is this package, its schemas, the generic catalogue adapter
and `/videos` library. Consumer scripts, voices, audio, product scenes, production
logs and final films belong to that consumer's production archive. Hermes-on-Herdr
can use these APIs after publication; no Hermes-specific production is bundled.

Curated site media is separate: `src/data/videos.json` is the public manifest,
`public/video-assets/video-kit/1.0.0/` holds reviewed standard samples. Add a
finished project later through `manifest.projects` with its own unique ID,
metadata, media and independent preview/source URLs. Never add a private script,
audio source or render directory to this manifest.

After reviewing all five standard renders:

```sh
bun run video:assets -- --from /tmp/hexly-five-examples
bunx biome format --write src/data/videos.json
bun run video:check
```

The publisher verifies render hashes and copies only WebP/MP4/PPTX/PDF files with
hash-bearing filenames. It rejects outputs over 20 MB per file. The checker caps
the curated collection at 40 MB and rejects undeclared files. Versioned assets
use immutable caching; manifests revalidate. Fonts are emitted explicitly by the
Vite plugin. `.cache`, `.video-work`, frames and rendering logs never ship.

Use a patch kit version for compatible fixes, minor for compatible additions,
major for a broken schema/API or family change. Bump versioned asset paths with
the kit; regenerate and review samples before marking them `ready`. Do not
silently replace bytes at a published immutable path.

## Validation

```sh
bun run typecheck
bun run test:coverage
bun run video:check
bun run test:http
bun run test:browser
bun run lint
bun run check:security
bun run deploy:check
```

The root tests cover the real catalogue × five templates × two languages,
manifest/schema boundaries, official geometry, licensed font hashes, reveal
timing, project selection, Video/Deck, screenshots, downloads and mobile access.
Representative rendered frames and export verification live in
[`docs/video-kit/1.0.0`](../../docs/video-kit/1.0.0/review.md).
