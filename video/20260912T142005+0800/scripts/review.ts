import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";
import sharp from "sharp";
import timing from "../src/timing.json";

const root = path.resolve(import.meta.dir, "..");
const output = path.join(root, "verification/preview-02");
await mkdir(output, { recursive: true });
const base = process.env.PREVIEW_URL ?? "http://127.0.0.1:7460/";
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: process.env.HEADED !== "1",
});
const errors: string[] = [];
const failed: string[] = [];
const page = await browser.newPage({
  viewport: { width: 1536, height: 1200 },
  colorScheme: "light",
});
page.on("pageerror", (e) => errors.push(e.message));
page.on("response", (r) => {
  if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`);
});
page.setDefaultTimeout(15000);
const shots = [];

try {
  for (const shot of timing.scenes) {
    await page.goto(`${base}?preview=2&frame=${shot.keyframe}`, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    const details = await page.evaluate(() => {
      const film = document.querySelector("[data-film-frame]");
      if (!film) throw new Error("Missing live composition");
      const bounds = film.getBoundingClientRect();
      const outside: string[] = [];
      for (const node of film.querySelectorAll(
        "[data-flow-label], [data-shot-title], [data-caption]",
      )) {
        const range = document.createRange();
        range.selectNodeContents(node);
        const b = range.getBoundingClientRect();
        if (
          b.left < bounds.left - 1 ||
          b.right > bounds.right + 1 ||
          b.top < bounds.top - 1 ||
          b.bottom > bounds.bottom + 1
        )
          outside.push(node.textContent ?? "");
      }
      const logos = Array.from(
        film.querySelectorAll<HTMLImageElement>("[data-product-logo] img"),
      ).map((img) => ({
        name: img.alt,
        loaded: img.complete && img.naturalWidth > 0,
        fit: getComputedStyle(img).objectFit,
      }));
      const caption = film.querySelector("[data-caption]");
      return {
        outside,
        logos,
        canvasCount: film.querySelectorAll("canvas").length,
        captionBackground: caption ? getComputedStyle(caption).backgroundColor : null,
        captionText: caption?.textContent ?? null,
      };
    });
    assert.deepEqual(details.outside, [], `Text overflow: ${shot.id}`);
    assert.equal(details.canvasCount, 0, "The new composition has no WebGL canvas");
    assert(
      details.logos.every((logo) => logo.loaded && logo.fit === "contain"),
      `Missing/distorted logo: ${shot.id}`,
    );
    assert(
      details.captionBackground === null || details.captionBackground === "rgba(0, 0, 0, 0)",
      "Subtitle must have no background",
    );
    await page.locator(".stage").screenshot({
      path: path.join(output, `${shot.index.toString().padStart(2, "0")}-${shot.id}.png`),
    });
    shots.push({ id: shot.id, frame: shot.keyframe, ...details });
  }

  // Fully expanded output must equal the same official wordmark with no mask.
  // Capture beyond the line box to include descenders, rather than checking CSS alone.
  const wordmark = page.locator("[data-hexly-wordmark]");
  const box = await wordmark.boundingBox();
  assert(box, "Missing Hexly wordmark");
  const clip = {
    x: Math.floor(box.x - 8),
    y: Math.floor(box.y - 40),
    width: Math.ceil(box.width + 16),
    height: Math.ceil(box.height + 80),
  };
  const fixed = await page.screenshot({ clip, path: path.join(output, "hexly-y-fixed.png") });
  await page.addStyleTag({
    content: "[data-hexly-wordmark] { clip-path: none !important; overflow: visible !important; }",
  });
  const reference = await page.screenshot({
    clip,
    path: path.join(output, "hexly-y-unmasked-reference.png"),
  });
  const a = await sharp(fixed).raw().toBuffer();
  const b = await sharp(reference).raw().toBuffer();
  assert.equal(a.length, b.length);
  let differences = 0;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) differences++;
  assert.equal(differences, 0, "The expanded wordmark must preserve every pixel, including y");

  const outro = timing.scenes.at(-1);
  assert(outro);
  await page.goto(`${base}?preview=2&frame=${outro.start + 30}`, { waitUntil: "networkidle" });
  const markOnly = await page
    .locator("[data-hexly-wordmark]")
    .evaluate((el) => Number(getComputedStyle(el).opacity));
  assert.equal(markOnly, 0, "Mark must appear alone before 1.25 seconds");
  await page.locator(".stage").screenshot({ path: path.join(output, "hexly-mark-only.png") });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}?preview=2&frame=567`, { waitUntil: "networkidle" });
  const mobileOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  assert.equal(mobileOverflow, false);
  await page.screenshot({ path: path.join(output, "mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "CC", exact: true }).click();
  assert.equal(await page.locator("[data-caption]").count(), 0);
  await page.locator(".chapters button").nth(5).click();
  await page.waitForFunction(
    () =>
      document.querySelector("[data-film-scene]")?.getAttribute("data-film-scene") === "channels",
  );
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  await page.setViewportSize({ width: 1536, height: 1200 });
  await page.goto(`${base}?preview=2`, { waitUntil: "networkidle" });
  await page.screenshot({ path: path.join(output, "desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "Play", exact: true }).click();
  const playbackStarted = Date.now();
  let last = -1;
  const motion = [];
  for (let i = 0; i < 7; i++) {
    await page.waitForTimeout(15000);
    const frame = Number(await page.locator("[data-film-frame]").getAttribute("data-film-frame"));
    assert(frame > last, "Live playback stopped advancing");
    const elapsed = (Date.now() - playbackStarted) / 1000;
    const expectedFrame = Math.min(timing.durationInFrames - 1, Math.round(elapsed * 30));
    assert(
      Math.abs(frame - expectedFrame) < 18,
      "Preview must follow the 30 fps wall-clock timeline",
    );
    motion.push({ frame, elapsed });
    last = frame;
    console.log(`Chrome playback frame ${frame} / ${timing.durationInFrames - 1}`);
    if (frame >= timing.durationInFrames - 2) break;
  }
  assert(last >= timing.durationInFrames - 2, "Complete live playback must reach the ending");
  assert.deepEqual(errors, []);
  assert.deepEqual(failed, []);
  await writeFile(
    path.join(output, "browser.json"),
    `${JSON.stringify({ checkedAt: new Date().toISOString(), browser: await browser.version(), base, scope: "Live Chrome preview and still screenshots only. No MP4 recording or final render.", shots, unmaskedWordmarkPixelDifferences: differences, markOnlyWordmarkOpacity: markOnly, mobileOverflow, playbackFrames: motion, errors, failed }, null, 2)}\n`,
  );
  console.log("Preview review passed; no video recorded.");
} finally {
  await browser.close();
}
