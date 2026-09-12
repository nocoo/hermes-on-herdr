import type { CSSProperties, ReactNode } from "react";
import {
	AbsoluteFill,
	Img,
	staticFile,
	useCurrentFrame,
	useVideoConfig,
} from "remotion";
import { family, hexly, themes } from "./brand";
import { useHexlyFonts } from "./fonts";
import { BrandLockup, BrandMark, HexlyReveal, RedDot } from "./Identity";
import { ease, entrance } from "./motion";
import type {
	Motion,
	SceneConfig,
	SceneKind,
	TemplateId,
	VideoProject,
} from "./schema";

export type SceneProps = Pick<SceneConfig, "title"> &
	Partial<Pick<SceneConfig, "eyebrow" | "body" | "link">> & {
		template?: TemplateId;
		motion?: Motion;
		index?: number;
		project?: VideoProject;
		children?: ReactNode;
	};

export const projectAsset = (path: string) =>
	/^(https:|data:)/.test(path) ? path : staticFile(path.replace(/^\//, ""));

function ProjectArt({
	project,
	screenshot = false,
}: {
	project?: VideoProject;
	screenshot?: boolean;
}) {
	const image = screenshot ? project?.screenshot : undefined;
	return (
		<div
			style={{
				display: "flex",
				alignItems: "center",
				justifyContent: "center",
				width: "100%",
				height: "100%",
				padding: image ? 14 : 54,
			}}
		>
			{image ? (
				<Img
					src={projectAsset(image.src)}
					alt={image.alt}
					style={{ width: "100%", height: "100%", objectFit: "contain" }}
				/>
			) : project?.logo ? (
				<Img
					src={projectAsset(project.logo)}
					alt={project.name}
					style={{ width: "100%", height: "100%", objectFit: "contain" }}
				/>
			) : (
				<BrandMark scale={5.8} />
			)}
		</div>
	);
}

function Cube({
	side,
	color,
	style,
}: {
	side: number;
	color: string;
	style?: CSSProperties;
}) {
	const half = side / 2;
	return (
		<div
			style={{
				position: "absolute",
				width: side,
				height: side,
				transformStyle: "preserve-3d",
				...style,
			}}
		>
			{[
				{ id: "front", transform: `translateZ(${half}px)`, tint: color },
				{
					id: "right",
					transform: `rotateY(90deg) translateZ(${half}px)`,
					tint: `color-mix(in srgb, ${color} 85%, ${hexly.ink})`,
				},
				{
					id: "top",
					transform: `rotateX(90deg) translateZ(${half}px)`,
					tint: `color-mix(in srgb, ${color} 65%, ${hexly.surface})`,
				},
				{
					id: "left",
					transform: `rotateY(-90deg) translateZ(${half}px)`,
					tint: color,
				},
				{
					id: "back",
					transform: `rotateY(180deg) translateZ(${half}px)`,
					tint: color,
				},
				{
					id: "bottom",
					transform: `rotateX(-90deg) translateZ(${half}px)`,
					tint: color,
				},
			].map((face) => (
				<div
					key={face.id}
					style={{
						position: "absolute",
						inset: 0,
						borderRadius: family.radius.object,
						transform: face.transform,
						background: `linear-gradient(145deg, color-mix(in srgb, ${face.tint} 88%, ${hexly.surface}), ${face.tint})`,
						border: `1px solid color-mix(in srgb, ${face.tint} 76%, ${hexly.ink})`,
						backfaceVisibility: "hidden",
						boxShadow: `inset 0 2px 5px ${hexly.surface}35`,
					}}
				/>
			))}
		</div>
	);
}

function StudioArt({
	progress,
	project,
}: {
	progress: number;
	project?: VideoProject;
}) {
	return (
		<div
			style={{
				position: "relative",
				width: 540,
				height: 500,
				perspective: 1400,
			}}
		>
			<div
				style={{
					position: "absolute",
					left: 20,
					right: 0,
					bottom: 4,
					height: 100,
					borderRadius: "50%",
					background: `radial-gradient(ellipse, ${hexly.shadow}1b, transparent 68%)`,
				}}
			/>
			<div
				style={{
					position: "absolute",
					inset: 0,
					transformStyle: "preserve-3d",
					transform: `translateY(${(1 - progress) * 18}px) rotateX(-22deg) rotateY(${-28 + 6 * progress}deg)`,
				}}
			>
				<Cube
					side={172}
					color={hexly.accent}
					style={{
						left: 55,
						top: 220,
						transform: `translateZ(${10 + progress * 6}px)`,
					}}
				/>
				<Cube
					side={136}
					color={hexly.soft}
					style={{ left: 264, top: 256, transform: "translateZ(-38px)" }}
				/>
				<Cube
					side={128}
					color={hexly.surface}
					style={{
						left: 214,
						top: 28,
						transform: `translateY(${(1 - progress) * 18}px) translateZ(-30px)`,
					}}
				/>
			</div>
			<div
				style={{
					position: "absolute",
					right: 24,
					top: 76,
					width: 164,
					height: 164,
					background: hexly.surface,
					border: `1px solid ${hexly.line}`,
					borderRadius: family.radius.panel,
					boxShadow: `0 20px 42px ${hexly.shadow}14`,
					opacity: progress,
				}}
			>
				<ProjectArt project={project} />
			</div>
		</div>
	);
}

function Facts({
	project,
	compact = false,
}: {
	project?: VideoProject;
	compact?: boolean;
}) {
	const facts = project?.facts ?? [
		{ label: "FORMAT", value: "16:9" },
		{ label: "FAMILY", value: "Hexly" },
		{ label: "MOTION", value: "Measured" },
	];
	return (
		<div
			style={{
				display: "grid",
				gap: compact ? 18 : 22,
				gridTemplateColumns: compact
					? "1fr"
					: `repeat(${Math.min(facts.length, 3)}, 1fr)`,
			}}
		>
			{facts.slice(0, 3).map((fact) => (
				<div
					key={fact.label}
					style={{ borderTop: `1px solid ${hexly.line}`, paddingTop: 25 }}
				>
					<div
						style={{
							fontFamily: hexly.mono,
							fontSize: 17,
							color: hexly.muted,
							letterSpacing: 1,
						}}
					>
						{fact.label.toUpperCase()}
					</div>
					<div
						style={{
							fontSize: compact ? 42 : 58,
							lineHeight: 1.15,
							fontWeight: 500,
							letterSpacing: -2,
							marginTop: 15,
							overflowWrap: "anywhere",
						}}
					>
						{fact.value}
					</div>
				</div>
			))}
		</div>
	);
}

function Slate({
	kind,
	title,
	eyebrow = "",
	body = "",
	link,
	template = "launch",
	motion = "full",
	index = 0,
	project,
	children,
}: SceneProps & { kind: SceneKind }) {
	const frame = useCurrentFrame();
	const { fps, width, height, durationInFrames } = useVideoConfig();
	const ready = useHexlyFonts();
	const theme = themes[template];
	const p = theme.palette;
	const portrait = height > width;
	const reduced = motion === "reduced";
	const essential = template === "essential";
	const editorial = template === "editorial";
	const pulse = template === "pulse";
	const studio = template === "studio";
	const content = kind === "content";
	const pad = portrait ? 84 : family.space.safe;
	const mono: CSSProperties = {
		fontFamily: hexly.mono,
		fontSize: portrait ? 25 : 20,
		letterSpacing: 1.6,
		lineHeight: 1.5,
	};
	const enter = (delay = 0) =>
		entrance(frame, fps, theme.enter, delay, reduced);
	const exit = reduced
		? 1
		: 1 -
			ease(
				(frame - durationInFrames + fps * family.motion.transition) /
					(fps * family.motion.transition),
			);
	const move = (delay = 0): CSSProperties => ({
		opacity: enter(delay) * exit,
		transform: `translateY(${(1 - enter(delay)) * family.motion.travel}px)`,
	});
	const art = kind === "intro" || kind === "chapter" || content;
	const split = art && (!essential || (content && !!project?.screenshot));
	const centered = essential && !split;
	const contentWidth = portrait
		? width - pad * 2
		: centered
			? 1390
			: split
				? editorial
					? 1020
					: 1040
				: 1510;
	const titleSize =
		(portrait ? 104 : essential ? 146 : editorial ? 118 : pulse ? 116 : 134) *
		(title.length > 55 ? 0.65 : title.length > 30 ? 0.8 : 1);
	const contentTop = portrait
		? essential
			? 580
			: 338
		: essential
			? 336
			: editorial
				? 286
				: pulse
					? 312
					: 326;
	const artLeft = portrait ? 178 : 1328;
	const artTop = portrait ? 1120 : editorial ? 316 : 334;
	const artWidth = portrait ? 724 : 466;
	const textColor = p.muted;
	return (
		<AbsoluteFill
			data-video-scene={kind}
			data-template={template}
			style={{
				background: p.page,
				color: p.ink,
				fontFamily: hexly.sans,
				overflow: "hidden",
				opacity: ready ? 1 : 0,
			}}
		>
			{editorial ? (
				<div
					style={{
						position: "absolute",
						left: pad,
						right: pad,
						top: 230,
						borderTop: `1px solid ${p.ink}`,
						display: "flex",
						justifyContent: "space-between",
						paddingTop: 16,
						...mono,
						fontSize: 17,
						color: p.muted,
					}}
				>
					<span>FIELD NOTES / {String(index + 1).padStart(2, "0")}</span>
					<span>HEXLY COLLECTION</span>
				</div>
			) : pulse ? (
				<div
					style={{
						position: "absolute",
						inset: portrait ? "262px 56px 224px" : "250px 82px 174px",
						border: `1px solid ${p.line}`,
						borderRadius: family.radius.panel,
						background: p.surface,
					}}
				/>
			) : null}
			<div
				style={{
					position: "absolute",
					left: pad,
					right: pad,
					top: portrait ? 102 : 92,
					display: "flex",
					justifyContent: "space-between",
					alignItems: "center",
				}}
			>
				<BrandLockup scale={portrait ? 2.1 : 1.7} />
				<span style={{ ...mono, color: p.muted, fontSize: portrait ? 21 : 17 }}>
					{theme.label.toUpperCase()} / {String(index + 1).padStart(2, "0")}
				</span>
			</div>
			<div
				style={{
					position: "absolute",
					left: centered ? (width - contentWidth) / 2 : pad + (pulse ? 32 : 0),
					top: contentTop,
					width: contentWidth - (pulse ? 56 : 0),
					textAlign: centered ? "center" : "left",
				}}
			>
				<div
					style={{
						...mono,
						display: "flex",
						justifyContent: centered ? "center" : "start",
						alignItems: "center",
						gap: 16,
						color: p.muted,
						marginBottom: 30,
						...move(0.04),
					}}
				>
					<RedDot size={12} />
					{eyebrow || kind.toUpperCase()}
				</div>
				<div
					data-video-title
					style={{
						margin: 0,
						fontSize: titleSize,
						letterSpacing: "-0.052em",
						fontWeight: 500,
						lineHeight: 1.05,
						whiteSpace: "pre-line",
						overflowWrap: "anywhere",
						...move(theme.stagger),
					}}
				>
					{title}
				</div>
				{body ? (
					<div
						data-video-body
						style={{
							marginTop: editorial ? 30 : 36,
							maxWidth: essential ? undefined : portrait ? 850 : 945,
							color: textColor,
							fontSize:
								body.length > 260 ? 26 : portrait ? 34 : editorial ? 29 : 31,
							lineHeight: 1.55,
							whiteSpace: "pre-line",
							...move(theme.stagger * 2),
						}}
					>
						{body}
					</div>
				) : null}
				{content && project?.technologies.length ? (
					<div
						style={{
							display: "flex",
							flexWrap: "wrap",
							justifyContent: essential ? "center" : "start",
							gap: 12,
							marginTop: 32,
							...move(theme.stagger * 3),
						}}
					>
						{project.technologies.map((name) => (
							<span
								key={name}
								style={{
									fontFamily: hexly.mono,
									fontSize: portrait ? 23 : 20,
									lineHeight: 1.4,
									padding: "10px 15px",
									border: `1px solid ${p.line}`,
									borderRadius: family.radius.small,
								}}
							>
								{name}
							</span>
						))}
					</div>
				) : null}
				{kind === "cta" && link ? (
					<div
						style={{
							marginTop: portrait ? 68 : 56,
							...move(theme.stagger * 3),
						}}
					>
						<div
							style={{
								display: "inline-flex",
								alignItems: "center",
								gap: 40,
								background: p.ink,
								color: p.page,
								fontSize: portrait ? 31 : 28,
								borderRadius: family.radius.small,
								padding: "24px 34px",
							}}
						>
							{link.label}
							<span aria-hidden="true">↗</span>
						</div>
						<div
							style={{
								...mono,
								color: textColor,
								fontSize: portrait ? 24 : 21,
								marginTop: 28,
								overflowWrap: "anywhere",
							}}
						>
							{link.href.replace(/^https:\/\//, "").replace(/\/$/, "")}
						</div>
					</div>
				) : null}
			</div>
			{split ? (
				<div
					style={{
						position: "absolute",
						left: artLeft,
						top: artTop,
						width: artWidth,
						...(!studio ? move(theme.stagger * 2) : {}),
					}}
				>
					{children ??
						(pulse && !(content && project?.screenshot) ? (
							<div style={{ padding: "6px 22px" }}>
								<Facts project={project} compact />
								<p
									style={{
										...mono,
										fontSize: 15,
										color: p.muted,
										lineHeight: 1.6,
										marginTop: 35,
									}}
								>
									{project?.sourceNote}
								</p>
							</div>
						) : studio && !project?.screenshot ? (
							<StudioArt
								progress={enter(theme.stagger * 2)}
								project={project}
							/>
						) : kind === "chapter" && !studio ? (
							<div
								style={{
									fontSize: portrait ? 300 : 320,
									lineHeight: 1,
									letterSpacing: -24,
									fontWeight: 400,
									color: p.accent,
								}}
							>
								01<span style={{ color: p.line }}>.</span>
							</div>
						) : (
							<div
								style={{
									position: "relative",
									width: "100%",
									height: editorial ? 430 : 470,
								}}
							>
								{!editorial ? (
									<div
										style={{
											position: "absolute",
											inset: "20px -18px -18px 20px",
											background: p.soft,
											border: `1px solid ${p.line}`,
											borderRadius: family.radius.panel,
										}}
									/>
								) : null}
								<div
									style={{
										position: "absolute",
										inset: 0,
										background: p.surface,
										border: `1px solid ${p.line}`,
										borderRadius: editorial
											? family.radius.small
											: family.radius.panel,
										overflow: "hidden",
									}}
								>
									<ProjectArt
										project={project}
										screenshot={content || kind === "intro"}
									/>
								</div>
								{editorial ? (
									<div
										style={{
											position: "absolute",
											top: "100%",
											paddingTop: 20,
											fontFamily: hexly.mono,
											fontSize: 16,
											lineHeight: 1.6,
											color: p.muted,
										}}
									>
										FIG. 01 /{" "}
										{project?.screenshot
											? project.screenshot.alt
											: (project?.name ?? "HEXLY IDENTITY")}
									</div>
								) : null}
							</div>
						))}
				</div>
			) : (
				children
			)}
			{!essential ? (
				<div
					style={{
						position: "absolute",
						left: pad,
						right: pad,
						bottom: portrait ? 166 : 146,
						height: 1,
						background: p.line,
					}}
				/>
			) : null}
			<div
				style={{
					position: "absolute",
					left: pad,
					right: pad,
					bottom: portrait ? 100 : 86,
					display: "flex",
					justifyContent: "space-between",
					gap: 32,
					color: textColor,
					...mono,
					fontSize: portrait ? 20 : 17,
				}}
			>
				<span>SMALL IDEAS. A LITTLE UNIVERSE.</span>
				<span>HEXLY.AI</span>
			</div>
		</AbsoluteFill>
	);
}

export const Intro = (props: SceneProps) => <Slate {...props} kind="intro" />;
export const Title = (props: SceneProps) => <Slate {...props} kind="title" />;
export const Chapter = (props: SceneProps) => (
	<Slate {...props} kind="chapter" />
);
export const Content = (props: SceneProps) => (
	<Slate {...props} kind="content" />
);
export const CTA = (props: SceneProps) => <Slate {...props} kind="cta" />;
export const LogoReveal = ({ title, template, motion }: SceneProps) => (
	<HexlyReveal template={template} motion={motion} caption={title} />
);
export const Outro = ({ title, body, template, motion }: SceneProps) => (
	<HexlyReveal
		template={template}
		motion={motion}
		caption={[...new Set([title, body].filter(Boolean))].join(" · ")}
	/>
);
export const sceneComponents = {
	intro: Intro,
	title: Title,
	chapter: Chapter,
	content: Content,
	cta: CTA,
	logo: LogoReveal,
	outro: Outro,
};
