import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, renderStill, selectComposition } from "@remotion/renderer";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const storyBytes = await readFile(path.join(root, "src/story.json"));
const timingBytes = await readFile(path.join(root, "src/generated/timing.json"));
const story = JSON.parse(storyBytes);
const timing = JSON.parse(timingBytes);
const mode = process.argv[2] ?? "stills";
const language = process.argv[3] ?? (mode === "sample" ? "zh" : "both");
if (!["stills", "sample", "video"].includes(mode)) throw new Error(`Unknown mode: ${mode}`);
if (!["zh", "en", "both"].includes(language)) throw new Error(`Unknown language: ${language}`);
if (mode !== "stills" && timing.provisional)
  throw new Error("Generate the real narration timeline before moving-picture renders");
const sourceHash = createHash("sha256").update(storyBytes).digest("hex");
if (sourceHash !== timing.sourceStorySha256)
  throw new Error("Story and narration timeline differ; run voice --timing-only");
const requested = process.argv[4]?.split(",").map(Number);
if (
  requested?.some(
    (frame) => !Number.isInteger(frame) || frame < 0 || frame >= timing.durationInFrames,
  )
)
  throw new Error("Requested frames are outside the composition");
if (requested && mode === "video")
  throw new Error("Final films always render the complete timeline");
if (mode === "sample" && requested && (requested.length !== 2 || requested[0] > requested[1]))
  throw new Error("Sample expects an ascending start,end pair");
const concurrency = Number(process.env.RENDER_CONCURRENCY ?? 3);
if (!Number.isInteger(concurrency) || concurrency < 1)
  throw new Error("RENDER_CONCURRENCY must be a positive integer");
const stamp = new Date()
  .toISOString()
  .replaceAll(":", "")
  .replaceAll("-", "")
  .replace(/\.\d+Z$/, "Z");
const reportPath = path.join(root, "process", `${stamp}-${mode}-${language}.json`);
await mkdir(path.join(root, "process"), { recursive: true });
await mkdir(path.join(root, "public/review"), { recursive: true });
const record = {
  mode,
  language,
  sourceHash,
  timingHash: createHash("sha256").update(timingBytes).digest("hex"),
  renderedAt: new Date().toISOString(),
  frames: timing.durationInFrames,
  fps: timing.fps,
  width: 1920,
  height: 1080,
  status: "started",
  artifacts: [],
};
await writeFile(reportPath, `${JSON.stringify(record, null, 2)}\n`);
const browserExecutable =
  process.env.CHROME_PATH ??
  (existsSync("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : undefined);
const chromiumOptions = { gl: "angle" };
console.log("Bundle the independent Remotion composition");
const serveUrl = await bundle({
  entryPoint: path.join(root, "src/index.ts"),
  publicDir: path.join(root, "public"),
  outDir: path.join(root, "process/render-web"),
});
const browser = await openBrowser("chrome", {
  browserExecutable,
  chromiumOptions,
  logLevel: "warn",
});
try {
  const common = {
    serveUrl,
    puppeteerInstance: browser,
    chromiumOptions,
    browserExecutable,
    timeoutInMilliseconds: 120000,
  };
  for (const lang of language === "both" ? ["zh", "en"] : [language]) {
    const inputProps = { language: lang, captions: mode !== "stills", audio: false };
    const composition = await selectComposition({
      ...common,
      id: `HermesWeekend${lang.toUpperCase()}`,
      inputProps,
    });
    if (mode === "stills") {
      const out = path.join(root, requested ? "process" : `public/review/stills/${lang}`);
      await mkdir(out, { recursive: true });
      const shots = requested
        ? requested.map((frame) => ({ frame, name: `check-${lang}-${frame}` }))
        : timing.scenes.map((scene) => ({
            frame: scene.keyframe,
            name: `${String(scene.index).padStart(2, "0")}-${scene.id}`,
          }));
      for (const shot of shots) {
        const output = path.join(out, `${shot.name}.png`);
        await renderStill({
          ...common,
          composition,
          inputProps,
          frame: shot.frame,
          output,
          imageFormat: "png",
          logLevel: "warn",
        });
        record.artifacts.push({ file: path.relative(root, output), frame: shot.frame });
        console.log(`Still ${lang} / ${shot.name}`);
      }
      if (!requested)
        await copyFile(
          path.join(out, "00-opening.png"),
          path.join(root, `public/review/poster-${lang}.png`),
        );
    } else {
      const sample = mode === "sample";
      const frameRange = sample
        ? (requested ?? [timing.scenes[5].start - 36, timing.scenes[5].start + 83])
        : undefined;
      const raw = path.join(root, "process", `${lang}-${mode}-raw.mp4`);
      let last = 0;
      await renderMedia({
        ...common,
        composition,
        inputProps,
        codec: "h264",
        outputLocation: raw,
        imageFormat: "jpeg",
        jpegQuality: 95,
        crf: 18,
        x264Preset: "fast",
        pixelFormat: "yuv420p",
        colorSpace: "bt709",
        concurrency,
        frameRange,
        logLevel: "warn",
        onProgress: ({ renderedFrames, encodedFrames, progress }) => {
          if (Date.now() - last > 10000) {
            last = Date.now();
            console.log(
              `${lang}: ${(progress * 100).toFixed(1)}% / ${renderedFrames} rendered / ${encodedFrames} encoded`,
            );
          }
        },
        onBrowserLog: (entry) => {
          if (entry.type === "error") console.error("Browser:", entry.text);
        },
      });
      const output = path.join(
        root,
        sample ? `process/transition-${lang}.mp4` : `public/review/${story.artifact}-${lang}.mp4`,
      );
      const start = sample ? frameRange[0] / timing.fps : 0;
      const duration = sample
        ? (frameRange[1] - frameRange[0] + 1) / timing.fps
        : timing.durationInFrames / timing.fps;
      const audio = path.join(root, `public/audio/mix-${lang}.m4a`);
      if (!existsSync(audio))
        throw new Error("Run sound to create the mastered audio before muxing");
      const result = spawnSync(
        "ffmpeg",
        [
          "-hide_banner",
          "-loglevel",
          "error",
          "-y",
          "-i",
          raw,
          "-ss",
          String(start),
          "-i",
          audio,
          "-map",
          "0:v:0",
          "-map",
          "1:a:0",
          "-c:v",
          "copy",
          "-c:a",
          ...(sample ? ["aac", "-b:a", "192k"] : ["copy"]),
          "-t",
          String(duration),
          "-movflags",
          "+faststart",
          "-metadata",
          `title=Hermes on Herdr - The Weekend Protocol (${lang})`,
          "-metadata",
          "artist=Hexly AI",
          output,
        ],
        { stdio: "inherit" },
      );
      if (result.status !== 0) throw new Error("Audio/video mux failed");
      const bytes = await readFile(output);
      record.artifacts.push({
        file: path.relative(root, output),
        bytes: bytes.length,
        sha256: createHash("sha256").update(bytes).digest("hex"),
        frameRange: frameRange ?? [0, timing.durationInFrames - 1],
      });
      console.log(`Complete: ${output}`);
    }
  }
  record.status = "complete";
} catch (error) {
  record.status = "failed";
  record.error = String(error);
  throw error;
} finally {
  await writeFile(reportPath, `${JSON.stringify(record, null, 2)}\n`);
  await browser.close({ silent: true });
}
