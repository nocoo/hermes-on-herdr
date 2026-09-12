import { Player, type PlayerRef } from "@remotion/player";
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Film, HexlyMark } from "./Film";
import { type Language, story, timing } from "./timeline";
import "./web.css";

function timestamp(frame: number) {
  const seconds = Math.floor(frame / timing.fps);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function App() {
  const [language, setLanguage] = useState<Language>("zh");
  const [mode, setMode] = useState<"video" | "animation">("video");
  const [chapter, setChapter] = useState(0);
  const video = useRef<HTMLVideoElement>(null);
  const player = useRef<PlayerRef>(null);
  const position = useRef(0);
  const zh = language === "zh";
  const film = `/review/${story.artifact}-${language}.mp4`;
  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [language]);
  function seek(index: number) {
    const frame = timing.scenes[index].start;
    position.current = frame;
    setChapter(index);
    if (mode === "video" && video.current) video.current.currentTime = frame / timing.fps;
    if (mode === "animation") player.current?.seekTo(frame);
  }
  function switchLanguage(next: Language) {
    position.current =
      mode === "video"
        ? (video.current?.currentTime ?? 0) * timing.fps
        : (player.current?.getCurrentFrame() ?? 0);
    setLanguage(next);
  }
  function switchMode(next: "video" | "animation") {
    position.current =
      mode === "video"
        ? (video.current?.currentTime ?? 0) * timing.fps
        : (player.current?.getCurrentFrame() ?? 0);
    setMode(next);
  }
  return (
    <>
      <header className="site-header shell">
        <a className="site-brand" href={story.repository}>
          <img src="/brand/product.png" width="42" height="42" alt="" />
          <strong>hermes on herdr</strong>
        </a>
        <nav className="site-controls" aria-label={zh ? "旁白语言" : "Narration language"}>
          <button type="button" aria-pressed={zh} onClick={() => switchLanguage("zh")}>
            中文
          </button>
          <button type="button" aria-pressed={!zh} onClick={() => switchLanguage("en")}>
            English
          </button>
        </nav>
      </header>
      <main className="shell">
        <section className="site-intro">
          <div>
            <p className="site-eyebrow">
              <i /> THE WEEKEND PROTOCOL
            </p>
            <h1>
              {zh ? (
                <>
                  你的团队。
                  <br />
                  <em>你的周末。</em>
                </>
              ) : (
                <>
                  Your team.
                  <br />
                  <em>Your weekend.</em>
                </>
              )}
            </h1>
          </div>
          <div className="site-intro-copy">
            <p>
              {zh
                ? "你定方向，Hermes 管理 Herdr，Herdr 管理天才工程师伙伴。把周末，还给自己。"
                : "You set the direction. Hermes manages Herdr. Herdr manages your brilliant engineering partners. Keep the weekend for yourself."}
            </p>
            <span>
              {timestamp(timing.durationInFrames)} · {timing.width} × {timing.height} ·{" "}
              {zh ? "中文配音" : "ENGLISH NARRATION"}
            </span>
          </div>
        </section>
        <section className="screen-section" aria-label={zh ? "宣传视频" : "Product film"}>
          <div className="screen-toolbar">
            <span>
              <i /> {zh ? "周末交接" : "THE WEEKEND PROTOCOL"}
            </span>
            <div className="site-controls">
              <button
                type="button"
                aria-pressed={mode === "video"}
                onClick={() => switchMode("video")}
              >
                {zh ? "成片" : "Film"}
              </button>
              <button
                type="button"
                aria-pressed={mode === "animation"}
                onClick={() => switchMode("animation")}
              >
                {zh ? "实时动画" : "Live composition"}
              </button>
            </div>
          </div>
          <div className="screen">
            {mode === "video" ? (
              <video
                key={language}
                ref={video}
                controls
                playsInline
                preload="metadata"
                src={film}
                poster={`/review/poster-${language}.png`}
                onLoadedMetadata={() => {
                  if (video.current) video.current.currentTime = position.current / timing.fps;
                }}
                onTimeUpdate={() => {
                  const frame = (video.current?.currentTime ?? 0) * timing.fps;
                  setChapter(
                    Math.max(
                      0,
                      timing.scenes.findLastIndex((item) => item.start <= frame),
                    ),
                  );
                }}
              >
                <track
                  kind="captions"
                  src={`/audio/narration-${language}.vtt`}
                  srcLang={language}
                  label={zh ? "中文" : "English"}
                />
              </video>
            ) : (
              <Player
                key={language}
                ref={player}
                component={Film}
                inputProps={{ language, captions: true, audio: true }}
                durationInFrames={timing.durationInFrames}
                fps={timing.fps}
                compositionWidth={1920}
                compositionHeight={1080}
                controls
                acknowledgeRemotionLicense
                initialFrame={Math.min(Math.round(position.current), timing.durationInFrames - 1)}
                style={{ width: "100%", aspectRatio: "16/9" }}
              />
            )}
          </div>
        </section>
        <div className="downloads">
          <span>
            {zh
              ? "从信任，到交接。十个镜头，一段完整的周末。"
              : "From trust to handoff. Ten scenes. A weekend returned."}
          </span>
          <div>
            <a href={film} download>
              {zh ? "下载 MP4" : "Download MP4"}
              <b>↗</b>
            </a>
            <a href={`/audio/narration-${language}.srt`} download>
              {zh ? "字幕 SRT" : "Subtitles"}
              <b>↗</b>
            </a>
            <a href={`/slides/hermes-weekend-${language}.pdf`} download>
              PDF<b>↗</b>
            </a>
            <a href={`/slides/hermes-weekend-${language}.odp`} download>
              ODP<b>↗</b>
            </a>
          </div>
        </div>
        <section className="chapter-section" aria-label={zh ? "选择章节" : "Choose a chapter"}>
          <div className="section-label">
            <span>{zh ? "故事的十个镜头" : "THE STORY IN TEN SCENES"}</span>
            <span>00 — 09</span>
          </div>
          <div className="chapters">
            {story.scenes.map((scene, index) => (
              <button
                type="button"
                key={scene.id}
                className={chapter === index ? "chapter active" : "chapter"}
                aria-pressed={chapter === index}
                onClick={() => seek(index)}
              >
                <img
                  src={`/review/stills/${language}/${String(index).padStart(2, "0")}-${scene.id}.png`}
                  alt=""
                  loading="lazy"
                />
                <div>
                  <span>{String(index).padStart(2, "0")}</span>
                  <strong>{scene.copy[language].title.replaceAll("\n", " ")}</strong>
                  <em>{timestamp(timing.scenes[index].start)}</em>
                </div>
              </button>
            ))}
          </div>
        </section>
        <section className="site-notes">
          <div>
            <p className="site-eyebrow">HERDR × HERMES</p>
            <h2>
              {zh
                ? "把天才交给系统管理，\n把周末还给自己。"
                : "Let the system manage the genius.\nKeep the weekend for yourself."}
            </h2>
            <a href={story.repository}>{zh ? "打开项目" : "Explore the project"} ↗</a>
          </div>
          <p>
            {zh
              ? "专用、受信任的 Hermes Profile。真实 Herdr pane。按需打开的 monitor TUI。配置好消息平台，让本机和 Herdr 保持在线，再离开桌面。"
              : "A dedicated, trusted Hermes profile. A real Herdr pane. The monitor TUI when you need it. Configure your messaging platform, keep this machine and Herdr online, and step away."}
          </p>
        </section>
      </main>
      <footer className="site-footer shell">
        <a href="https://hexly.ai" className="site-hexly">
          <HexlyMark size={33} color="#e79670" paper="#0b161c" />
          <strong>
            hexly<span>.</span>ai
          </strong>
        </a>
        <span>
          {zh
            ? "原创视觉与配乐 · Kokoro 合成旁白"
            : "Original visuals & score · Kokoro synthetic narration"}
        </span>
        <a href="/credits.md">{zh ? "素材与许可" : "Sources & licenses"} ↗</a>
      </footer>
    </>
  );
}

const root = document.getElementById("root");
if (!root) throw new Error("Missing website root");
createRoot(root).render(<App />);
