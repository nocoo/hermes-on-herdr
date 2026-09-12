import rawTiming from "./generated/timing.json";
import story from "./story.json";

export { story };
export type Language = "zh" | "en";
type Caption = { scene: string; start: number; end: number; text: string };
export const timing = rawTiming as {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  scenes: {
    id: string;
    index: number;
    start: number;
    duration: number;
    keyframe: number;
    voiceStart: number;
    voiceEnd: number;
  }[];
  captions: Record<Language, Caption[]>;
};
export const clamp = (value: number) => Math.max(0, Math.min(1, value));
export const mix = (a: number, b: number, t: number) => a + (b - a) * t;
export const smooth = (value: number) => {
  const t = clamp(value);
  return t * t * t * (t * (t * 6 - 15) + 10);
};

export const artCenter = (index: number) => {
  return [1320, 1290, 585, 1290, 575, 1320, 590, 1310, 1290, 1320][index] ?? 1320;
};

export function sceneAt(frame: number) {
  const index = Math.max(
    0,
    timing.scenes.findLastIndex((scene) => frame >= scene.start),
  );
  const scene = timing.scenes[index];
  const local = frame - scene.start;
  const entry = smooth(local / 32);
  const exit =
    index === timing.scenes.length - 1 ? 1 : 1 - smooth((local - scene.duration + 20) / 20);
  const previous = Math.max(0, index - 1);
  const center = mix(artCenter(previous), artCenter(index), smooth(local / 42));
  return { index, scene, local, entry, exit, center: index === 0 ? artCenter(0) : center };
}
