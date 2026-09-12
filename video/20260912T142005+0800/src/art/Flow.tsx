import { hexly } from "@hexly/video-kit";
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { between, lerp } from "../timeline";

export const color = {
  blue: "#596DD9",
  coral: "#DB765F",
  mint: "#45A78A",
  lilac: "#AB87D0",
  yellow: "#F4C764",
  paleBlue: "#CAD5F6",
  paleCoral: "#F1CBBC",
} as const;

const files = {
  codex: "codex.png",
  grok: "grok.png",
  pi: "pi.svg",
  "claude-code": "claude-code.png",
  hermes: "hermes.jpg",
  herdr: "herdr.png",
  discord: "discord-blurple.svg",
  telegram: "telegram.svg",
  slack: "slack.png",
} as const;
export type LogoId = keyof typeof files;
const names: Record<LogoId, string> = {
  codex: "Codex",
  grok: "Grok",
  pi: "Pi",
  "claude-code": "Claude Code",
  hermes: "Hermes",
  herdr: "Herdr",
  discord: "Discord",
  telegram: "Telegram",
  slack: "Slack",
};
const agents = ["codex", "grok", "pi", "claude-code"] as const;
type Point = readonly [number, number];
type Curve = readonly [Point, Point, Point, Point];

export function curvePoint(points: Curve, t: number): Point {
  const u = 1 - t;
  const coordinate = (axis: 0 | 1) =>
    u ** 3 * points[0][axis] +
    3 * u ** 2 * t * points[1][axis] +
    3 * u * t ** 2 * points[2][axis] +
    t ** 3 * points[3][axis];
  return [coordinate(0), coordinate(1)];
}

function Label({
  x,
  y,
  children,
  size = 28,
  ink = hexly.ink,
  mono = false,
  style,
}: {
  x: number;
  y: number;
  children: ReactNode;
  size?: number;
  ink?: string;
  mono?: boolean;
  style?: CSSProperties;
}) {
  return (
    <div
      data-flow-label
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: "translateX(-50%)",
        fontFamily: mono ? hexly.mono : hexly.sans,
        color: ink,
        fontSize: size,
        lineHeight: 1.3,
        letterSpacing: mono ? 0 : -0.6,
        whiteSpace: "nowrap",
        textAlign: "center",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function Logo({
  brand,
  x,
  y,
  size = 144,
  label,
  opacity = 1,
}: {
  brand: LogoId;
  x: number;
  y: number;
  size?: number;
  label?: string | false;
  opacity?: number;
}) {
  return (
    <div data-product-logo={brand} style={{ opacity }}>
      <Img
        src={staticFile(`logos/${files[brand]}`)}
        alt={names[brand]}
        style={{
          position: "absolute",
          left: x - size / 2,
          top: y - size / 2,
          width: size,
          height: size,
          objectFit: "contain",
        }}
      />
      {label !== false ? (
        <Label x={x} y={y + size / 2 + 24} size={size < 100 ? 24 : 30}>
          {label ?? names[brand]}
        </Label>
      ) : null}
    </div>
  );
}

function Ribbon({
  points,
  seconds,
  delay = 0,
  ink = color.blue,
  width = 6,
  signal = true,
  dashed = false,
}: {
  points: Curve;
  seconds: number;
  delay?: number;
  ink?: string;
  width?: number;
  signal?: boolean;
  dashed?: boolean;
}) {
  const draw = between(seconds, delay, delay + 1.05);
  const travel = Math.max(0, seconds - delay - 1.1);
  const t = (travel % 3.5) / 3.5;
  const [x, y] = curvePoint(points, t);
  const [a, b, c, d] = points;
  const line = `M${a.join(",")} C${b.join(",")} ${c.join(",")} ${d.join(",")}`;
  return (
    <svg
      width={1920}
      height={1080}
      viewBox="0 0 1920 1080"
      aria-hidden="true"
      style={{ position: "absolute", inset: 0, overflow: "visible" }}
    >
      <path
        d={line}
        fill="none"
        stroke={ink}
        strokeWidth={width}
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray={dashed ? "0.015 0.025" : 1}
        strokeDashoffset={dashed ? -seconds * 0.009 : 1 - draw}
        opacity={dashed ? draw * 0.75 : 1}
      />
      {signal && travel > 0 ? (
        <circle
          cx={x}
          cy={y}
          r={10}
          fill={color.coral}
          stroke={hexly.page}
          strokeWidth={5}
          opacity={between(t, 0, 0.06) * (1 - between(t, 0.9, 1))}
        />
      ) : null}
    </svg>
  );
}

function Session({
  x,
  y,
  width,
  height,
  progress = 1,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
  progress?: number;
}) {
  return (
    <>
      <svg width={1920} height={1080} aria-hidden="true" style={{ position: "absolute" }}>
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          rx={32}
          fill="none"
          stroke={color.blue}
          strokeWidth={2.5}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - progress}
        />
      </svg>
      <Label x={x + 175} y={y - 40} size={19} mono ink={color.blue} style={{ opacity: progress }}>
        CURRENT HERDR SESSION
      </Label>
    </>
  );
}

function Note({ children }: { children: ReactNode }) {
  return (
    <Label x={960} y={866} size={24} ink={hexly.muted}>
      {children}
    </Label>
  );
}

function Context({ t }: { t: number }) {
  return (
    <>
      <Session x={1130} y={379} width={534} height={391} progress={between(t, 0.6, 1.7)} />
      <Ribbon
        points={[
          [605, 554],
          [750, 554],
          [800, 554],
          [875, 554],
        ]}
        seconds={t}
        ink={color.coral}
      />
      <Ribbon
        points={[
          [1045, 554],
          [1180, 554],
          [1210, 554],
          [1310, 554],
        ]}
        seconds={t}
        delay={0.5}
        ink={color.paleBlue}
        signal={false}
        dashed
      />
      <Logo brand="hermes" x={500} y={554} size={162} />
      <Logo brand="herdr" x={1420} y={554} size={162} />
      <Label x={960} y={519} size={61} ink={color.coral} style={{ opacity: between(t, 1.6, 2.2) }}>
        ≠
      </Label>
      <Label x={1420} y={712} size={22} mono ink={color.blue}>
        pane · socket · caller
      </Label>
      <Note>Not inherited automatically</Note>
    </>
  );
}

function Talent({ t }: { t: number }) {
  const align = between(t, 4.2, 6.8);
  const starts: Point[] = [
    [417, 488],
    [790, 641],
    [1154, 466],
    [1520, 621],
  ];
  return (
    <>
      {[color.blue, color.coral, color.mint].map((ink, i) => (
        <Ribbon
          key={ink}
          points={[
            [417 + i * 366, lerp(starts[i]?.[1] ?? 500, 560, align)],
            [580 + i * 366, lerp(i % 2 ? 200 : 810, 560, align)],
            [625 + i * 366, lerp(i % 2 ? 860 : 250, 560, align)],
            [783 + i * 366, lerp(starts[i + 1]?.[1] ?? 500, 560, align)],
          ]}
          seconds={t}
          delay={i * 0.25 + 0.4}
          ink={ink}
          width={5}
        />
      ))}
      {agents.map((id, i) => {
        const start = starts[i] ?? [0, 0];
        const entrance = between(t, i * 0.2, i * 0.2 + 0.8);
        return (
          <Logo
            key={id}
            brand={id}
            x={lerp(start[0], 417 + i * 366, align)}
            y={lerp(start[1], 560, align) + (1 - entrance) * 70}
            opacity={entrance}
            size={152}
          />
        );
      })}
      <Label x={960} y={811} size={35} style={{ opacity: between(t, 4.4, 5.5) }}>
        More talent. More coordination.
      </Label>
    </>
  );
}

function Bind({ t }: { t: number }) {
  const x = lerp(458, 1000, between(t, 1.3, 3.7));
  return (
    <>
      <Session x={773} y={385} width={905} height={394} progress={between(t, 0.1, 1.4)} />
      <Ribbon
        points={[
          [x + 107, 555],
          [1190, 555],
          [1240, 555],
          [1333, 555],
        ]}
        seconds={t}
        delay={3.4}
        ink={color.coral}
      />
      <Logo brand="hermes" x={x} y={555} size={162} label="Trusted Hermes" />
      <Logo brand="herdr" x={1440} y={555} size={162} />
      <Label
        x={1220}
        y={713}
        size={23}
        mono
        ink={color.blue}
        style={{ opacity: between(t, 3.7, 4.5) }}
      >
        pane · socket · caller
      </Label>
      <Label x={478} y={706} size={29} ink={color.coral} style={{ opacity: 1 - between(t, 3, 4) }}>
        You choose.
      </Label>
      <Note>A dedicated profile, explicitly bound</Note>
    </>
  );
}

function Managers({ t }: { t: number }) {
  const targets: Point[] = [
    [1345, 404],
    [1625, 526],
    [1625, 740],
    [1345, 788],
  ];
  return (
    <>
      <Ribbon
        points={[
          [475, 563],
          [585, 563],
          [665, 563],
          [755, 563],
        ]}
        seconds={t}
        delay={0.3}
        ink={color.coral}
      />
      {targets.map(([x, y], i) => (
        <Ribbon
          key={agents[i]}
          points={[
            [945, 563],
            [1110, 563],
            [1110, y],
            [x - 82, y],
          ]}
          seconds={t}
          delay={1.1 + i * 0.32}
          ink={[color.blue, color.lilac, color.mint, color.coral][i]}
          width={4}
        />
      ))}
      <Logo brand="hermes" x={375} y={563} size={155} label="Hermes · M2" />
      <Logo brand="herdr" x={850} y={563} size={155} label="Herdr · manager" />
      {agents.map((id, i) => (
        <Logo
          key={id}
          brand={id}
          x={targets[i]?.[0] ?? 0}
          y={targets[i]?.[1] ?? 0}
          size={112}
          opacity={between(t, 0.45 + i * 0.12, 1.2 + i * 0.12)}
        />
      ))}
      <Note>Full control of the bound session</Note>
    </>
  );
}

function Channels({ t, local = false }: { t: number; local?: boolean }) {
  return (
    <>
      <Session x={826} y={382} width={880} height={392} progress={between(t, 0.3, 1.5)} />
      <Ribbon
        points={[
          [640, 577],
          [742, 577],
          [785, 577],
          [925, 577],
        ]}
        seconds={t}
        delay={1.2}
        ink={color.coral}
      />
      <Ribbon
        points={[
          [1135, 577],
          [1210, 577],
          [1310, 577],
          [1395, 577],
        ]}
        seconds={t}
        delay={2.2}
      />
      <Logo brand="hermes" x={1030} y={577} size={148} label="Hermes · M2" />
      <Logo brand="herdr" x={1500} y={577} size={148} />
      <div style={{ opacity: between(t, 0, 0.8) }}>
        {(["discord", "telegram", "slack"] as const).map((id, i) => (
          <Logo key={id} brand={id} x={285 + i * 150} y={465} size={70} label={false} />
        ))}
        <Label x={436} y={571} size={39}>
          {local ? "You're connected." : "Check the team."}
        </Label>
        <Label x={436} y={649} size={24} ink={color.coral}>
          Your channel
        </Label>
      </div>
      {local ? (
        <>
          <Label x={1030} y={414} size={22} mono ink={color.blue}>
            LOCAL CONTROL
          </Label>
          <Note>Host + gateway stay online</Note>
        </>
      ) : (
        <Note>Configured channels · illustrative workflow</Note>
      )}
    </>
  );
}

function Monitor({ t }: { t: number }) {
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 786,
          top: 368,
          width: 900,
          height: 464,
          opacity: between(t, 0.2, 1.1),
          transform: `translateY(${(1 - between(t, 0.2, 1.5)) * 35}px)`,
        }}
      >
        <Img
          src={staticFile("cli/monitor-ready.svg")}
          alt="Native Herdr plugin monitor, fictional offline demo data"
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
        />
      </div>
      <Logo brand="hermes" x={376} y={446} size={100} label={false} />
      <Logo brand="herdr" x={555} y={446} size={100} label={false} />
      <Ribbon
        points={[
          [440, 446],
          [459, 446],
          [473, 446],
          [492, 446],
        ]}
        seconds={t}
        delay={0.3}
        width={4}
      />
      {["start", "pause", "resume", "stop"].map((command, i) => (
        <Label
          key={command}
          x={460}
          y={555 + i * 61}
          size={28}
          mono
          style={{ opacity: between(t, 0.4 + i * 0.3, 1.1 + i * 0.3) }}
        >
          {command}
        </Label>
      ))}
      <Note>Native monitor · offline demo data</Note>
    </>
  );
}

function Trust({ t }: { t: number }) {
  return (
    <>
      <Session x={844} y={371} width={861} height={406} progress={between(t, 0.2, 1.4)} />
      <Logo brand="hermes" x={400} y={555} size={123} label="External instance" />
      <Logo brand="hermes" x={1060} y={555} size={154} label="Chosen profile" />
      <Logo brand="herdr" x={1500} y={555} size={154} />
      <Ribbon
        points={[
          [1160, 555],
          [1250, 555],
          [1305, 555],
          [1398, 555],
        ]}
        seconds={t}
        delay={0.7}
        ink={color.mint}
      />
      <Label x={700} y={523} size={60} ink={color.coral}>
        ≠
      </Label>
      <Note>{t < 4.5 ? "No public control plane" : "Session binding ≠ OS sandbox"}</Note>
    </>
  );
}

function Weekend({ t }: { t: number }) {
  const draw = between(t, 0.3, 1.7);
  return (
    <>
      <svg width={1920} height={1080} aria-hidden="true" style={{ position: "absolute" }}>
        <ellipse
          cx={520}
          cy={612}
          rx={230}
          ry={176}
          fill="none"
          stroke={color.blue}
          strokeWidth={4}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - draw}
        />
        <path
          d="M994 686 A330 330 0 0 1 1654 686"
          fill={color.yellow}
          opacity={between(t, 1.1, 2.9)}
        />
        <path
          d="M975 705 H1680"
          fill="none"
          stroke={color.coral}
          strokeWidth={4}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - between(t, 1.9, 3.2)}
        />
      </svg>
      <Logo brand="hermes" x={465} y={599} size={88} label={false} />
      <Logo brand="herdr" x={586} y={599} size={88} label={false} />
      {agents.map((id, i) => {
        const angle = (i / 4) * Math.PI * 2 - Math.PI / 2 + t * 0.2;
        return (
          <Logo
            key={id}
            brand={id}
            x={520 + Math.cos(angle) * 230}
            y={612 + Math.sin(angle) * 176}
            size={76}
            label={false}
            opacity={draw}
          />
        );
      })}
      <Label
        x={1190}
        y={554}
        size={82}
        style={{ fontWeight: 500, opacity: between(t, 1.4, 2.2), letterSpacing: -4 }}
      >
        SAT
      </Label>
      <Label
        x={1490}
        y={554}
        size={82}
        style={{ fontWeight: 500, opacity: between(t, 1.7, 2.5), letterSpacing: -4 }}
      >
        SUN
      </Label>
      <Label x={1320} y={750} size={30} ink={color.coral} style={{ opacity: between(t, 2.1, 3.2) }}>
        Yours again.
      </Label>
    </>
  );
}

export function Flow({ id, frame }: { id: string; frame: number }) {
  const t = frame / 30;
  let scene: ReactNode;
  switch (id) {
    case "context":
      scene = <Context t={t} />;
      break;
    case "talent":
      scene = <Talent t={t} />;
      break;
    case "bind":
      scene = <Bind t={t} />;
      break;
    case "managers":
      scene = <Managers t={t} />;
      break;
    case "channels":
      scene = <Channels t={t} />;
      break;
    case "local":
      scene = <Channels t={t} local />;
      break;
    case "monitor":
      scene = <Monitor t={t} />;
      break;
    case "trust":
      scene = <Trust t={t} />;
      break;
    case "weekend":
      scene = <Weekend t={t} />;
      break;
    default:
      scene = null;
  }
  return <AbsoluteFill data-motion="signal-flow">{scene}</AbsoluteFill>;
}
