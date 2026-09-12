import { ease, hexly, Intro, Outro, RedDot, useHexlyFonts } from "@hexly/video-kit";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { World } from "./art/World";
import { shotAt, story, timing } from "./timeline";

export type FilmProps = { captions: boolean; audio: boolean };

export function wrapCaption(text: string) {
  const words = text.split(" ");
  const lines: string[] = [""];
  for (const word of words) {
    const previous = lines[lines.length - 1] ?? "";
    if (previous && previous.length + word.length + 1 > 79) lines.push(word);
    else lines[lines.length - 1] = previous ? `${previous} ${word}` : word;
  }
  return lines.join("\n");
}

function Captions({ frame }: { frame: number }) {
  const caption = timing.captions.find(
    (c) => frame / timing.fps >= c.start && frame / timing.fps < c.end,
  );
  if (!caption) return null;
  return (
    <div
      data-caption
      style={{
        position: "absolute",
        left: 152,
        right: 152,
        bottom: 35,
        textAlign: "center",
        color: hexly.ink,
        fontFamily: hexly.sans,
        fontSize: 32,
        lineHeight: 1.35,
        whiteSpace: "pre-line",
        fontWeight: 400,
        padding: "9px 22px",
        background: `${hexly.page}f4`,
        borderRadius: 8,
      }}
    >
      {wrapCaption(caption.text)}
    </div>
  );
}

export function Film({ captions = true, audio = true }: FilmProps) {
  const frame = useCurrentFrame();
  const { shot, scene, local } = shotAt(frame);
  const ready = useHexlyFonts();
  const isBookend = scene.id === "intro" || scene.id === "outro";
  const enter = ease(local / 24);
  const exit = ease((shot.duration - local) / 14);
  const moving = { opacity: enter * exit, transform: `translateY(${(1 - enter) * 22}px)` };
  const qualifications = "qualifications" in scene ? scene.qualifications : [];
  return (
    <AbsoluteFill style={{ background: hexly.page, color: hexly.ink, fontFamily: hexly.sans }}>
      {ready && !isBookend ? (
        <>
          <AbsoluteFill style={{ opacity: Math.min(ease(local / 12), exit) }}>
            <World id={scene.id} frame={local} />
          </AbsoluteFill>
          <div
            style={{
              position: "absolute",
              left: 112,
              top: 80,
              right: 112,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 15,
                fontSize: 25,
                letterSpacing: -0.6,
              }}
            >
              <RedDot size={11} />
              hermes on herdr
            </div>
            <div
              style={{
                fontFamily: hexly.mono,
                fontSize: 17,
                color: hexly.muted,
                letterSpacing: 1.2,
              }}
            >
              {String(shot.index).padStart(2, "0")} / CONTEXT IS CONTROL
            </div>
          </div>
          <div
            data-shot-title
            style={{
              position: "absolute",
              left: 112,
              top: scene.id === "monitor" ? 295 : 306,
              width: scene.id === "monitor" ? 620 : 820,
              ...moving,
            }}
          >
            <div
              style={{
                color: hexly.accent,
                fontFamily: hexly.mono,
                fontSize: 19,
                letterSpacing: 1.7,
                marginBottom: 30,
              }}
            >
              {scene.eyebrow}
            </div>
            <div
              style={{
                fontSize: scene.id === "monitor" ? 88 : 100,
                fontWeight: 500,
                letterSpacing: -5.5,
                lineHeight: 1.06,
                whiteSpace: "pre-line",
              }}
            >
              {scene.title}
            </div>
            {scene.id === "weekend" ? (
              <div
                style={{ marginTop: 38, fontFamily: hexly.mono, fontSize: 22, color: hexly.muted }}
              >
                github.com/nocoo/hermes-on-herdr
              </div>
            ) : null}
          </div>
          {qualifications?.length ? (
            <div
              data-qualification
              style={{
                position: "absolute",
                left: 112,
                right: 112,
                bottom: 170,
                color: hexly.muted,
                fontSize: 25,
                lineHeight: 1.45,
                opacity: ease((local - 15) / 18) * exit,
              }}
            >
              {qualifications.map((line) => (
                <div key={line}>
                  <span style={{ background: `${hexly.page}ed`, padding: "3px 7px 3px 0" }}>
                    {line}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
      {scene.id === "intro" ? (
        <Sequence from={shot.start} durationInFrames={shot.duration}>
          <Intro title={scene.title} eyebrow={scene.eyebrow} template="studio">
            <div style={{ width: 440, height: 460, display: "grid", placeItems: "center" }}>
              <Img
                src={staticFile("product/logo.png")}
                style={{
                  width: 390,
                  height: 390,
                  objectFit: "contain",
                  transform: `translateY(${(1 - enter) * 18}px)`,
                  opacity: enter,
                }}
              />
            </div>
          </Intro>
        </Sequence>
      ) : null}
      {scene.id === "outro" ? (
        <Sequence from={shot.start} durationInFrames={shot.duration}>
          <Outro title={scene.title} template="studio" />
        </Sequence>
      ) : null}
      {ready && captions ? <Captions frame={frame} /> : null}
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
