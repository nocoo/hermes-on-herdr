import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { PDFDocument } from "pdf-lib";
import PptxGenJS from "pptxgenjs";
import story from "../src/story.json";
import timing from "../src/timing.json";

const root = path.resolve(import.meta.dir, "..");
const out = path.join(root, "public/slides");
await mkdir(out, { recursive: true });
const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Hexly AI";
pptx.title = "Context is control · hermes on herdr";
pptx.subject = "English film keyframes with editable native speaker notes";
const pdf = await PDFDocument.create();
pdf.setTitle(pptx.title);
pdf.setAuthor("Hexly AI");
const pages = [];
const notes = ["# Context is control · English speaker notes", ""];
for (const [index, scene] of story.scenes.entries()) {
  const file = `review/stills/${String(index).padStart(2, "0")}-${scene.id}.png`;
  const bytes = await readFile(path.join(root, "public", file));
  const image = await pdf.embedPng(bytes);
  if (image.width !== 1920 || image.height !== 1080) throw new Error("Non-native slide frame");
  pdf.addPage([960, 540]).drawImage(image, { x: 0, y: 0, width: 960, height: 540 });
  const slide = pptx.addSlide();
  slide.addImage({
    path: path.join(root, "public", file),
    x: 0,
    y: 0,
    w: 13.333333,
    h: 7.5,
    altText: scene.title.replaceAll("\n", " "),
  });
  const qualification = "qualifications" in scene ? scene.qualifications?.join(" ") : "";
  const note = [scene.narration.join(" "), qualification, `Source: ${story.repository}`]
    .filter(Boolean)
    .join("\n\n");
  slide.addNotes(note);
  pages.push({
    scene: scene.id,
    frame: timing.scenes[index]?.keyframe,
    file,
    imageSha256: createHash("sha256").update(bytes).digest("hex"),
    notes: note,
  });
  notes.push(
    `## ${String(index + 1).padStart(2, "0")} · ${scene.title.replaceAll("\n", " ")}`,
    "",
    note,
    "",
  );
}
await pptx.writeFile({ fileName: path.join(out, "hermes-context-en.pptx"), compression: true });
await writeFile(path.join(out, "hermes-context-en.pdf"), await pdf.save());
await writeFile(path.join(out, "speaker-notes-en.md"), `${notes.join("\n")}\n`);
await writeFile(
  path.join(out, "slides.json"),
  `${JSON.stringify({ pages, format: "Native 16:9 image pages with editable speaker notes", kitRevision: "e1b220a7643e8275134b0bff0a11d703c047abbe" }, null, 2)}\n`,
);
const odp = spawnSync(path.join(root, ".venv/bin/python"), [path.join(root, "scripts/odp.py")], {
  encoding: "utf8",
});
if (odp.status !== 0) throw new Error(odp.stderr || "ODP export failed");
console.log(odp.stdout.trim());
console.log(`Exported ${pages.length} actual chapter frames to PDF/PPTX/ODP`);
