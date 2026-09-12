import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

const output = path.resolve(import.meta.dir, "../verification/preview-02");
const base = process.env.PREVIEW_URL ?? "http://127.0.0.1:7460/";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: false,
});

try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
    colorScheme: "dark",
  });
  page.setDefaultTimeout(15000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const frame = () =>
    page.locator("[data-film-frame]").getAttribute("data-film-frame").then(Number);

  await page.goto(`${base}?preview=2`, { waitUntil: "networkidle" });
  assert.equal(await frame(), 60, "Initial preview must show the cover");
  await page.getByRole("button", { name: "Fullscreen", exact: true }).click();
  await page.waitForFunction(() => document.fullscreenElement !== null);
  await page.keyboard.press("Space");
  await page.waitForFunction(
    () => Number(document.querySelector("[data-film-frame]")?.getAttribute("data-film-frame")) < 60,
  );
  const restartedAt = await frame();
  await page.waitForFunction(
    () => Number(document.querySelector("[data-film-frame]")?.getAttribute("data-film-frame")) > 65,
  );
  await page.keyboard.press("Space");
  await page.getByRole("button", { name: "Play", exact: true }).waitFor({ state: "attached" });
  const pausedAt = await frame();
  await page.waitForTimeout(600);
  assert.equal(await frame(), pausedAt, "Space must pause fullscreen playback");
  await page.keyboard.press("Space");
  await page.waitForFunction(
    (previous) =>
      Number(document.querySelector("[data-film-frame]")?.getAttribute("data-film-frame")) >
      previous + 20,
    pausedAt,
  );
  const resumedAt = await frame();
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.fullscreenElement === null);
  await page.getByRole("button", { name: "Pause", exact: true }).click();

  // A dark desktop preference must not invert the official Pi SVG in this light film.
  await page.goto(`${base}?preview=2&frame=567`, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  const scheme = await page
    .locator("[data-film-frame]")
    .evaluate((element) => getComputedStyle(element).colorScheme);
  assert.equal(scheme, "light");
  await page.locator(".stage").screenshot({
    path: path.join(output, "dark-system-light-film.png"),
  });
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(output, "headed-controls.json"),
    `${JSON.stringify({ checkedAt: new Date().toISOString(), browser: await browser.version(), base, headed: true, scope: "Live fullscreen controls and still screenshot; no video recording.", restartedAt, pausedAt, resumedAt, escapeExitedFullscreen: true, systemColorScheme: "dark", filmColorScheme: scheme, errors }, null, 2)}\n`,
  );
  console.log("Headed Chrome fullscreen play/pause/resume/Escape passed. No video recorded.");
} finally {
  await browser.close();
}
