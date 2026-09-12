import { Euler, Quaternion, Vector3 } from "three";
import { between, lerp } from "../timeline";

export const candy = {
  sky: "#B7DCF2",
  mint: "#BCE3CF",
  lilac: "#E8C9EB",
  peach: "#FFCBB6",
  lemon: "#F8D67C",
  oat: "#E7DCD0",
};
export type Vec3 = [number, number, number];
export type CubieSpec = {
  id: string;
  label: string;
  detail: string;
  color: string;
  position: Vec3;
  rotation: Vec3;
  scale: number;
};

const faceLabels = [
  ["Codex", "CODING IC"],
  ["Herdr", "MANAGER"],
  ["Grok", "CODING IC"],
  ["Pi", "CODING IC"],
  ["Hermes", "TRUSTED M2"],
  ["Claude Code", "CODING IC"],
  ["Pane", "MANAGED"],
  ["Socket", "LOCAL"],
  ["Caller", "CONTEXT"],
  ["Workflow", "COORDINATE"],
  [">_", "TERMINAL"],
  ["Plugin", "EXPLICIT LINK"],
  ["Discord", "CHANNEL"],
  ["Telegram", "CHANNEL"],
  ["Slack", "CHANNEL"],
  ["Profile", "CHOSEN"],
  ["Session", "BOUND OWNER"],
  ["Local", "CONTROL"],
];

export const grid: Vec3[] = [];
// Front layer first so the key names remain visible at the final camera angle.
for (const z of [1, 0, -1])
  for (const y of [1, 0, -1])
    for (const x of [-1, 0, 1]) {
      grid.push([x, y, z]);
    }

export function quarterTurn(position: Vec3, rotation: Vec3, axis: "x" | "y", angle: number) {
  const vector = new Vector3(...position);
  const normal = axis === "x" ? new Vector3(1, 0, 0) : new Vector3(0, 1, 0);
  vector.applyAxisAngle(normal, angle);
  const q = new Quaternion().setFromAxisAngle(normal, angle);
  q.multiply(new Quaternion().setFromEuler(new Euler(...rotation)));
  const e = new Euler().setFromQuaternion(q);
  return { position: vector.toArray() as Vec3, rotation: [e.x, e.y, e.z] as Vec3 };
}

export function assembledCube(seconds: number, exploded = true): CubieSpec[] {
  const close = exploded ? between(seconds, 0.2, 2.6) : 1;
  const top = (between(seconds, 3.0, 4.35) * Math.PI) / 2;
  const side = (between(seconds, 4.65, 6.0) * Math.PI) / 2;
  return grid.map((cell, index) => {
    let position = cell.map((v) => v * lerp(2.12, 1.075, close)) as Vec3;
    let rotation: Vec3 = [0, 0, 0];
    if (close < 1) {
      const drift = 1 - close;
      rotation = [
        drift * Math.sin(index * 3.1) * 0.4,
        drift * Math.cos(index * 1.6) * 0.55,
        drift * Math.sin(index * 0.8) * 0.3,
      ];
    }
    if (cell[1] === 1) ({ position, rotation } = quarterTurn(position, rotation, "y", top));
    // Membership is tested after the first complete turn, as on a real cube.
    if (position[0] > 0.9 && close === 1) {
      ({ position, rotation } = quarterTurn(position, rotation, "x", side));
    }
    const label = faceLabels[index % faceLabels.length];
    if (!label) throw new Error("Missing cube face");
    return {
      id: `cubie-${index}`,
      label: label[0] ?? "",
      detail: label[1] ?? "",
      color: Object.values(candy)[(index * 5 + Math.floor(index / 3)) % 6] ?? candy.mint,
      position,
      rotation,
      scale: 0.985,
    };
  });
}

const node = (
  id: string,
  label: string,
  color: string,
  position: Vec3,
  scale = 1.15,
  detail = "",
  rotation: Vec3 = [-0.05, 0.12, 0],
) => ({ id, label, detail, color, position, scale, rotation });

export function sceneCubies(id: string, seconds: number): CubieSpec[] {
  const f = (delay: number) => between(seconds, delay, delay + 1.0);
  const bob = (offset: number) => Math.sin(seconds * 0.65 + offset) * 0.045;
  if (id === "weekend") return assembledCube(seconds);
  if (id === "context")
    return [
      node("hermes", "Hermes", candy.oat, [-1.85, 0.05 + bob(0), 0.5], 1.45, "INDEPENDENT"),
      node("pane", "Pane", candy.lemon, [1.35, 1.5, 0], 1.1, "CONTEXT"),
      node("socket", "Socket", candy.mint, [2.05, -0.15, 0.7], 1.1, "CONTEXT"),
      node("caller", "Caller", candy.sky, [0.8, -1.35, 0.2], 1.1, "CONTEXT"),
    ];
  if (id === "talent")
    return [
      node(
        "codex",
        "Codex",
        candy.sky,
        [-2.2, lerp(-3.8, 0.8, f(0.05)) + bob(0), 0.6],
        1.32,
        "CODING IC",
        [0, 0.2, -0.06],
      ),
      node(
        "grok",
        "Grok",
        candy.peach,
        [-0.45, lerp(-3.8, -0.75, f(0.22)) + bob(1), 1.2],
        1.22,
        "CODING IC",
        [0.04, -0.15, 0.04],
      ),
      node(
        "pi",
        "Pi",
        candy.lemon,
        [1.05, lerp(-3.8, 1.1, f(0.42)) + bob(2), 0],
        1.25,
        "CODING IC",
        [0.02, 0.22, 0.08],
      ),
      node(
        "claude",
        "Claude Code",
        candy.lilac,
        [2.55, lerp(-3.8, -0.6, f(0.61)) + bob(3), 0.8],
        1.37,
        "CODING IC",
        [-0.06, -0.1, -0.06],
      ),
      node("workflow", "Workflow", candy.mint, [0.1, 1.55, -2], 0.8, "COORDINATION"),
      node("terminal", ">_", candy.oat, [-2.1, -1.35, -0.6], 0.7, "TERMINAL"),
      node("panes", "Pane", candy.sky, [2.9, 1.25, -1.8], 0.64, "HERDR"),
    ];
  if (id === "bind") {
    const nodes = assembledCube(0, false).filter((_, index) => index > 8 || index === 7);
    return [
      ...nodes.map((cube) => ({
        ...cube,
        scale: 0.985,
        position: [cube.position[0] + 0.4, cube.position[1] - 0.3, cube.position[2] - 0.6] as Vec3,
      })),
      node(
        "trusted",
        "Hermes",
        candy.oat,
        [lerp(-2.6, 0.4, f(1.2)), lerp(0.65, -0.3, f(1.2)), lerp(1.8, 0.475, f(1.2))],
        0.985,
        "CHOSEN M2",
        [0, lerp(-0.55, 0, f(1.2)), 0],
      ),
      node("pane", "Pane", candy.lemon, [-1.6, 1.8, 0], 0.85, "MANAGED"),
      node("socket", "Socket", candy.mint, [0.1, 2.0, -0.15], 0.85, "LOCAL"),
      node("caller", "Caller", candy.sky, [1.8, 1.85, 0], 0.85, "REAL IDENTITY"),
    ];
  }
  if (id === "managers")
    return [
      node("hermes", "Hermes", candy.oat, [0, 2, 0], 1.1, "M2"),
      node("herdr", "Herdr", candy.mint, [0, 0.2, 0], 1.14, "MANAGER"),
      ...["Codex", "Grok", "Pi", "Claude Code"].map((label, index) =>
        node(
          label,
          label,
          [candy.sky, candy.peach, candy.lemon, candy.lilac][index] ?? candy.sky,
          [-2.7 + index * 1.8, -1.75, 0],
          1.06,
          "CODING IC",
          [0, 0, 0],
        ),
      ),
    ];
  if (id === "channels")
    return [
      node("discord", "Discord", candy.lilac, [-1.5, 1.65, -0.7], 1.03, "CHANNEL"),
      node("telegram", "Telegram", candy.sky, [0.05, 2, -1], 1.03, "CHANNEL"),
      node("slack", "Slack", candy.peach, [1.65, 1.65, -0.7], 1.03, "CHANNEL"),
      node("hermes", "Hermes", candy.oat, [0.4, -0.6, 0.55], 1.21, "YOUR M2"),
      node("herdr", "Herdr", candy.mint, [2.5, -0.6, 0.35], 1.21, "LOCAL SESSION"),
    ];
  if (id === "local")
    return [
      ...assembledCube(0, false)
        .filter((_, index) => index > 8)
        .map((cube) => ({
          ...cube,
          position: [
            cube.position[0] + 0.8,
            cube.position[1] - 0.35,
            cube.position[2] - 0.6,
          ] as Vec3,
        })),
      node("hermes", "Hermes", candy.oat, [0.8, 0.2, 0.8], 1.1, "M2"),
      node("herdr", "Herdr", candy.mint, [0.8, -1, 0.8], 1.1, "LOCAL"),
      node(
        "request",
        "Message",
        candy.peach,
        [-1.8 + f(0.6) * 0.4, 0.25, 0.5],
        1.04,
        "YOUR CHANNEL",
      ),
    ];
  if (id === "monitor")
    return ["start", "pause", "resume", "stop"].map((label, index) =>
      node(
        label,
        label,
        [candy.mint, candy.lemon, candy.sky, candy.peach][index] ?? candy.mint,
        [-2.9 + index * 1.8, -2.25, 1.1],
        0.79,
        "GATEWAY",
        [0, 0.04, 0],
      ),
    );
  if (id === "trust")
    return [
      node("external", "Hermes", "#dce0d5", [-2.25, 0.45, 0.7], 1.16, "UNSELECTED"),
      node("trusted", "Hermes", candy.oat, [0.6, 0.7, 0.4], 1.3, "CHOSEN + TRUSTED"),
      node("herdr", "Herdr", candy.mint, [2.2, -0.5, 0], 1.22, "BOUND SESSION"),
      node("pane", "Pane", candy.lemon, [0.2, -1.0, 0.2], 0.86, "VERIFIED OWNER"),
    ];
  return [];
}
