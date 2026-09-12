import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";
import story from "../src/story.json";
import timing from "../src/timing.json";

const output = path.resolve(import.meta.dir, "../verification/final");
const base = process.env.PREVIEW_URL ?? "http://127.0.0.1:7460/";
const movie = new URL(`review/${story.filename}`, base).href;
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: false,
});
try {
  const page = await browser.newPage({
    viewport: { width: 1536, height: 1200 },
    colorScheme: "light",
  });
  page.setDefaultTimeout(20000);
  const errors: string[] = [];
  const failed: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`);
  });
  const captionChecks = [];
  for (const id of ["intro", "context", "outro"]) {
    const shot = timing.scenes.find((s) => s.id === id);
    assert(shot);
    const frame = shot.voiceStart + 15;
    await page.goto(`${base}?frame=${frame}`, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    const count = await page.locator("[data-caption]").count();
    assert.equal(count, id === "context" ? 1 : 0, `${id}: subtitle policy`);
    await page.locator(".stage").screenshot({ path: path.join(output, `web-${id}.png`) });
    captionChecks.push({ id, frame, count });
  }
  const range = await page.request.get(movie, { headers: { Range: "bytes=0-1023" } });
  assert.equal(range.status(), 206, "The MP4 must support HTTP range requests");
  assert.equal((await range.body()).length, 1024);

  // Exercise the delivered file using Chrome's native media decoder, separate
  // from Remotion's live animation. Navigate away to dispose its audio/effects.
  await page.goto(movie, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => (document.querySelector("video")?.readyState ?? 0) >= 2);
  await page.evaluate(() => {
    const video = document.querySelector("video");
    if (!video) throw new Error("Chrome did not create a native video document");
    video.pause();
    video.currentTime = 0;
    const play = document.createElement("button");
    play.textContent = "Play final MP4";
    play.style.cssText = "position:fixed;top:0;left:0;z-index:1000";
    play.onclick = () => void video.play();
    document.body.append(play);
  });
  const metadata = await page.locator("video").evaluate((video: HTMLVideoElement) => ({
    duration: video.duration,
    width: video.videoWidth,
    height: video.videoHeight,
    muted: video.muted,
    volume: video.volume,
  }));
  assert.equal(metadata.width, 1920);
  assert.equal(metadata.height, 1080);
  assert(Math.abs(metadata.duration - timing.durationInFrames / timing.fps) < 0.05);
  assert.equal(metadata.muted, false);
  assert.equal(metadata.volume, 1);
  await page.getByRole("button", { name: "Play final MP4", exact: true }).click();
  const started = Date.now();
  const playback = [];
  let last = -1;
  for (let i = 0; i < Math.ceil(metadata.duration / 20) + 1; i++) {
    await page.waitForTimeout(20000);
    const state = await page.locator("video").evaluate((video: HTMLVideoElement) => ({
      time: video.currentTime,
      ended: video.ended,
      paused: video.paused,
      readyState: video.readyState,
      networkState: video.networkState,
      error: video.error?.message ?? null,
      audioDecodedBytes: (video as HTMLVideoElement & { webkitAudioDecodedByteCount?: number })
        .webkitAudioDecodedByteCount,
    }));
    await writeFile(path.join(output, "chrome-playback-progress.json"), JSON.stringify(state));
    assert.equal(state.error, null);
    assert(state.time > last, `Native MP4 playback stopped advancing: ${JSON.stringify(state)}`);
    assert(Math.abs(state.time - Math.min((Date.now() - started) / 1000, metadata.duration)) < 1);
    playback.push(state);
    last = state.time;
    console.log(`Native Chrome MP4: ${state.time.toFixed(1)} / ${metadata.duration}s`);
    if (state.ended) break;
  }
  assert(playback.at(-1)?.ended, "Chrome must play through the final frame");
  const quality = await page.locator("video").evaluate((video: HTMLVideoElement) => {
    const q = video.getVideoPlaybackQuality();
    return { total: q.totalVideoFrames, dropped: q.droppedVideoFrames };
  });
  assert(quality.total >= timing.durationInFrames - 2);
  assert(quality.dropped / quality.total < 0.01);
  const audioBytes = playback.at(-1)?.audioDecodedBytes;
  if (audioBytes !== undefined) assert(audioBytes > 0, "Chrome must decode the AAC track");
  await page.locator("video").evaluate((video: HTMLVideoElement) => {
    video.controls = false;
  });
  await page.locator("video").screenshot({ path: path.join(output, "chrome-final-frame.png") });
  assert.deepEqual(errors, []);
  assert.deepEqual(failed, []);
  await writeFile(
    path.join(output, "chrome.json"),
    `${JSON.stringify({ checkedAt: new Date().toISOString(), browser: await browser.version(), headed: true, movie, rangeStatus: range.status(), metadata, captionChecks, playback, quality, errors, failed }, null, 2)}\n`,
  );
  console.log("Final MP4 completed native Chrome playback; bookend subtitles absent.");
} finally {
  await browser.close();
}
