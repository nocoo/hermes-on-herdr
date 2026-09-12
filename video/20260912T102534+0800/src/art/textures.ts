import * as THREE from "three";
import type { Language } from "../timeline";

export const palette = {
  ink: "#102029",
  slate: "#24414d",
  brass: "#d6b77a",
  mint: "#a5edc1",
  white: "#eff3e7",
  muted: "#91a9ac",
  amber: "#efb478",
};
export type Textures = Record<string, THREE.Texture>;

function canvas(width = 1200, height = 720) {
  const element = document.createElement("canvas");
  element.width = width;
  element.height = height;
  const context = element.getContext("2d");
  if (!context) throw new Error("2D canvas is required for terminal textures");
  return { element, context };
}

function texture(element: HTMLCanvasElement) {
  const result = new THREE.CanvasTexture(element);
  result.colorSpace = THREE.SRGBColorSpace;
  result.anisotropy = 4;
  return result;
}

function terminal(title: string, rows: [string, string][], foot = "HERMES ON HERDR / DEMO") {
  const { element, context: c } = canvas();
  c.fillStyle = "#10212a";
  c.fillRect(0, 0, 1200, 720);
  const gradient = c.createLinearGradient(0, 0, 1000, 720);
  gradient.addColorStop(0, "#ffffff06");
  gradient.addColorStop(1, "#00000000");
  c.fillStyle = gradient;
  c.fillRect(0, 0, 1200, 720);
  c.strokeStyle = "#d1d8bb27";
  c.lineWidth = 2;
  c.beginPath();
  c.moveTo(0, 98);
  c.lineTo(1200, 98);
  c.stroke();
  ["#b18368", "#bca773", "#8ccaad"].forEach((color, i) => {
    c.fillStyle = color;
    c.beginPath();
    c.arc(45 + i * 30, 49, 7, 0, Math.PI * 2);
    c.fill();
  });
  c.fillStyle = palette.muted;
  c.font = '27px "Geist Mono"';
  c.fillText(title, 160, 59);
  rows.forEach(([text, color], index) => {
    c.font = `${index === 0 ? 42 : 35}px "Geist Mono", "Noto Sans SC"`;
    c.fillStyle = color;
    c.fillText(text, 56, 189 + index * 80);
  });
  c.fillStyle = "#7f9b98";
  c.font = '23px "Geist Mono"';
  c.fillText(foot, 56, 665);
  c.fillStyle = palette.mint;
  c.fillRect(1090, 647, 45, 5);
  return texture(element);
}

function label(title: string, subtitle: string, color = palette.white) {
  const { element, context: c } = canvas(768, 256);
  c.textAlign = "center";
  c.fillStyle = color;
  c.font = '600 76px "Space Grotesk"';
  c.fillText(title, 384, 118);
  c.fillStyle = palette.muted;
  c.font = '43px "Geist Mono"';
  c.fillText(subtitle, 384, 185);
  return texture(element);
}

export function createTextures(lang: Language): Textures {
  const p = palette;
  const result: Textures = {};
  const agents = ["Codex", "Grok", "Pi", "Claude Code"];
  agents.forEach((name, i) => {
    const prompts = [
      "build the idea",
      "review the change",
      "trace the behavior",
      "refine the interface",
    ];
    result[`agent${i}`] = terminal(`${name} / IC ${String(i + 1).padStart(2, "0")}`, [
      [`$ ${prompts[i]}`, p.white],
      ["> understanding context", p.muted],
      ["> working on your intent", p.mint],
      ["  plan  /  build  /  verify", p.brass],
    ]);
    result[`agent-label${i}`] = label(name, "IC");
  });
  result.working = label("WORKING", "", p.mint);
  result.blocked = label("NEEDS INPUT", "", p.amber);
  result.done = label("DONE", "", p.mint);
  result.herdr = label("Herdr", "MANAGER", p.white);
  result.hermes = label("Hermes", "M2", p.brass);
  result.you = label("YOU", "DIRECTION", p.white);
  result.ready = label("READY", "RUNNING IN A REAL PANE", p.mint);
  result.paused = label("PAUSED", "EXPLICIT RESUME REQUIRED", p.amber);
  result.stopped = label("STOPPED", "OWNER SESSION ENDED", p.muted);
  result.manager = terminal("herdr / workspace", [
    ["$ herdr agent list", p.white],
    ["  codex       working", p.mint],
    ["  grok        done", p.mint],
    ["  pi          working", p.mint],
    ["  claude      blocked", p.amber],
  ]);
  result.control = terminal(
    "hermes / herdr-control",
    [
      ["$ herdr agent list", p.white],
      ["$ herdr pane read w1:p1", p.white],
      ["$ herdr agent prompt builder", p.white],
      ['  "Continue with the next step."', p.mint],
      ["> inspect / coordinate / follow up", p.brass],
    ],
    "ILLUSTRATIVE SESSION / FULL HERDR CONTROL",
  );
  result.lifecycle = terminal(
    "hermes-on-herdr / lifecycle",
    [
      ["  start   ->  READY", p.mint],
      ["  pause   ->  PAUSED", p.amber],
      ["  owner startup  ->  PAUSED", p.amber],
      ["  resume  ->  READY", p.mint],
      ["  owner exit  ->  STOPPED", p.muted],
    ],
    "PERSISTED INTENT / DIAGRAM",
  );
  result.clock = (() => {
    const { element, context: c } = canvas(1200, 720);
    c.fillStyle = "#15282c";
    c.fillRect(0, 0, 1200, 720);
    c.textAlign = "center";
    c.fillStyle = p.brass;
    c.font = '32px "Geist Mono"';
    c.fillText("FRIDAY", 600, 170);
    c.fillStyle = p.white;
    c.font = '500 232px "Space Grotesk"';
    c.fillText("18:00", 600, 445);
    c.fillStyle = p.muted;
    c.font = '27px "Geist Mono"';
    c.fillText("YOUR WEEKEND IS CALLING", 600, 586);
    return texture(element);
  })();
  result.message = (() => {
    const { element, context: c } = canvas(1000, 650);
    c.fillStyle = "#132832";
    c.fillRect(0, 0, 1000, 650);
    c.fillStyle = p.brass;
    c.font = '29px "Geist Mono"';
    c.fillText("YOU  <->  HERMES", 46, 72);
    c.fillStyle = "#2e4848";
    c.beginPath();
    c.roundRect(160, 132, 790, 122, 28);
    c.fill();
    c.fillStyle = p.white;
    c.font = '36px "Space Grotesk", "Noto Sans SC"';
    c.fillText(lang === "zh" ? "现在进展如何？" : "How is the work going?", 203, 208);
    c.fillStyle = "#1c3b3b";
    c.beginPath();
    c.roundRect(42, 305, 848, 205, 28);
    c.fill();
    c.fillStyle = p.mint;
    c.font = '30px "Space Grotesk", "Noto Sans SC"';
    c.fillText(lang === "zh" ? "先检查 Agent 状态，" : "I can check the agents,", 82, 377);
    c.fillText(
      lang === "zh" ? "再跟进需要你处理的事项。" : "then follow up on what needs you.",
      82,
      435,
    );
    c.fillStyle = p.muted;
    c.font = '22px "Geist Mono"';
    c.fillText("CONFIGURED PLATFORM / ILLUSTRATIVE EXCHANGE", 43, 594);
    return texture(element);
  })();
  return result;
}
