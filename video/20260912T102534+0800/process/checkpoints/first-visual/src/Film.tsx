import { useEffect, useState } from "react";
import {
  AbsoluteFill,
  Audio,
  cancelRender,
  continueRender,
  delayRender,
  Img,
  interpolateColors,
  staticFile,
  useCurrentFrame,
} from "remotion";
import * as THREE from "three";
import { createTextures, type Textures } from "./art/textures";
import { World } from "./art/World";
import { artCenter, clamp, type Language, sceneAt, smooth, story, timing } from "./timeline";
import "./film.css";

export type FilmProps = { language: Language; captions?: boolean; audio?: boolean };

function useAssets(language: Language) {
  const [handle] = useState(() =>
    delayRender("Load local OFL fonts and original terminal textures"),
  );
  const [textures, setTextures] = useState<Textures | null>(null);
  useEffect(() => {
    let active = true;
    let loaded: Textures | null = null;
    const load = async () => {
      await Promise.all(
        [
          ["Space Grotesk", "space-grotesk.woff2", "300 700"],
          ["Geist Mono", "geist-mono.woff2", "100 900"],
          ["Noto Sans SC", "noto-sans-sc.woff2", "100 900"],
        ].map(async ([family, filename, weight]) => {
          const font = new FontFace(family, `url(${staticFile(`fonts/${filename}`)})`, { weight });
          await font.load();
          document.fonts.add(font);
        }),
      );
      const monitor = await new THREE.TextureLoader().loadAsync(
        staticFile("product/monitor-demo.png"),
      );
      monitor.colorSpace = THREE.SRGBColorSpace;
      monitor.anisotropy = 4;
      loaded = { ...createTextures(language), monitor };
      if (active) {
        setTextures(loaded);
        continueRender(handle);
      }
    };
    load().catch(cancelRender);
    return () => {
      active = false;
      if (loaded) Object.values(loaded).forEach((texture) => texture.dispose());
    };
  }, [handle, language]);
  return textures;
}

export function HexlyMark({
  size = 48,
  color = "#bf5c3c",
  paper = "#f0f0e9",
}: {
  size?: number;
  color?: string;
  paper?: string;
}) {
  // Official Hexly geometry, from its owner's src/components/Icon.tsx BrandMark.
  return (
    <svg width={size * 0.9} height={size} viewBox="0 0 36 40" fill="none" aria-hidden="true">
      <path d="m18 2 15.6 9v18L18 38 2.4 29V11Z" fill={color} />
      <path d="m18 9 9.5 5.5v11L18 31l-9.5-5.5v-11Z" stroke={paper} strokeWidth="1.6" />
      <path d="M18 9v22M8.5 14.5l19 11m0-11-19 11" stroke={paper} strokeWidth="1.6" />
    </svg>
  );
}

export function Film({ language = "zh", captions = true, audio = true }: FilmProps) {
  const frame = useCurrentFrame();
  const shot = sceneAt(frame);
  const scene = story.scenes[shot.index];
  const copy = scene.copy[language];
  const textures = useAssets(language);
  const closing = scene.id === "closing";
  const opening = scene.id === "opening";
  const right = artCenter(shot.index) < 960;
  const seconds = frame / timing.fps;
  const caption = timing.captions[language].find(
    (line) => seconds >= line.start && seconds < line.end,
  );
  const background = closing
    ? interpolateColors(shot.local, [0, 42], ["#0b161c", "#f0f0e9"])
    : "#0b161c";
  const ink = closing ? interpolateColors(shot.local, [0, 42], ["#eef2e7", "#30372e"]) : "#eef2e7";
  const opacity = (opening ? Math.max(0.15, shot.entry) : shot.entry) * shot.exit;
  const closingTitle = language === "en" ? "Manage the genius.\nKeep your weekend." : copy.title;
  return (
    <AbsoluteFill
      className={`film ${closing ? "film-closing" : ""} ${opening ? "film-opening" : ""}`}
      style={{ background, color: ink }}
    >
      <div
        className="film-atmosphere"
        style={{
          opacity: closing ? 1 - smooth(shot.local / 70) : 1,
          background: `radial-gradient(ellipse 630px 600px at ${shot.center}px 510px, #3150585c, transparent 76%), radial-gradient(ellipse 1400px 900px at 80% 110%, #b5984721, transparent 74%)`,
        }}
      />
      <div className="film-grid" style={{ opacity: closing ? 0.04 : 0.1 }} />
      <div className="film-horizon" style={{ opacity: closing ? 0.16 : 0.45 }} />
      <header className="film-header">
        <div className="film-brand">
          <Img src={staticFile("brand/product.png")} alt="" />
          <strong>hermes on herdr</strong>
        </div>
        <div className="film-edition">
          <span />
          {opening || closing ? "THE WEEKEND PROTOCOL" : "HEXLY AI / PROJECT FILMS"}
        </div>
      </header>
      {textures && <World frame={frame} textures={textures} />}
      <section
        className={`film-copy ${right ? "film-copy-right" : ""} ${closing ? "film-copy-closing" : ""}`}
        style={{ opacity, transform: `translateY(${(1 - shot.entry) * 22}px)` }}
      >
        <div className="film-kicker">
          <span style={{ opacity: 0.6 + 0.4 * Math.sin(frame / 24) ** 2 }} />
          {scene.kicker}
        </div>
        <h1
          style={{
            fontSize: closing
              ? language === "zh"
                ? 65
                : 73
              : opening
                ? 110
                : language === "zh"
                  ? 83
                  : 76,
          }}
        >
          {(closing ? closingTitle : copy.title).split("\n").map((line, i) => (
            <span key={line} className={i > 0 ? "film-accent" : ""}>
              {line}
            </span>
          ))}
        </h1>
        <p className="film-body">{copy.body}</p>
        {!closing && (
          <div className="film-badges" style={{ opacity: smooth((shot.local - 26) / 30) }}>
            {copy.badges.map((badge) => (
              <span key={badge}>
                <i />
                {badge}
              </span>
            ))}
          </div>
        )}
        {closing && (
          <div className="film-hexly" style={{ opacity: smooth((shot.local - 42) / 32) }}>
            <div>
              <HexlyMark size={65} />
              <strong>
                hexly<span>.</span>
                <em>ai</em>
              </strong>
            </div>
            <p>github.com/nocoo/hermes-on-herdr</p>
          </div>
        )}
      </section>
      {scene.id === "monitor" && (
        <div className="film-demo-note" style={{ opacity: shot.entry * shot.exit }}>
          {language === "zh"
            ? "TUI 为离线演示数据 · 消息交流为示意"
            : "OFFLINE DEMO TUI · ILLUSTRATIVE MESSAGING"}
        </div>
      )}
      {captions && caption && (
        <div
          className="film-caption"
          style={{
            opacity: Math.min(
              clamp((seconds - caption.start) * 12),
              clamp((caption.end - seconds) * 12),
            ),
          }}
        >
          <span>{caption.text}</span>
        </div>
      )}
      <footer className="film-footer">
        <span>
          {closing ? "HEXLY AI" : String(shot.index).padStart(2, "0")}
          <i>
            {closing
              ? " / MADE FOR YOUR TIME"
              : ` / ${String(story.scenes.length - 1).padStart(2, "0")}`}
          </i>
        </span>
        <div className="film-progress">
          {timing.scenes.map((item) => (
            <span key={item.id}>
              <i style={{ width: `${clamp((frame - item.start) / item.duration) * 100}%` }} />
            </span>
          ))}
        </div>
        <span>{closing ? "hexly.ai" : "THE WEEKEND PROTOCOL"}</span>
      </footer>
      {audio && <Audio src={staticFile(`audio/mix-${language}.m4a`)} />}
    </AbsoluteFill>
  );
}
