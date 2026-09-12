import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";
import {
	AbsoluteFill,
	useCurrentFrame,
	useDelayRender,
	useVideoConfig,
} from "remotion";
import { family, hexly, type Palette, palettes, themes } from "./brand";
import { useHexlyFonts } from "./fonts";
import { revealState } from "./motion";
import type { Motion, TemplateId } from "./schema";

export function BrandMark({
	scale = 1,
	palette = palettes.light,
}: {
	scale?: number;
	palette?: Palette;
}) {
	return (
		<svg
			width={hexly.mark.width * scale}
			height={hexly.mark.height * scale}
			viewBox={hexly.mark.viewBox}
			fill="none"
			aria-hidden="true"
			style={{ maxWidth: "100%", maxHeight: "100%" }}
		>
			<path d={hexly.mark.outer} fill={palette.accent} />
			<path
				d={hexly.mark.inner}
				stroke={palette.page}
				strokeWidth={hexly.mark.strokeWidth}
			/>
			<path
				d={hexly.mark.facets}
				stroke={palette.page}
				strokeWidth={hexly.mark.strokeWidth}
			/>
		</svg>
	);
}

export function wordmarkStyle(scale: number, palette: Palette): CSSProperties {
	return {
		fontFamily: hexly.sans,
		fontSize: hexly.wordmark.size * scale,
		fontWeight: hexly.wordmark.weight,
		letterSpacing: hexly.wordmark.letterSpacing * scale,
		lineHeight: 1,
		whiteSpace: "nowrap",
		color: palette.ink,
	};
}

export function Wordmark({ palette = palettes.light }: { palette?: Palette }) {
	return (
		<>
			hexly<span style={{ color: palette.accent }}>.</span>
			<span style={{ color: palette.muted, fontWeight: 400 }}>ai</span>
		</>
	);
}

export function BrandLockup({
	scale = 1,
	palette = palettes.light,
}: {
	scale?: number;
	palette?: Palette;
}) {
	return (
		<span
			role="img"
			aria-label="hexly.ai"
			style={{
				display: "inline-flex",
				alignItems: "center",
				gap: hexly.wordmark.gap * scale,
				...wordmarkStyle(scale, palette),
			}}
		>
			<BrandMark scale={scale} palette={palette} />
			<span>
				<Wordmark palette={palette} />
			</span>
		</span>
	);
}

export function RedDot({
	size = 10,
	style,
}: {
	size?: number;
	style?: CSSProperties;
}) {
	return (
		<span
			aria-hidden="true"
			data-red-dot
			style={{
				display: "inline-block",
				flexShrink: 0,
				width: size,
				height: size,
				borderRadius: "50%",
				background: family.dot.color,
				boxShadow: `inset 0 0 1px ${family.dot.highlight}`,
				...style,
			}}
		/>
	);
}

export function HexlyReveal({
	caption,
	template = "launch",
	motion = "full",
	scale: requestedScale,
}: {
	caption?: string;
	template?: TemplateId;
	motion?: Motion;
	scale?: number;
}) {
	const frame = useCurrentFrame();
	const { fps, width, height } = useVideoConfig();
	const palette = themes[template].palette;
	const scale = requestedScale ?? (width < height ? 4.2 : 5.2);
	const ready = useHexlyFonts();
	const ref = useRef<HTMLSpanElement>(null);
	const { delayRender, continueRender } = useDelayRender();
	const [textUnitWidth, setTextUnitWidth] = useState(0);
	const textWidth = textUnitWidth * scale;
	useLayoutEffect(() => {
		if (!ready || !ref.current) return;
		const handle = delayRender("Measure the official Hexly wordmark");
		// offsetWidth stays in composition pixels when a Player is scaled for mobile.
		setTextUnitWidth(ref.current.offsetWidth / scale);
		continueRender(handle);
	}, [ready, scale, delayRender, continueRender]);
	const state = revealState(frame, fps, motion === "reduced");
	const markWidth = hexly.mark.width * scale;
	const gap = hexly.wordmark.gap * scale;
	const left =
		width / 2 - markWidth / 2 - ((textWidth + gap) / 2) * state.expand;
	return (
		<AbsoluteFill
			data-scene="logo"
			style={{
				background: palette.page,
				fontFamily: hexly.sans,
				opacity: ready && textWidth ? 1 : 0,
			}}
		>
			<div
				data-hexly-mark
				style={{
					position: "absolute",
					left,
					top: height / 2 - (hexly.mark.height * scale) / 2,
					opacity: state.mark,
					transform: `translateY(${(1 - state.mark) * 14}px)`,
				}}
			>
				<BrandMark scale={scale} palette={palette} />
			</div>
			<div
				data-hexly-wordmark
				style={{
					position: "absolute",
					left: left + markWidth + gap,
					top: height / 2 - (hexly.wordmark.size * scale) / 2,
					overflow: "hidden",
					width: state.expand * (textWidth + 2),
					opacity: state.expand,
				}}
			>
				<span
					ref={ref}
					style={{ display: "inline-block", ...wordmarkStyle(scale, palette) }}
				>
					<Wordmark palette={palette} />
				</span>
			</div>
			{caption ? (
				<div
					data-hexly-caption
					style={{
						position: "absolute",
						top: height / 2 + (hexly.mark.height * scale) / 2 + 62,
						left: width * 0.1,
						width: width * 0.8,
						textAlign: "center",
						fontSize: width < height ? 30 : 28,
						lineHeight: 1.5,
						color: palette.muted,
						opacity: state.caption,
					}}
				>
					{caption}
				</div>
			) : null}
		</AbsoluteFill>
	);
}
