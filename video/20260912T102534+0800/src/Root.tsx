import { Composition } from "remotion";
import { Film } from "./Film";
import { timing } from "./timeline";

export function Root() {
  return (
    <>
      {/* biome-ignore lint/correctness/useUniqueElementIds: Remotion export names must be stable; these are not DOM IDs. */}
      <Composition
        id="HermesWeekendZH"
        component={Film}
        durationInFrames={timing.durationInFrames}
        fps={timing.fps}
        width={1920}
        height={1080}
        defaultProps={{ language: "zh" as const, captions: true, audio: true }}
      />
      {/* biome-ignore lint/correctness/useUniqueElementIds: Remotion export names must be stable; these are not DOM IDs. */}
      <Composition
        id="HermesWeekendEN"
        component={Film}
        durationInFrames={timing.durationInFrames}
        fps={timing.fps}
        width={1920}
        height={1080}
        defaultProps={{ language: "en" as const, captions: true, audio: true }}
      />
    </>
  );
}
