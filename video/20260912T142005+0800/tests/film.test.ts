import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dimensions, durationFor, hexly, parseFilm, revealState } from "@hexly/video-kit";
import { curvePoint } from "../src/art/Flow";
import { captionAt, displayCaptions } from "../src/captions";
import { shotAt, story, timing } from "../src/timeline";

test("every measured audio clip fits its shot and subtitles keep the exact narration", () => {
  const sourceHash = createHash("sha256")
    .update(readFileSync(new URL("../src/story.json", import.meta.url)))
    .digest("hex");
  expect(timing.storySha256).toBe(sourceHash);
  expect(timing.audio.length).toBe(story.scenes.flatMap((s) => s.narration).length);
  let end = 0;
  for (const [index, shot] of timing.scenes.entries()) {
    expect(shot.start).toBe(end);
    expect(shotAt(shot.start).scene.id).toBe(shot.id);
    expect(shotAt(shot.start + shot.duration - 1).scene.id).toBe(shot.id);
    expect(shot.voiceEnd).toBeLessThanOrEqual(shot.start + shot.duration - 20);
    const clips = timing.audio.filter((clip) => clip.scene === shot.id);
    const scene = story.scenes[index];
    if (!scene) throw new Error("Missing story scene");
    expect(clips.map((clip) => clip.text)).toEqual(scene.narration);
    for (const clip of clips) {
      expect(clip.fromFrame).toBeGreaterThanOrEqual(shot.start);
      expect(clip.fromFrame + clip.durationFrames).toBeLessThanOrEqual(shot.start + shot.duration);
      const bytes = readFileSync(new URL(`../public/${clip.file}`, import.meta.url));
      expect(createHash("sha256").update(bytes).digest("hex")).toBe(clip.sha256);
    }
    end += shot.duration;
  }
  expect(end).toBe(timing.durationInFrames);
  for (const [i, caption] of timing.captions.entries()) {
    const clip = timing.audio[i];
    if (!clip) throw new Error("Missing caption clip");
    expect(caption.text).toBe(clip.text);
    expect(caption.end).toBeGreaterThan(caption.start);
    if (i > 0) expect(caption.start).toBeGreaterThanOrEqual(timing.captions[i - 1]?.end ?? 0);
  }
  expect(() => shotAt(-1)).toThrow();
  expect(() => shotAt(timing.durationInFrames)).toThrow();
});

test("signal paths have exact endpoints and shorter captions preserve all words", () => {
  const curve = [
    [0, 0],
    [20, 80],
    [60, 10],
    [100, 100],
  ] as const;
  expect(curvePoint(curve, 0)).toEqual([0, 0]);
  expect(curvePoint(curve, 1)).toEqual([100, 100]);
  expect(curvePoint(curve, 0.5).every(Number.isFinite)).toBe(true);
  for (const original of timing.captions) {
    const phrases = displayCaptions.filter(
      (c) => c.start >= original.start && c.end <= original.end,
    );
    expect(phrases.map((c) => c.text).join(" ")).toBe(original.text);
    expect(phrases[0]?.start).toBe(original.start);
    expect(phrases.at(-1)?.end).toBe(original.end);
    for (const phrase of phrases) {
      expect(phrase.text.length).toBeLessThanOrEqual(72);
      expect(captionAt((phrase.start + phrase.end) / 2)?.text).toBe(phrase.text);
    }
  }
});

test("the published package supplies the exact brand and mark-first reveal", () => {
  expect(hexly.page).toBe("#f0f0e9");
  expect(hexly.accent).toBe("#bf5c3c");
  expect(revealState(30, 30)).toEqual({ mark: 1, expand: 0, caption: 0 });
  expect(revealState(37, 30).expand).toBe(0);
  expect(revealState(54, 30).expand).toBeGreaterThan(0);
  expect(revealState(74, 30).caption).toBe(0);
  expect(revealState(110, 30)).toEqual({ mark: 1, expand: 1, caption: 1 });
  expect(dimensions("landscape")).toEqual({ width: 1920, height: 1080 });
  const config = parseFilm({
    schemaVersion: 1,
    template: "essential",
    format: "landscape",
    fps: 30,
    motion: "full",
    project: {
      id: "hermes-on-herdr",
      name: story.product,
      summary: story.title,
      repository: story.repository,
      website: null,
      colors: [hexly.page, hexly.ink],
      technologies: [],
      facts: [],
      sourceNote: "Consumer test of the published package, not a separate film.",
    },
    scenes: [
      {
        id: "intro",
        kind: "intro",
        duration: 4,
        title: story.title,
        eyebrow: story.product,
        body: "",
      },
    ],
  });
  expect(durationFor(config)).toBe(120);
  expect(() => parseFilm({ ...config, scenes: [config.scenes[0], config.scenes[0]] })).toThrow();
});
