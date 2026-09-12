import story from "./story.json";
import timing from "./timing.json";

export { story, timing };
export type StoryScene = (typeof story.scenes)[number];
export type Shot = (typeof timing.scenes)[number];
export type SceneId = StoryScene["id"];

export function shotAt(frame: number) {
  const shot = timing.scenes.find((s) => frame >= s.start && frame < s.start + s.duration);
  if (!shot) throw new RangeError(`Frame ${frame} is outside the measured timeline`);
  const scene = story.scenes[shot.index];
  if (!scene || scene.id !== shot.id) throw new Error("Story/timing scene mismatch");
  return { shot, scene, local: frame - shot.start };
}

export const clamp = (v: number) => Math.min(1, Math.max(0, v));
export function smooth(v: number) {
  const t = clamp(v);
  return t * t * t * (t * (t * 6 - 15) + 10);
}
export const between = (time: number, start: number, end: number) =>
  smooth((time - start) / (end - start));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
