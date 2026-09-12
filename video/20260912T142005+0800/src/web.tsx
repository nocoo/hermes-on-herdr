import { BrandLockup, RedDot } from "@hexly/video-kit";
import { type CallbackListener, Player, type PlayerRef } from "@remotion/player";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Film, filmMetadata } from "./Film";
import { story, timing } from "./timeline";
import "./web.css";

const params = new URLSearchParams(window.location.search);
const requestedFrame = params.has("frame") ? Number(params.get("frame")) : null;
const initialFrame =
  requestedFrame !== null &&
  Number.isInteger(requestedFrame) &&
  requestedFrame >= 0 &&
  requestedFrame < timing.durationInFrames
    ? requestedFrame
    : 60;
const names = [
  "Intro",
  "The gap",
  "Agents",
  "The plugin",
  "Managers",
  "Channels",
  "Local control",
  "Monitor",
  "Trust",
  "Weekend",
  "Hexly AI",
];
const stamp = (frame: number) =>
  `${Math.floor(frame / 1800)}:${String(Math.floor(frame / 30) % 60).padStart(2, "0")}`;

function App() {
  const player = useRef<PlayerRef>(null);
  const hasPlayed = useRef(requestedFrame !== null);
  const [frame, setFrame] = useState(initialFrame);
  const [playing, setPlaying] = useState(false);
  const [captions, setCaptions] = useState(params.get("captions") !== "0");
  const inputProps = useMemo(() => ({ captions, audio: true }), [captions]);
  const chapter = Math.max(
    0,
    timing.scenes.findIndex((s) => frame >= s.start && frame < s.start + s.duration),
  );
  const scene = story.scenes[chapter] ?? story.scenes[0];
  const toggle = useCallback(() => {
    const active = player.current;
    if (!active) return;
    if (active.isPlaying()) active.pause();
    else {
      if (!hasPlayed.current) active.seekTo(0);
      hasPlayed.current = true;
      active.play();
    }
  }, []);
  useEffect(() => {
    const active = player.current;
    if (!active) return;
    const update: CallbackListener<"frameupdate"> = ({ detail }) => setFrame(detail.frame);
    const play = () => setPlaying(true);
    const pause = () => setPlaying(false);
    // Remotion's space-key option relies on its built-in play button. Our controls
    // are outside the picture, so handle shortcuts only while this player is fullscreen.
    const keydown = (event: KeyboardEvent) => {
      if (!active.isFullscreen()) return;
      if (event.code === "Escape") {
        active.exitFullscreen();
        return;
      }
      if (event.code !== "Space") return;
      event.preventDefault();
      if (!event.repeat) toggle();
    };
    window.addEventListener("keydown", keydown);
    active.addEventListener("frameupdate", update);
    active.addEventListener("play", play);
    active.addEventListener("pause", pause);
    active.addEventListener("ended", pause);
    return () => {
      window.removeEventListener("keydown", keydown);
      active.removeEventListener("frameupdate", update);
      active.removeEventListener("play", play);
      active.removeEventListener("pause", pause);
      active.removeEventListener("ended", pause);
    };
  }, [toggle]);
  const seek = (next: number, play = false) => {
    hasPlayed.current = true;
    player.current?.seekTo(next);
    if (play) player.current?.play();
    else player.current?.pause();
  };
  return (
    <>
      <header className="site-header">
        <a href="https://hexly.ai" aria-label="Hexly AI">
          <BrandLockup />
        </a>
        <a className="repo-link" href={story.repository}>
          hermes on herdr ↗
        </a>
      </header>
      <main>
        <section className="intro-copy">
          <p className="eyebrow">
            <RedDot size={8} /> ENGLISH FILM
          </p>
          <div className="headline-row">
            <h1>Context is control.</h1>
            <p>A trusted Hermes. A connected team.</p>
          </div>
        </section>
        <section className="stage" aria-label="English animation preview">
          <Player
            ref={player}
            component={Film}
            durationInFrames={filmMetadata.durationInFrames}
            fps={filmMetadata.fps}
            compositionWidth={filmMetadata.width}
            compositionHeight={filmMetadata.height}
            inputProps={inputProps}
            initialFrame={initialFrame}
            controls={false}
            moveToBeginningWhenEnded={false}
            clickToPlay={false}
            style={{ width: "100%", aspectRatio: "16 / 9" }}
          />
        </section>
        <section className="playback" aria-label="Playback controls">
          <button type="button" className="play-button" onClick={toggle}>
            {playing ? "Pause" : "Play"}
          </button>
          <button type="button" onClick={() => seek(0, true)}>
            Restart
          </button>
          <input
            aria-label="Preview position"
            type="range"
            min={0}
            max={timing.durationInFrames - 1}
            value={frame}
            onChange={(e) => seek(Number(e.target.value))}
          />
          <span className="timecode">
            {stamp(frame)} / {stamp(timing.durationInFrames)}
          </span>
          <button type="button" aria-pressed={captions} onClick={() => setCaptions((v) => !v)}>
            CC
          </button>
          <button
            type="button"
            title="Space to pause or play; Esc to leave fullscreen"
            onClick={() => player.current?.requestFullscreen()}
          >
            Fullscreen
          </button>
        </section>
        <nav className="chapters" aria-label="Film chapters">
          {timing.scenes.map((shot, i) => (
            <button
              key={shot.id}
              type="button"
              aria-current={chapter === i ? "step" : undefined}
              onClick={() => seek(shot.start, true)}
            >
              <span className="chapter-time">{stamp(shot.start)}</span>
              {names[i]}
            </button>
          ))}
        </nav>
        <div className="review-info">
          <span>English · 1920 × 1080 · 30 fps</span>
          <span>
            <a href={`review/${story.filename}`} target="_blank" rel="noreferrer">
              Play MP4 ↗
            </a>{" "}
            ·{" "}
            <a href={`review/${story.filename}`} download>
              Download MP4
            </a>
          </span>
        </div>
        <details className="production-notes">
          <summary>Story &amp; verification notes</summary>
          <h2>{scene?.title}</h2>
          <p>{scene?.narration.join(" ")}</p>
          {scene && "qualifications" in scene ? <p>{scene.qualifications?.join(" ")}</p> : null}
          <p>
            Current 0.x evidence: Discord connectivity is recorded. Telegram/Slack integration, a
            fresh message-to-pane round trip, and complete cold-start/exit integration are not
            independently verified. Channel access needs configuration. The host, gateway, messaging
            and model services must remain reachable. The chosen profile retains same-user terminal
            permissions; session binding is not an OS sandbox.
          </p>
          <a href="logos/SOURCES.md">Product logo sources ↗</a>
        </details>
      </main>
      <footer>
        <BrandLockup />
        <span className="footer-note">Let the system manage the talent.</span>
      </footer>
    </>
  );
}

const root = document.getElementById("root");
if (!root) throw new Error("Missing app root");
createRoot(root).render(<App />);
