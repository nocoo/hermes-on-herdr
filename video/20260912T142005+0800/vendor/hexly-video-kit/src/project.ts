import {
	type FilmConfig,
	parseFilm,
	projectSchema,
	type TemplateId,
	type VideoProject,
} from "./schema";

/** One content adapter for every template, video and deck. No per-project template copies. */
export function createProjectFilm(
	input: VideoProject,
	template: TemplateId = "launch",
	locale: "en" | "zh" = "en",
): FilmConfig {
	const project = projectSchema.parse(input);
	const zh = locale === "zh";
	const destination = project.website ?? project.repository;
	return parseFilm({
		schemaVersion: 1,
		template,
		format: "landscape",
		fps: 30,
		motion: "full",
		project,
		scenes: [
			{
				id: "intro",
				kind: "intro",
				duration: 5,
				eyebrow: "A HEXLY PROJECT",
				title: project.name,
				body: project.summary,
			},
			{
				id: "title",
				kind: "title",
				duration: 4,
				eyebrow: zh ? "一个清晰的想法" : "ONE CLEAR IDEA",
				title: zh ? "小想法，\n自成宇宙。" : "Small ideas.\nA little universe.",
				body: project.summary,
			},
			{
				id: "chapter",
				kind: "chapter",
				duration: 4,
				eyebrow: "01 / INSIDE THE PROJECT",
				title: zh ? "从想法到细节。" : "From idea\nto detail.",
				body: zh ? `走进 ${project.name}` : `A closer look at ${project.name}.`,
			},
			{
				id: "content",
				kind: "content",
				duration: 6,
				eyebrow: zh ? "项目概览" : "PROJECT NOTES",
				title: project.name,
				body: project.summary,
			},
			{
				id: "cta",
				kind: "cta",
				duration: 5,
				eyebrow: zh ? "下一步" : "TAKE A CLOSER LOOK",
				title: zh ? "让想法发生。" : "Make room\nfor the idea.",
				body: "",
				link: {
					label: zh ? "探索项目" : "Explore the project",
					href: destination,
				},
			},
			{
				id: "logo",
				kind: "logo",
				duration: 4,
				eyebrow: "HEXLY",
				title: zh ? "留一点空间，做好一点事。" : "Space for good work.",
				body: "",
			},
			{
				id: "outro",
				kind: "outro",
				duration: 5,
				eyebrow: "HEXLY",
				title: project.name,
				body: "hexly.ai",
			},
		],
	});
}
