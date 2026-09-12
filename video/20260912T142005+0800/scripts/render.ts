import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import sharp from "sharp";
import story from "../src/story.json";
import timing from "../src/timing.json";

const root = path.resolve(import.meta.dir, "..");
const mode = process.argv[2] ?? "stills";
if (!["stills", "sample", "video"].includes(mode)) throw new Error(`Unknown mode: ${mode}`);
const run = JSON.parse(await readFile(path.join(root, "run.json"), "utf8"));
if (mode !== "stills" && run.reviewGate?.approved !== true)
  throw new Error(
    "The user requested Chrome review first. MP4 rendering awaits explicit approval.",
  );
const requested = process.argv[3]?.split(",").map(Number);
if (requested?.some((f) => !Number.isInteger(f) || f < 0 || f >= timing.durationInFrames))
  throw new Error("Frame outside measured composition");
if (mode === "video" && requested) throw new Error("The final render must contain every frame");
if (
  mode === "sample" &&
  requested &&
  (requested.length !== 2 || (requested[0] ?? 0) > (requested[1] ?? 0))
)
  throw new Error("A sample requires start,end");
const storyHash = createHash("sha256")
  .update(await readFile(path.join(root, "src/story.json")))
  .digest("hex");
if (!timing.measured || storyHash !== timing.storySha256)
  throw new Error("Generate the real narration timeline before rendering");
const voice = path.join(root, "public/audio/mix-en.m4a");
if (mode !== "stills" && !existsSync(voice))
  throw new Error("Master the soundtrack before moving-picture renders");
const stamp = new Date()
  .toISOString()
  .replaceAll(/[-:]/g, "")
  .replace(/\.\d+Z$/, "Z");
const out = path.join(root, "process", `${stamp}-${mode}`);
await mkdir(out, { recursive: true });
const publicOut = path.join(root, "public/review");
await mkdir(path.join(publicOut, "stills"), { recursive: true });
const report: Record<string, unknown> = {
  mode,
  startedAt: new Date().toISOString(),
  storyHash,
  kitRevision: "e1b220a7643e8275134b0bff0a11d703c047abbe",
  width: 1920,
  height: 1080,
  fps: timing.fps,
  durationInFrames: timing.durationInFrames,
  status: "started",
};
const reportPath = path.join(out, "render.json");
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`);
const browserExecutable =
  process.env.CHROME_PATH ??
  (existsSync("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : undefined);
const chromiumOptions = { gl: "angle" as const };
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
const inputProps = { captions: mode !== "stills", audio: false };
const common = {
  serveUrl,
  puppeteerInstance: browser,
  browserExecutable,
  chromiumOptions,
  timeoutInMilliseconds: 120000,
  inputProps,
};
try {
  const composition = await selectComposition({ ...common, id: story.composition });
  if (mode === "stills") {
    const shots = requested
      ? requested.map((frame) => ({ frame, name: `frame-${frame}` }))
      : timing.scenes.map((s) => ({
          frame: s.keyframe,
          name: `${String(s.index).padStart(2, "0")}-${s.id}`,
        }));
    for (const shot of shots) {
      const output = path.join(
        requested ? out : path.join(publicOut, "stills"),
        `${shot.name}.png`,
      );
      await renderStill({
        ...common,
        composition,
        frame: shot.frame,
        output,
        imageFormat: "png",
        logLevel: "warn",
      });
      console.log(`Still ${shot.name} / ${shot.frame}`);
    }
    if (!requested) {
      await copyFile(
        path.join(publicOut, "stills/09-weekend.png"),
        path.join(publicOut, "poster.png"),
      );
      const thumbs = await Promise.all(
        shots.map(async (s, index) => ({
          input: await sharp(path.join(publicOut, `stills/${s.name}.png`))
            .resize(640, 360)
            .png()
            .toBuffer(),
          left: (index % 3) * 660 + 24,
          top: Math.floor(index / 3) * 392 + 24,
        })),
      );
      await sharp({
        create: {
          width: 2008,
          height: Math.ceil(shots.length / 3) * 392 + 16,
          channels: 3,
          background: "#f0f0e9",
        },
      })
        .composite(thumbs)
        .jpeg({ quality: 93 })
        .toFile(path.join(publicOut, "contact-sheet.jpg"));
    }
    report.frames = shots;
  } else {
    const sample = mode === "sample";
    const weekend = timing.scenes.find((s) => s.id === "weekend");
    if (!weekend) throw new Error("Missing assembly shot");
    const frameRange = sample
      ? ((requested ?? [weekend.start, weekend.start + 210]) as [number, number])
      : undefined;
    const raw = path.join(root, "process", `${stamp}-${mode}-raw.mp4`);
    let last = 0;
    const concurrency = Number(process.env.RENDER_CONCURRENCY ?? 3);
    if (!Number.isInteger(concurrency) || concurrency < 1)
      throw new Error("Bad RENDER_CONCURRENCY");
    await renderMedia({
      ...common,
      composition,
      codec: "h264",
      crf: 18,
      pixelFormat: "yuv420p",
      outputLocation: raw,
      frameRange,
      concurrency,
      x264Preset: "medium",
      imageFormat: "jpeg",
      jpegQuality: 95,
      muted: true,
      logLevel: "warn",
      onProgress: ({ renderedFrames }) => {
        if (renderedFrames - last >= 120) {
          console.log(`Rendered ${renderedFrames} frames`);
          last = renderedFrames;
        }
      },
    });
    const final = sample ? path.join(out, "transition.mp4") : path.join(publicOut, story.filename);
    const args = ["-hide_banner", "-y", "-i", raw];
    if (sample && frameRange) args.push("-ss", String(frameRange[0] / 30));
    args.push("-i", voice);
    args.push("-map", "0:v:0", "-map", "1:a:0");
    // Body captions are already in the approved picture. Ship SRT separately
    // so a player cannot turn on a second, overlapping subtitle layer.
    args.push(
      "-c:v",
      "copy",
      "-c:a",
      "copy",
      "-metadata:s:a:0",
      "language=eng",
      "-t",
      String(
        sample && frameRange
          ? (frameRange[1] - frameRange[0] + 1) / 30
          : timing.durationInFrames / 30,
      ),
      "-movflags",
      "+faststart",
      "-metadata",
      "title=Context is control — hermes on herdr",
      final,
    );
    const mux = spawnSync("ffmpeg", args, { encoding: "utf8" });
    await writeFile(path.join(out, "mux.log"), mux.stderr ?? "");
    if (mux.status !== 0) throw new Error(`FFmpeg mux failed: ${mux.stderr}`);
    report.output = path.relative(root, final);
    report.sha256 = createHash("sha256")
      .update(await readFile(final))
      .digest("hex");
    console.log(`Mastered ${final}`);
  }
  report.status = "complete";
} catch (error) {
  report.status = "failed";
  report.error = String(error);
  throw error;
} finally {
  await browser.close({ silent: true });
  report.finishedAt = new Date().toISOString();
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`);
}
