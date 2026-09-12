import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (file) => readFileSync(path.join(root, file));
const story = JSON.parse(read("src/story.json"));
const timing = JSON.parse(read("src/generated/timing.json"));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");

test("both editions use a measured, contiguous full-HD timeline", () => {
  assert.equal(timing.provisional, undefined);
  assert.deepEqual([timing.width, timing.height, timing.fps], [1920, 1080, 30]);
  assert.equal(timing.sourceStorySha256, sha(read("src/story.json")));
  assert.equal(timing.scenes.length, story.scenes.length);
  let end = 0;
  for (const [index, scene] of timing.scenes.entries()) {
    assert.equal(scene.id, story.scenes[index].id);
    assert.equal(scene.start, end);
    assert.ok(Number.isInteger(scene.duration) && scene.duration > 0);
    assert.ok(scene.keyframe > scene.start && scene.keyframe < scene.start + scene.duration);
    assert.ok(scene.voiceEnd <= scene.start + scene.duration - 25);
    assert.ok(story.scenes[index].source.length > 0);
    end += scene.duration;
  }
  assert.equal(end, timing.durationInFrames);
});

for (const language of ["zh", "en"]) {
  test(`${language}: complete speech, unmodified voice assets and aligned non-overlapping captions`, () => {
    const expected = story.scenes.flatMap((scene) => scene.narration[language]);
    const clips = timing.audio[language];
    const captions = timing.captions[language];
    assert.deepEqual(
      clips.map((clip) => clip.text),
      expected,
    );
    const written =
      language === "en"
        ? expected.map((line) => line.replaceAll("M two", "M2").replaceAll("T U I", "TUI"))
        : expected;
    assert.deepEqual(
      captions.map((line) => line.text),
      written,
    );
    let end = 0;
    clips.forEach((clip, index) => {
      const scene = timing.scenes.find((item) => item.id === clip.scene);
      assert.ok(scene);
      assert.ok(clip.fromFrame >= end);
      assert.ok(clip.fromFrame + clip.durationFrames <= scene.start + scene.duration - 25);
      assert.ok(clip.durationSeconds > 0.5);
      assert.ok(clip.durationFrames >= clip.durationSeconds * timing.fps);
      const metadata = JSON.parse(read(`public/${clip.file.replace(/\.wav$/, ".json")}`));
      assert.equal(clip.sha256, sha(read(`public/${clip.file}`)));
      assert.equal(clip.text, metadata.text);
      assert.deepEqual(metadata.voice, story.voices[language]);
      assert.equal(captions[index].start, clip.fromFrame / timing.fps);
      assert.equal(captions[index].end, (clip.fromFrame + clip.durationFrames) / timing.fps);
      end = clip.fromFrame + clip.durationFrames;
    });
    assert.equal(
      read(`public/audio/narration-${language}.srt`).toString().match(/ --> /g).length,
      expected.length,
    );
  });
}
