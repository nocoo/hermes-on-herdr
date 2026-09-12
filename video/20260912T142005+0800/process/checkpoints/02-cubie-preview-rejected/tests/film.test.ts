import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dimensions, durationFor, hexly, parseFilm, revealState } from "@hexly/video-kit";
import { assembledCube, grid, quarterTurn, sceneCubies } from "../src/art/cube";
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

test("quarter turns preserve all 27 cells and the final cube is complete", () => {
  expect(grid.length).toBe(27);
  const result = assembledCube(8);
  const cells = result.map((c) => c.position.map((n) => Math.round(n / 1.075)).join(","));
  expect(new Set(cells).size).toBe(27);
  expect(new Set(cells)).toEqual(new Set(grid.map((p) => p.join(","))));
  for (const cube of result) {
    for (const n of cube.position) expect(Math.abs(n)).toBeLessThan(1.076);
  }
  const turned = quarterTurn([1, 0, 0], [0, 0, 0], "y", Math.PI * 2);
  expect(turned.position[0]).toBeCloseTo(1, 9);
  expect(turned.position[2]).toBeCloseTo(0, 9);
  expect(assembledCube(4.1)).toEqual(assembledCube(4.1));
  for (const scene of story.scenes)
    for (const t of [0, 0.5, 2.7, 4.1, 5.3, 8]) {
      const cubes = sceneCubies(scene.id, t);
      expect(new Set(cubes.map((c) => c.id)).size).toBe(cubes.length);
      expect(
        cubes.every((c) => [...c.position, ...c.rotation, c.scale].every(Number.isFinite)),
      ).toBe(true);
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
    template: "studio",
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
