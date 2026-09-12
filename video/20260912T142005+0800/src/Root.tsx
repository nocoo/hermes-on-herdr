import { Composition } from "remotion";
import { Film, filmMetadata } from "./Film";
import { story } from "./timeline";

export function Root() {
  return (
    <Composition
      id={story.composition}
      component={Film}
      {...filmMetadata}
      defaultProps={{ captions: true, audio: true }}
    />
  );
}
