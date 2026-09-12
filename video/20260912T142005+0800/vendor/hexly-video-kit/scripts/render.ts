import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
	existsSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	statSync,
	writeFileSync,
} from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { bundle } from "@remotion/bundler";
import {
	renderMedia,
	renderStill,
	selectComposition,
} from "@remotion/renderer";
import { PDFDocument } from "pdf-lib";
import pptxgen from "pptxgenjs";
import sharp from "sharp";
import example from "../examples/hexly.json";
import { hexly, kitVersion } from "../src/brand";
import { createProjectFilm } from "../src/project";
import {
	type FilmConfig,
	parseFilm,
	templateIds,
	timelineFor,
} from "../src/schema";

const { values } = parseArgs({
	args: process.argv.slice(2).filter((arg) => arg !== "--"),
	options: {
		example: { type: "string" },
		props: { type: "string" },
		out: { type: "string" },
		"public-dir": { type: "string" },
		mode: { type: "string", default: "all" },
		scale: { type: "string", default: "0.5" },
	},
});
const root = fileURLToPath(new URL("../", import.meta.url));
const mode = values.mode;
if (!["all", "video", "deck", "stills"].includes(mode))
	throw new Error("Use --mode all|video|deck|stills.");
const scale = Number(values.scale);
if (![0.5, 1].includes(scale))
	throw new Error("Use --scale 0.5 (preview) or 1 (full resolution).");
const stamp = new Date().toISOString().replace(/[:.]/g, "-");
const output = resolve(values.out ?? join(root, "outputs", stamp));
if (existsSync(output))
	throw new Error(`Output exists; choose a fresh --out directory: ${output}`);
if (output.startsWith(join(root, "public")))
	throw new Error(
		"Render outside public/. Publish reviewed assets separately.",
	);
const selected = values.example ?? "launch";
if (
	!values.props &&
	selected !== "all" &&
	!templateIds.includes(selected as FilmConfig["template"])
)
	throw new Error("Unknown template.");
const films = values.props
	? [parseFilm(JSON.parse(readFileSync(resolve(values.props), "utf8")))]
	: (selected === "all"
			? templateIds
			: [selected as FilmConfig["template"]]
		).map((id) => createProjectFilm(example, id));
mkdirSync(output, { recursive: true });
const publicDir = resolve(values["public-dir"] ?? join(root, "public"));
const browserExecutable =
	process.env.CHROME_PATH ??
	(existsSync("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
		? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
		: undefined);
const serveUrl = await bundle({
	entryPoint: join(root, "demo/index.tsx"),
	publicDir,
	outDir: join(root, ".cache/remotion", stamp),
});
const reports: unknown[] = [];

for (const film of films) {
	const startedAt = new Date().toISOString();
	const destination = join(output, film.template);
	mkdirSync(join(destination, "frames"), { recursive: true });
	const composition = await selectComposition({
		serveUrl,
		id: `Hexly-${film.template}`,
		inputProps: film,
		browserExecutable,
	});
	const common = { serveUrl, composition, browserExecutable, scale };
	const stillFilm: FilmConfig = { ...film, motion: "reduced" };
	const stillComposition = await selectComposition({
		serveUrl,
		id: `Hexly-${film.template}`,
		inputProps: stillFilm,
		browserExecutable,
	});
	const scenes = timelineFor(film);
	const frames: string[] = [];
	for (const [index, scene] of scenes.entries()) {
		const filename = join(
			destination,
			"frames",
			`${String(index + 1).padStart(2, "0")}-${scene.id}.png`,
		);
		// Deck is an explicit still layout: all elements are settled, including the logo.
		await renderStill({
			...common,
			composition: stillComposition,
			inputProps: stillFilm,
			frame: scene.from + 1,
			imageFormat: "png",
			output: filename,
		});
		frames.push(filename);
	}
	const first = frames[0];
	if (!first) throw new Error("Missing cover frame.");
	await sharp(first)
		.webp({ quality: 88 })
		.toFile(join(destination, "poster.webp"));
	const columns = 3;
	const thumbWidth = film.format === "portrait" ? 225 : 384;
	const thumbHeight = film.format === "portrait" ? 400 : 216;
	const gap = 16;
	const thumbs = await Promise.all(
		frames.map(async (path, index) => ({
			input: await sharp(path).resize(thumbWidth, thumbHeight).png().toBuffer(),
			left: gap + (index % columns) * (thumbWidth + gap),
			top: gap + Math.floor(index / columns) * (thumbHeight + gap),
		})),
	);
	await sharp({
		create: {
			width: columns * (thumbWidth + gap) + gap,
			height: Math.ceil(frames.length / columns) * (thumbHeight + gap) + gap,
			channels: 3,
			background: hexly.page,
		},
	})
		.composite(thumbs)
		.webp({ quality: 90 })
		.toFile(join(destination, "contact-sheet.webp"));
	const width = composition.width * scale;
	const height = composition.height * scale;
	if (mode === "all" || mode === "deck") {
		const pptx = new pptxgen();
		pptx.defineLayout({
			name: "HEXLY",
			width: width / 72,
			height: height / 72,
		});
		pptx.layout = "HEXLY";
		pptx.author = "Hexly";
		pptx.subject = `${film.project.name} · ${film.template} · Video Kit ${kitVersion}`;
		pptx.title = film.project.name;
		const pdf = await PDFDocument.create();
		pdf.setTitle(pptx.title);
		pdf.setAuthor("Hexly");
		for (const [index, filename] of frames.entries()) {
			const scene = scenes[index];
			if (!scene) throw new Error("Frame and scene counts differ.");
			const slide = pptx.addSlide();
			slide.addImage({
				path: filename,
				x: 0,
				y: 0,
				w: width / 72,
				h: height / 72,
				altText: `${scene.title}. ${scene.body}`,
			});
			slide.addNotes(
				[
					scene.eyebrow,
					scene.title,
					scene.body,
					scene.link?.href ?? "",
					film.project.sourceNote,
					film.project.repository,
				].join("\n\n"),
			);
			const image = await pdf.embedPng(readFileSync(filename));
			pdf
				.addPage([width, height])
				.drawImage(image, { x: 0, y: 0, width, height });
		}
		await pptx.writeFile({
			fileName: join(destination, "deck.pptx"),
			compression: true,
		});
		writeFileSync(join(destination, "deck.pdf"), await pdf.save());
		if (
			(
				await PDFDocument.load(readFileSync(join(destination, "deck.pdf")))
			).getPageCount() !== scenes.length
		)
			throw new Error("PDF page count mismatch.");
	}
	if (mode === "all" || mode === "video") {
		let bucket = -1;
		const target = join(destination, "sample.mp4");
		await renderMedia({
			...common,
			inputProps: film,
			outputLocation: target,
			codec: "h264",
			crf: 18,
			pixelFormat: "yuv420p",
			colorSpace: "bt709",
			concurrency: 3,
			onProgress: ({ progress }) => {
				const next = Math.floor(progress * 10);
				if (next !== bucket) {
					bucket = next;
					process.stdout.write(`${film.template}: ${next * 10}%\n`);
				}
			},
		});
		const probe = JSON.parse(
			execFileSync(
				"ffprobe",
				[
					"-v",
					"error",
					"-select_streams",
					"v:0",
					"-show_entries",
					"stream=width,height,nb_frames,codec_name,r_frame_rate",
					"-of",
					"json",
					target,
				],
				{ encoding: "utf8" },
			),
		);
		const stream = probe.streams?.[0];
		if (
			stream?.width !== width ||
			stream?.height !== height ||
			Number(stream?.nb_frames) !== composition.durationInFrames ||
			stream?.codec_name !== "h264" ||
			stream?.r_frame_rate !== "30/1"
		)
			throw new Error("Rendered video does not match its composition.");
		// Decode the actual MP4, not just the Remotion still, for visual comparison.
		execFileSync("ffmpeg", [
			"-v",
			"error",
			"-i",
			target,
			"-ss",
			"3",
			"-frames:v",
			"1",
			join(destination, "decoded-frame.png"),
		]);
	}
	const artifacts = readdirSync(destination, { recursive: true })
		.filter(
			(file) =>
				typeof file === "string" && statSync(join(destination, file)).isFile(),
		)
		.map((file) => {
			const name = String(file);
			const bytes = readFileSync(join(destination, name));
			return {
				file: name,
				bytes: bytes.length,
				sha256: createHash("sha256").update(bytes).digest("hex"),
			};
		});
	const report = {
		kitVersion,
		template: film.template,
		project: film.project.id,
		mode,
		startedAt,
		completedAt: new Date().toISOString(),
		width,
		height,
		fps: film.fps,
		durationInFrames: composition.durationInFrames,
		pages: scenes.map((scene) => ({
			id: scene.id,
			kind: scene.kind,
			from: scene.from,
			durationInFrames: scene.durationInFrames,
		})),
		propsSha256: createHash("sha256")
			.update(JSON.stringify(film))
			.digest("hex"),
		artifacts,
	};
	writeFileSync(
		join(destination, "render.json"),
		`${JSON.stringify(report, null, 2)}\n`,
	);
	reports.push(report);
	process.stdout.write(
		`Verified ${film.template}: ${scenes.length} frames, ${mode}.\n`,
	);
}
writeFileSync(
	join(output, "renders.json"),
	`${JSON.stringify(reports, null, 2)}\n`,
);
process.stdout.write(`Output: ${output}\n`);
