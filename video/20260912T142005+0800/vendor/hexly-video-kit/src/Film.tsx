import { AbsoluteFill, Sequence } from "remotion";
import { themes } from "./brand";
import { sceneComponents } from "./Scenes";
import { type FilmConfig, timelineFor } from "./schema";

/** Pass parseFilm() output. Consumers can also compose the exported scenes with Sequence. */
export function Film(config: FilmConfig) {
	return (
		<AbsoluteFill style={{ background: themes[config.template].palette.page }}>
			{timelineFor(config).map((scene, index) => {
				const Component = sceneComponents[scene.kind];
				return (
					<Sequence
						key={scene.id}
						name={scene.title}
						from={scene.from}
						durationInFrames={scene.durationInFrames}
					>
						<Component
							{...scene}
							index={index}
							project={config.project}
							template={config.template}
							motion={config.motion}
						/>
					</Sequence>
				);
			})}
		</AbsoluteFill>
	);
}
