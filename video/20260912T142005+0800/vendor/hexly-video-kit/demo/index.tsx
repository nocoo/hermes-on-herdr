import { Composition, registerRoot } from "remotion";
import example from "../examples/hexly.json";
import { Film } from "../src/Film";
import { createProjectFilm } from "../src/project";
import {
	dimensions,
	durationFor,
	filmSchema,
	parseFilm,
	templateIds,
} from "../src/schema";

function Root() {
	return (
		<>
			{templateIds.map((template) => {
				const film = createProjectFilm(example, template);
				return (
					<Composition
						key={template}
						id={`Hexly-${template}`}
						component={Film}
						schema={filmSchema}
						defaultProps={film}
						fps={film.fps}
						durationInFrames={durationFor(film)}
						{...dimensions(film.format)}
						calculateMetadata={({ props }) => {
							const config = parseFilm(props);
							return {
								props: config,
								fps: config.fps,
								durationInFrames: durationFor(config),
								...dimensions(config.format),
							};
						}}
					/>
				);
			})}
		</>
	);
}
registerRoot(Root);
