import { Composition } from "remotion";
import { Film } from "./Film";
import { timing } from "./timeline";

export function Root() {
  return (
    <>
      <Composition
        id="HermesWeekendZH"
        component={Film}
        durationInFrames={timing.durationInFrames}
        fps={timing.fps}
        width={1920}
        height={1080}
        defaultProps={{ language: "zh" as const, captions: true, audio: true }}
      />
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
