import { BrandLockup, ease, HexlyReveal, hexly, RedDot, useHexlyFonts } from "@hexly/video-kit";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { color, Flow } from "./art/Flow";
import { captionAt } from "./captions";
import { shotAt, story, timing } from "./timeline";

export type FilmProps = { captions: boolean; audio: boolean };

export function Film({ captions = true, audio = true }: FilmProps) {
  const frame = useCurrentFrame();
  const { shot, scene, local } = shotAt(frame);
  const ready = useHexlyFonts();
  const enter = ease(local / 22);
  const exit = ease((shot.duration - local) / 12);
  const caption = captionAt(frame / timing.fps);
  const bookend = scene.id === "intro" || scene.id === "outro";
  return (
    <AbsoluteFill
      data-film-frame={frame}
      data-film-scene={scene.id}
      style={{
        background: hexly.page,
        color: hexly.ink,
        fontFamily: hexly.sans,
        colorScheme: "light",
      }}
    >
      {ready && !bookend ? (
        <>
          <div
            style={{
              position: "absolute",
              left: 112,
              top: 70,
              display: "flex",
              gap: 14,
              alignItems: "center",
              fontSize: 24,
            }}
          >
            <RedDot size={10} /> hermes on herdr
          </div>
          <div
            style={{
              position: "absolute",
              right: 112,
              top: 76,
              color: hexly.muted,
              fontFamily: hexly.mono,
              fontSize: 18,
            }}
          >
            {String(shot.index).padStart(2, "0")}
          </div>
          <AbsoluteFill style={{ opacity: Math.min(ease(local / 12), exit) }}>
            <Flow id={scene.id} frame={local} />
          </AbsoluteFill>
          <div
            data-shot-title
            style={{
              position: "absolute",
              left: 125,
              right: 125,
              top: 181,
              fontSize: 94,
              fontWeight: 500,
              letterSpacing: -4.8,
              lineHeight: 1.14,
              textAlign: "center",
              whiteSpace: "nowrap",
              opacity: enter * exit,
              transform: `translateY(${(1 - enter) * 18}px)`,
            }}
          >
            {scene.title}
          </div>
        </>
      ) : null}
      {ready && scene.id === "intro" ? (
        <AbsoluteFill style={{ opacity: exit }}>
          <div style={{ position: "absolute", left: 112, top: 70 }}>
            <BrandLockup scale={1.1} />
          </div>
          <Img
            src={staticFile("product/logo.png")}
            alt="hermes on herdr"
            style={{
              position: "absolute",
              left: 879,
              top: 256,
              width: 162,
              height: 162,
              objectFit: "contain",
              opacity: enter,
            }}
          />
          <div
            style={{
              position: "absolute",
              left: 112,
              right: 112,
              top: 439,
              textAlign: "center",
              fontSize: 27,
              color: hexly.accent,
              opacity: enter,
            }}
          >
            hermes on herdr
          </div>
          <div
            data-shot-title
            style={{
              position: "absolute",
              left: 112,
              right: 112,
              top: 515,
              textAlign: "center",
              fontSize: 114,
              fontWeight: 500,
              letterSpacing: -6,
              lineHeight: 1.16,
              opacity: enter,
              transform: `translateY(${(1 - enter) * 24}px)`,
            }}
          >
            {scene.title}
          </div>
          <div
            style={{
              position: "absolute",
              top: 727,
              left: 810,
              width: 300 * enter,
              height: 5,
              borderRadius: 5,
              background: color.coral,
            }}
          />
        </AbsoluteFill>
      ) : null}
      {scene.id === "outro" ? (
        <Sequence from={shot.start} durationInFrames={shot.duration}>
          <AbsoluteFill data-brand-reveal-fix>
            <style>{`[data-brand-reveal-fix] [data-hexly-wordmark] { overflow: visible !important; clip-path: inset(-40px 0 -40px -4px); }`}</style>
            <HexlyReveal caption="hermes on herdr" template="essential" />
          </AbsoluteFill>
        </Sequence>
      ) : null}
      {ready && captions && caption ? (
        <div
          data-caption
          style={{
            position: "absolute",
            left: 130,
            right: 130,
            bottom: 61,
            color: hexly.ink,
            fontFamily: hexly.sans,
            fontSize: 32,
            lineHeight: 1.4,
            textAlign: "center",
            fontWeight: 400,
          }}
        >
          {caption.text}
        </div>
      ) : null}
      {audio ? <Audio src={staticFile("audio/mix-en.m4a")} /> : null}
    </AbsoluteFill>
  );
}

export const filmMetadata = {
  durationInFrames: timing.durationInFrames,
  fps: story.fps,
  width: story.width,
  height: story.height,
};
