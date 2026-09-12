import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const timing = JSON.parse(await readFile(path.join(root, "src/generated/timing.json")));
const baseURL = process.argv[2] ?? "http://127.0.0.1:7432";
const out = path.join(root, "verification/browser");
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
await mkdir(out, { recursive: true });
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? (existsSync(chrome) ? chrome : undefined),
  args: ["--autoplay-policy=no-user-gesture-required", "--use-gl=angle"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.setDefaultTimeout(30000);
const errors = [];
const warnings = [];
page.on("pageerror", (error) => errors.push(String(error)));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
  if (message.type() === "warning") warnings.push(message.text());
});
page.on("response", (response) => {
  if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
});
const report = {
  startedAt: new Date().toISOString(),
  baseURL,
  browser: await browser.version(),
  status: "started",
  editions: {},
  errors,
  warnings,
};

async function readyVideo(seconds) {
  await page.waitForFunction((target) => {
    const video = document.querySelector(".screen > video");
    return (
      video?.readyState >= 2 &&
      !video.seeking &&
      (target === undefined || Math.abs(video.currentTime - target) < 0.08)
    );
  }, seconds);
}

async function seekVideo(seconds) {
  await page.locator(".screen > video").evaluate((video, target) => {
    video.pause();
    video.currentTime = target;
  }, seconds);
  await readyVideo(seconds);
}

try {
  await page.goto(baseURL, { waitUntil: "networkidle" });
  for (const language of ["zh", "en"]) {
    console.log(`Browser playback and downloads: ${language}`);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page
      .getByRole("button", { name: language === "zh" ? "中文" : "English", exact: true })
      .click();
    await readyVideo();
    const video = page.locator(".screen > video");
    const metadata = await video.evaluate((element) => ({
      width: element.videoWidth,
      height: element.videoHeight,
      duration: element.duration,
      source: element.currentSrc,
    }));
    assert.deepEqual([metadata.width, metadata.height], [timing.width, timing.height]);
    assert.ok(Math.abs(metadata.duration - timing.durationInFrames / timing.fps) < 0.05);
    assert.ok(metadata.source.endsWith(`-${language}.mp4`));
    const range = await page.request.get(metadata.source, { headers: { Range: "bytes=0-1023" } });
    assert.equal(range.status(), 206);
    assert.equal((await range.body()).length, 1024);

    await seekVideo(timing.audio[language][0].fromFrame / timing.fps + 0.4);
    const playback = await video.evaluate(async (element) => {
      const context = new AudioContext();
      const analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      context.createMediaElementSource(element).connect(analyser);
      analyser.connect(context.destination);
      element.muted = false;
      element.volume = 1;
      await context.resume();
      await element.play();
      const start = element.currentTime;
      const values = new Float32Array(analyser.fftSize);
      const rms = [];
      for (let index = 0; index < 24; index++) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        analyser.getFloatTimeDomainData(values);
        rms.push(
          Math.sqrt(values.reduce((sum, sample) => sum + sample * sample, 0) / values.length),
        );
      }
      element.pause();
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 180;
      const draw = canvas.getContext("2d");
      draw.drawImage(element, 0, 0, canvas.width, canvas.height);
      const pixels = draw.getImageData(0, 0, canvas.width, canvas.height).data;
      let luma = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        luma += 0.2126 * pixels[i] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i + 2];
      }
      const result = {
        secondsAdvanced: element.currentTime - start,
        audioRmsMean: rms.reduce((sum, value) => sum + value, 0) / rms.length,
        audioRmsMax: Math.max(...rms),
        decodedFrameMeanLuma: luma / (canvas.width * canvas.height),
        decodedFrames: element.getVideoPlaybackQuality().totalVideoFrames,
      };
      await context.close();
      return result;
    });
    assert.ok(playback.secondsAdvanced >= 0.9, "The actual MP4 must advance while playing");
    assert.ok(playback.audioRmsMean > 0.01, "The decoded audio must contain a real signal");
    assert.ok(playback.decodedFrames >= 10 && playback.decodedFrameMeanLuma > 10);
    await video.evaluate((element) => {
      element.textTracks[0].mode = "hidden";
    });
    await page.waitForFunction(
      (count) => document.querySelector(".screen > video")?.textTracks[0]?.cues?.length === count,
      timing.captions[language].length,
    );

    const chapters = [];
    for (const scene of timing.scenes) {
      await page.locator(".chapter").nth(scene.index).click();
      await readyVideo(scene.start / timing.fps);
      assert.equal(
        await page.locator(".chapter").nth(scene.index).getAttribute("aria-pressed"),
        "true",
      );
      chapters.push({
        scene: scene.id,
        seconds: await video.evaluate((element) => element.currentTime),
      });
    }

    const downloads = [];
    for (const link of await page.locator(".downloads a").all()) {
      const href = await link.getAttribute("href");
      const pending = page.waitForEvent("download");
      await link.click();
      const download = await pending;
      assert.equal(await download.failure(), null);
      const bytes = await readFile(await download.path());
      const expected = await readFile(path.join(root, "public", href));
      assert.equal(sha(bytes), sha(expected));
      downloads.push({
        file: download.suggestedFilename(),
        bytes: bytes.length,
        sha256: sha(bytes),
      });
      await download.delete();
    }

    const monitorTime =
      timing.scenes.find((scene) => scene.id === "monitor").start / timing.fps + 2.5;
    await seekVideo(monitorTime);
    if (language === "zh") {
      await page.getByRole("button", { name: "English", exact: true }).click();
      await readyVideo(monitorTime);
      await page.getByRole("button", { name: "中文", exact: true }).click();
      await readyVideo(monitorTime);
      report.languageSwitch = "preserved 83-second position in both directions";
    }
    await page
      .getByRole("button", {
        name: language === "zh" ? "实时动画" : "Live composition",
        exact: true,
      })
      .click();
    await page.locator(".screen canvas").waitFor();
    const caption = timing.captions[language].find(
      (line) => monitorTime >= line.start && monitorTime < line.end,
    );
    await page.waitForFunction(
      (text) => document.querySelector(".film-caption span")?.textContent === text,
      caption.text,
    );
    // A new canvas starts with the browser's default 300 x 150 buffer until
    // ThreeCanvas finishes initializing its configured full-frame renderer.
    await page.waitForFunction(
      ([width, height]) => {
        const element = document.querySelector(".screen canvas");
        return element?.width === width && element.height === height;
      },
      [timing.width, timing.height],
    );
    const canvas = await page
      .locator(".screen canvas")
      .evaluate((element) => ({ width: element.width, height: element.height }));
    assert.deepEqual([canvas.width, canvas.height], [timing.width, timing.height]);
    await page
      .locator(".screen-section")
      .screenshot({ path: path.join(out, `live-${language}.png`) });
    await page
      .getByRole("button", { name: language === "zh" ? "成片" : "Film", exact: true })
      .click();
    await readyVideo(monitorTime);
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        Array.from(document.querySelectorAll(".chapter img"), (image) => {
          image.loading = "eager";
          return image.decode();
        }),
      );
      window.scrollTo(0, 0);
    });
    await page.screenshot({ path: path.join(out, `desktop-${language}.png`), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    // Decode moving frames at the narrow viewport as well, so the screenshot
    // does not capture Chrome's temporary spinner while resizing the video.
    const mobileStart = await page.locator(".screen > video").evaluate(async (element) => {
      await element.play();
      return element.currentTime;
    });
    await page.waitForFunction(
      (start) => document.querySelector(".screen > video")?.currentTime > start + 0.5,
      mobileStart,
    );
    const mobilePlayback = await page.locator(".screen > video").evaluate((element) => {
      element.pause();
      return element.currentTime;
    });
    const mobile = await page.evaluate(() => ({
      viewport: innerWidth,
      content: document.documentElement.scrollWidth,
    }));
    mobile.playedSeconds = mobilePlayback - mobileStart;
    assert.ok(mobile.content <= mobile.viewport, `Horizontal overflow: ${JSON.stringify(mobile)}`);
    await page.screenshot({ path: path.join(out, `mobile-${language}.png`), fullPage: true });
    report.editions[language] = {
      metadata,
      range: range.headers()["content-range"],
      playback,
      captions: timing.captions[language].length,
      chapters,
      downloads,
      liveCanvas: canvas,
      mobile,
    };
  }
  assert.deepEqual(errors, []);
  report.status = "passed";
  await rm(path.join(out, "failure.png"), { force: true });
  console.log(
    "PASS: bilingual playback/audio, captions, range requests, all chapters, downloads, live composition and mobile layout",
  );
} catch (error) {
  report.status = "failed";
  report.failure = String(error);
  await page.screenshot({ path: path.join(out, "failure.png"), fullPage: true });
  throw error;
} finally {
  report.completedAt = new Date().toISOString();
  await writeFile(
    path.join(root, "verification/browser.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  await browser.close();
}
