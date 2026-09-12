import { Player, type PlayerRef, Thumbnail } from "@remotion/player";
import { useEffect, useMemo, useRef, useState } from "react";
import { Film } from "./Film";
import {
	dimensions,
	durationFor,
	type FilmConfig,
	parseFilm,
	timelineFor,
} from "./schema";
import "./site.css";

const labels = {
	en: {
		clip: "Rendered sample",
		live: "Interactive preview",
		format: "Frame format",
		landscape: "Landscape · 16:9",
		portrait: "Portrait · 9:16",
		reduced: "Reduce motion",
		system: "Following your system motion preference",
		play: "Play preview",
		pause: "Pause preview",
		seek: "Seek preview",
		scenes: "Explore the components",
		transcript: "Scene text",
		loading: "Loading the preview…",
		error: "The preview could not load. Reload the page to try again.",
		silent: "Silent sample · on-screen text below",
		fullscreen: "Full screen",
		intro: "Intro",
		title: "Title",
		chapter: "Chapter",
		content: "Content",
		cta: "Call to action",
		logo: "Logo reveal",
		outro: "Outro",
		video: "Video Preview",
		deck: "Deck / PPT Preview",
		previous: "Previous slide",
		next: "Next slide",
		slide: "Slide",
	},
	zh: {
		clip: "渲染短片",
		live: "交互预览",
		format: "画面比例",
		landscape: "横屏 · 16:9",
		portrait: "竖屏 · 9:16",
		reduced: "减弱动画",
		system: "遵循系统的减弱动画偏好",
		play: "播放预览",
		pause: "暂停预览",
		seek: "预览进度",
		scenes: "逐一探索组件",
		transcript: "场景文字",
		loading: "正在加载预览…",
		error: "预览暂时无法加载，请刷新页面重试。",
		silent: "无声示例 · 画面文字见下方",
		fullscreen: "全屏",
		intro: "前贴片",
		title: "标题",
		chapter: "章节",
		content: "内容",
		cta: "行动引导",
		logo: "标志揭幕",
		outro: "后贴片",
		video: "视频预览",
		deck: "Deck / PPT 预览",
		previous: "上一页",
		next: "下一页",
		slide: "页面",
	},
};

function useReducedMotion() {
	const [reduced, setReduced] = useState(
		() => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
	);
	useEffect(() => {
		const media = window.matchMedia("(prefers-reduced-motion: reduce)");
		const update = () => setReduced(media.matches);
		media.addEventListener("change", update);
		return () => media.removeEventListener("change", update);
	}, []);
	return reduced;
}

const timecode = (frame: number, fps: number) => {
	const seconds = Math.floor(frame / fps);
	return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
};

/** Lazy-load this export in a website. Rendering tools are never imported here. */
export function VideoPreview({
	config,
	locale = "en",
	clip,
	poster,
	view = "video",
	onView,
	onConfigChange,
}: {
	config: FilmConfig;
	locale?: "en" | "zh";
	clip?: string;
	poster?: string;
	view?: "video" | "deck";
	onView?: (view: "video" | "deck") => void;
	onConfigChange?: (config: FilmConfig) => void;
}) {
	const t = labels[locale];
	const systemReduced = useReducedMotion();
	const [reduce, setReduce] = useState(config.motion === "reduced");
	const [format, setFormat] = useState(config.format);
	const [mode, setMode] = useState<"clip" | "live">(
		clip && !systemReduced ? "clip" : "live",
	);
	const [frame, setFrame] = useState(45);
	const [playing, setPlaying] = useState(false);
	const player = useRef<PlayerRef>(null);
	const video = useRef<HTMLVideoElement>(null);
	const stage = useRef<HTMLDivElement>(null);
	const reduced = reduce || systemReduced;
	const film = useMemo(
		() =>
			parseFilm({ ...config, format, motion: reduced ? "reduced" : "full" }),
		[config, format, reduced],
	);
	const chapters = useMemo(() => timelineFor(film), [film]);
	const duration = durationFor(film);
	const size = dimensions(format);
	const active = chapters.findLast((chapter) => chapter.from <= frame)?.id;
	const slide = Math.max(
		0,
		chapters.findIndex((chapter) => chapter.id === active),
	);
	const deck = view === "deck";
	const live = mode === "live" || reduced || !clip;
	useEffect(() => {
		onConfigChange?.(film);
	}, [film, onConfigChange]);

	useEffect(() => {
		if (!live || deck) return;
		const p = player.current;
		if (!p) return;
		const update = ({ detail }: { detail: { frame: number } }) =>
			setFrame(detail.frame);
		const play = () => setPlaying(true);
		const pause = () => setPlaying(false);
		p.addEventListener("frameupdate", update);
		p.addEventListener("play", play);
		p.addEventListener("pause", pause);
		p.addEventListener("ended", pause);
		return () => {
			p.removeEventListener("frameupdate", update);
			p.removeEventListener("play", play);
			p.removeEventListener("pause", pause);
			p.removeEventListener("ended", pause);
		};
	}, [live, deck]);
	// biome-ignore lint/correctness/useExhaustiveDependencies: Reset playback when display settings change, including external history navigation.
	useEffect(() => {
		player.current?.pause();
		video.current?.pause();
		setPlaying(false);
	}, [reduced, format, deck]);

	const pause = () => {
		player.current?.pause();
		video.current?.pause();
		setPlaying(false);
	};
	const switchMode = (next: "clip" | "live") => {
		pause();
		setMode(next);
	};
	const seek = (next: number) => {
		pause();
		setFrame(next);
		if (!live) setMode("live");
		else player.current?.seekTo(next);
	};

	return (
		<div className="vk-preview" data-motion={reduced ? "reduced" : "full"}>
			{onView ? (
				<fieldset
					className="vk-view-tabs"
					aria-label={locale === "en" ? "Presentation view" : "演示视图"}
				>
					<button
						type="button"
						aria-pressed={!deck}
						onClick={() => {
							pause();
							onView("video");
						}}
					>
						{t.video}
					</button>
					<button
						type="button"
						aria-pressed={deck}
						onClick={() => {
							pause();
							onView("deck");
						}}
					>
						{t.deck}
					</button>
				</fieldset>
			) : null}
			<div className="vk-toolbar">
				{deck ? (
					<span className="vk-deck-label">
						{t.slide} {slide + 1} / {chapters.length}
					</span>
				) : (
					<fieldset
						className="vk-mode"
						aria-label={locale === "en" ? "Preview mode" : "预览模式"}
					>
						{clip && !reduced ? (
							<button
								type="button"
								aria-pressed={!live}
								onClick={() => switchMode("clip")}
							>
								{t.clip}
							</button>
						) : null}
						<button
							type="button"
							aria-pressed={live}
							onClick={() => switchMode("live")}
						>
							{t.live}
						</button>
					</fieldset>
				)}
				<label className="vk-format">
					<span className="vk-sr-only">{t.format}</span>
					<select
						value={live || deck ? format : "landscape"}
						onChange={(event) => {
							pause();
							setFormat(event.target.value as FilmConfig["format"]);
							setMode("live");
						}}
					>
						<option value="landscape">{t.landscape}</option>
						<option value="portrait">{t.portrait}</option>
					</select>
				</label>
			</div>
			<div
				className={`vk-stage ${(live || deck) && format === "portrait" ? "vk-portrait" : ""}`}
				ref={stage}
			>
				{deck ? (
					<Thumbnail
						component={Film}
						inputProps={{ ...film, motion: "reduced" }}
						frameToDisplay={(chapters[slide]?.from ?? 0) + 1}
						durationInFrames={duration}
						fps={film.fps}
						compositionWidth={size.width}
						compositionHeight={size.height}
						style={{
							width: "100%",
							aspectRatio: `${size.width} / ${size.height}`,
						}}
					/>
				) : live ? (
					<Player
						ref={player}
						component={Film}
						inputProps={film}
						durationInFrames={duration}
						fps={film.fps}
						compositionWidth={size.width}
						compositionHeight={size.height}
						initialFrame={frame}
						acknowledgeRemotionLicense
						numberOfSharedAudioTags={0}
						controls={false}
						autoPlay={false}
						loop={false}
						clickToPlay={false}
						doubleClickToFullscreen={false}
						spaceKeyToPlayOrPause={false}
						style={{
							width: "100%",
							aspectRatio: `${size.width} / ${size.height}`,
						}}
						errorFallback={() => (
							<p className="vk-error" role="alert">
								{t.error}
							</p>
						)}
						renderLoading={() => (
							<p className="vk-error" role="status">
								{t.loading}
							</p>
						)}
					/>
				) : (
					<video
						muted
						ref={video}
						src={clip}
						poster={poster}
						controls
						playsInline
						preload="none"
						aria-label={t.clip}
						onLoadedMetadata={(event) => {
							event.currentTarget.currentTime = frame / film.fps;
						}}
						onTimeUpdate={(event) =>
							setFrame(
								Math.min(
									duration - 1,
									Math.floor(event.currentTarget.currentTime * film.fps),
								),
							)
						}
					>
						{t.silent}
					</video>
				)}
				{deck ? (
					<div className="vk-deck-controls">
						<button
							type="button"
							disabled={slide === 0}
							onClick={() => seek((chapters[slide - 1]?.from ?? 0) + 1)}
						>
							{t.previous}
						</button>
						<span aria-live="polite">
							{slide + 1} / {chapters.length}
						</span>
						<button
							type="button"
							disabled={slide === chapters.length - 1}
							onClick={() => seek((chapters[slide + 1]?.from ?? 0) + 1)}
						>
							{t.next}
						</button>
					</div>
				) : live ? (
					<div className="vk-controls">
						<button
							type="button"
							onClick={() => {
								if (playing) pause();
								else {
									if (frame >= duration - 1) player.current?.seekTo(0);
									player.current?.play();
								}
							}}
							aria-label={playing ? t.pause : t.play}
						>
							<span aria-hidden="true">{playing ? "Ⅱ" : "▶"}</span>
						</button>
						<input
							type="range"
							min={0}
							max={duration - 1}
							value={frame}
							aria-label={t.seek}
							aria-valuetext={timecode(frame, film.fps)}
							onChange={(event) => seek(Number(event.target.value))}
						/>
						<output>
							{timecode(frame, film.fps)} / {timecode(duration, film.fps)}
						</output>
						<button
							type="button"
							aria-label={t.fullscreen}
							onClick={() => {
								void stage.current?.requestFullscreen().catch(() => undefined);
							}}
						>
							<span aria-hidden="true">⛶</span>
						</button>
					</div>
				) : null}
			</div>
			{!deck ? (
				<div className="vk-preferences">
					<label>
						<input
							type="checkbox"
							checked={reduced}
							disabled={systemReduced}
							onChange={(event) => setReduce(event.target.checked)}
						/>
						{t.reduced}
					</label>
					<span>{systemReduced ? t.system : t.silent}</span>
				</div>
			) : null}
			<section className="vk-chapters" aria-label={t.scenes}>
				<h2>{t.scenes}</h2>
				<div className="vk-chapter-grid">
					{chapters.map((chapter, index) => (
						<button
							key={chapter.id}
							type="button"
							aria-pressed={active === chapter.id}
							onClick={() => seek(chapter.from + 1)}
						>
							<span className="vk-chapter-index">
								{String(index + 1).padStart(2, "0")}
								<span>{timecode(chapter.from, film.fps)}</span>
							</span>
							<strong>{t[chapter.kind]}</strong>
							<span className="vk-chapter-duration">{chapter.duration}s</span>
						</button>
					))}
				</div>
			</section>
			<details className="vk-transcript">
				<summary>{t.transcript}</summary>
				<ol>
					{chapters.map((chapter) => (
						<li key={chapter.id}>
							<strong>{chapter.title}</strong>
							{chapter.body ? <p>{chapter.body}</p> : null}
							{chapter.link ? (
								<a href={chapter.link.href}>{chapter.link.label} ↗</a>
							) : null}
						</li>
					))}
				</ol>
			</details>
		</div>
	);
}
