// Static asset inspection only. No Remotion import, voice generation or video render.
import {mkdtemp, mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {chromium} from 'playwright-core';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const chrome = process.env.ASSET_CHROME_PATH || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium',
].find(existsSync);
if (!chrome) throw new Error('Install Chrome/Chromium or set ASSET_CHROME_PATH');
await mkdir(join(root, '.cache'), {recursive: true});
const profile = await mkdtemp(join(root, '.cache', 'asset-chrome-'));
const browser = await chromium.launchPersistentContext(profile, {
  executablePath: chrome, headless: true, deviceScaleFactor: 1,
  args: ['--force-color-profile=srgb', '--disable-background-networking'],
  timeout: 30000,
});
const captures = [];
const errors = [];
const externalRequests = new Set();
try {
  const page = await browser.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (/^https?:/.test(request.url())) externalRequests.add(request.url());
  });
  const targets = [];
  for (const name of ['cli-contact-sheet', 'cubie-contact-sheet']) {
    const source = `public/review/${name}.svg`;
    const svg = await readFile(join(root, source), 'utf8');
    const width = Number(svg.match(/\bwidth="(\d+)"/)[1]);
    const height = Number(svg.match(/\bheight="(\d+)"/)[1]);
    targets.push({source, width, height, file: `public/review/${name}.png`});
  }
  targets.push(
    {source: 'index.html', width: 1920, height: 1080, file: 'verification/gallery-desktop.png'},
    {source: 'index.html', width: 390, height: 844, file: 'verification/gallery-mobile.png'},
  );
  for (const target of targets) {
    await page.setViewportSize({width: target.width, height: target.height});
    await page.goto(pathToFileURL(join(root, target.source)).href, {waitUntil: 'load', timeout: 30000});
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map(image => image.decode()));
    });
    const layout = await page.evaluate(() => ({
      width: innerWidth, contentWidth: document.documentElement.scrollWidth,
      imageCount: document.images.length,
      brokenImages: [...document.images].filter(image => !image.naturalWidth).length,
      fontStatus: document.fonts.status,
    }));
    if (layout.contentWidth > target.width || layout.brokenImages) {
      throw new Error(`Layout failure for ${target.source}: ${JSON.stringify(layout)}`);
    }
    const data = await page.screenshot({path: join(root, target.file), animations: 'disabled'});
    if (data.readUInt32BE(16) !== target.width || data.readUInt32BE(20) !== target.height) {
      throw new Error(`Unexpected PNG dimensions: ${target.file}`);
    }
    captures.push({...target, sha256: createHash('sha256').update(data).digest('hex'), bytes: data.length, layout});
    console.log(`captured ${target.file} (${target.width} x ${target.height})`);
  }
  if (errors.length || externalRequests.size) {
    throw new Error(`Preview must be self-contained: ${JSON.stringify({errors, externalRequests: [...externalRequests]})}`);
  }
  await writeFile(join(root, 'verification/browser.json'), JSON.stringify({
    mode: 'static-assets-only', browser: browser.browser()?.version(),
    capturedAt: new Date().toISOString(), captures, pageErrors: errors,
    externalRequests: [...externalRequests],
    note: 'Native SVG sizes and responsive gallery viewports; no film, speech or motion render.',
  }, null, 2) + '\n');
} finally {
  await browser.close();
  await rm(profile, {recursive: true, force: true});
}
