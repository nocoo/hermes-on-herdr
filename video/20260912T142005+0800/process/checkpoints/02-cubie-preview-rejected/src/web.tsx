import { BrandLockup, RedDot } from "@hexly/video-kit";
import { type CallbackListener, Player, type PlayerRef } from "@remotion/player";
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Film, filmMetadata } from "./Film";
import { story, timing } from "./timeline";
import "./web.css";

const asset = (file: string) => `${import.meta.env.BASE_URL}${file}`;
const preview = new URLSearchParams(window.location.search).has("preview");
const stamp = (frame: number) =>
  `${Math.floor(frame / 1800)}:${String(Math.floor(frame / 30) % 60).padStart(2, "0")}`;
const still = (index: number) =>
  asset(`review/stills/${String(index).padStart(2, "0")}-${story.scenes[index]?.id}.png`);

function App() {
  const [mode, setMode] = useState<"film" | "animation" | "deck">(preview ? "animation" : "film");
  const [chapter, setChapter] = useState(0);
  const player = useRef<PlayerRef>(null);
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const active = player.current;
    if (mode !== "animation" || !active) return;
    const update: CallbackListener<"frameupdate"> = ({ detail }) => {
      const index = timing.scenes.findIndex(
        (s) => detail.frame >= s.start && detail.frame < s.start + s.duration,
      );
      if (index >= 0) setChapter(index);
    };
    active.addEventListener("frameupdate", update);
    return () => active.removeEventListener("frameupdate", update);
  }, [mode]);
  const current = story.scenes[chapter] ?? story.scenes[0];
  if (!current) throw new Error("The film has no scenes");
  const selectChapter = (index: number) => {
    setChapter(index);
    const frame = timing.scenes[index]?.start ?? 0;
    if (mode === "film" && video.current) video.current.currentTime = frame / 30;
    if (mode === "animation") {
      player.current?.seekTo(frame);
      player.current?.play();
    }
  };
  const selectMode = (next: typeof mode) => {
    video.current?.pause();
    player.current?.pause();
    setMode(next);
  };
  return (
    <>
      <header className="site-header">
        <a href="https://hexly.ai" aria-label="Hexly AI">
          <BrandLockup />
        </a>
        <a href={story.repository} className="repo-link">
          hermes on herdr <span aria-hidden="true">↗</span>
        </a>
      </header>
      <main>
        <section className="intro-copy">
          <p className="eyebrow">
            <RedDot size={9} /> {preview ? "LIVE PREVIEW · HEXLY AI" : "A FILM FROM HEXLY AI"}
          </p>
          <div className="headline-row">
            <h1>
              Your weekend,
              <br />
              returned.
            </h1>
            <p>
              Connect a trusted Hermes to your Herdr session.
              <br className="desktop-break" />
              Manage your agent team through the channels you already use.
            </p>
          </div>
        </section>
        <div className="toolbar">
          <fieldset className="modes" aria-label="Viewing mode">
            {(preview ? (["animation"] as const) : (["film", "animation", "deck"] as const)).map(
              (value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={mode === value}
                  onClick={() => selectMode(value)}
                >
                  {
                    {
                      film: "Watch the film",
                      animation: "Explore the animation",
                      deck: "Browse the deck",
                    }[value]
                  }
                </button>
              ),
            )}
          </fieldset>
          <span className="film-meta">ENGLISH · 1:36 · {preview ? "DRAFT" : "1080P"}</span>
        </div>
        <section className="stage" aria-label="Context is control, English film">
          {mode === "film" ? (
            <video
              key="film"
              ref={video}
              controls
              preload="metadata"
              playsInline
              src={asset(`review/${story.filename}`)}
              poster={asset("review/poster.png")}
              onTimeUpdate={() => {
                const frame = Math.floor((video.current?.currentTime ?? 0) * 30);
                const index = timing.scenes.findIndex(
                  (s) => frame >= s.start && frame < s.start + s.duration,
                );
                if (index >= 0) setChapter(index);
              }}
            >
              <track
                kind="captions"
                srcLang="en"
                label="English transcript"
                src={asset("audio/narration-en.vtt")}
              />
              Your browser does not support video. Download the MP4 below.
            </video>
          ) : mode === "animation" ? (
            <Player
              ref={player}
              component={Film}
              {...filmMetadata}
              inputProps={{ captions: true, audio: true }}
              compositionWidth={filmMetadata.width}
              compositionHeight={filmMetadata.height}
              initialFrame={timing.scenes[chapter]?.start ?? 0}
              showPosterWhenUnplayed
              renderPoster={() => (
                <img
                  src={still(0)}
                  alt="Context is control · hermes on herdr"
                  style={{ width: "100%", height: "100%", objectFit: "contain" }}
                />
              )}
              controls
              autoPlay={false}
              style={{ width: "100%", aspectRatio: "16 / 9" }}
            />
          ) : (
            <img
              className="deck-frame"
              src={still(chapter)}
              alt={current.title.replaceAll("\n", " ")}
            />
          )}
        </section>
        <div className="below-player">
          <p>
            Context is control <span>·</span> hermes on herdr
          </p>
          {preview ? (
            <span className="preview-note">
              Live animation · draft audio · export pending review
            </span>
          ) : (
            <a href={asset(`review/${story.filename}`)} download>
              Download MP4 <span aria-hidden="true">↓</span>
            </a>
          )}
        </div>
        <nav className="chapters" aria-label="Film chapters">
          {story.scenes.map((scene, index) => (
            <button
              type="button"
              key={scene.id}
              aria-current={chapter === index ? "step" : undefined}
              onClick={() => selectChapter(index)}
            >
              <span className="chapter-time">{stamp(timing.scenes[index]?.start ?? 0)}</span>
              <span>{scene.title.split("\n")[0]?.replace(/\.$/, "")}</span>
            </button>
          ))}
        </nav>
        {mode === "deck" ? (
          <section className="speaker-notes" aria-live="polite">
            <p className="eyebrow">
              {String(chapter + 1).padStart(2, "0")} / {story.scenes.length} · SPEAKER NOTES
            </p>
            <p>{current.narration.join(" ")}</p>
            {"qualifications" in current ? (
              <p className="qualification">{current.qualifications?.join(" ")}</p>
            ) : null}
          </section>
        ) : null}
        <section className="take-away">
          <div>
            <p className="eyebrow">THE PIECES, IN PLACE</p>
            <h2>
              A familiar channel.
              <br />A trusted connection.
            </h2>
          </div>
          <div>
            <p>
              A Hermes instance outside Herdr does not automatically inherit the session's pane,
              socket or caller context. The plugin makes that connection explicit for the profile
              you choose.
            </p>
            <a className="text-link" href={`${story.repository}#为什么需要这个插件`}>
              Explore the plugin <span aria-hidden="true">↗</span>
            </a>
          </div>
        </section>
        {!preview ? (
          <section className="downloads" aria-label="Film downloads">
            <a href={asset("slides/hermes-context-en.pdf")} download>
              <span>Presentation</span>PDF <span aria-hidden="true">↓</span>
            </a>
            <a href={asset("slides/hermes-context-en.pptx")} download>
              <span>With speaker notes</span>PPTX <span aria-hidden="true">↓</span>
            </a>
            <a href={asset("slides/hermes-context-en.odp")} download>
              <span>OpenDocument</span>ODP <span aria-hidden="true">↓</span>
            </a>
            <a href={asset("audio/narration-en.srt")} download>
              <span>English captions</span>SRT <span aria-hidden="true">↓</span>
            </a>
          </section>
        ) : null}
        <p className="release-note">
          Early 0.x release. Discord connectivity is recorded; Telegram/Slack integration and a
          fresh complete message-to-pane round trip remain unverified. Channel credentials and
          access policies need configuration. The host, Herdr and gateway must stay online. A
          trusted profile retains same-user terminal permissions; session binding is not an OS
          sandbox.
        </p>
      </main>
      <footer>
        <BrandLockup />
        <span>Let the system manage the talent.</span>
        {preview ? (
          <span>Animation review · rendering awaits approval</span>
        ) : (
          <>
            <a href={asset("credits.md")}>Credits &amp; licenses</a>
            <a href={`${story.repository}/tree/main/video/20260912T142005+0800`}>
              Source &amp; rebuild
            </a>
          </>
        )}
      </footer>
    </>
  );
}

const root = document.getElementById("root");
if (!root) throw new Error("Missing app root");
createRoot(root).render(<App />);
