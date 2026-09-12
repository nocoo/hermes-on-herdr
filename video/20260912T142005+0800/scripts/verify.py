"""Verify the actual delivered MP4, its soundtrack, captions, frames and slide exports."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from PIL import Image, ImageDraw
from pypdf import PdfReader
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
STORY = json.loads((ROOT / "src/story.json").read_text())
TIMING = json.loads((ROOT / "src/timing.json").read_text())
OUT = ROOT / "verification/final"
OUT.mkdir(parents=True, exist_ok=True)
VIDEO = ROOT / "public/review" / STORY["filename"]
FPS = TIMING["fps"]
SECONDS = TIMING["durationInFrames"] / FPS


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def command(args, log):
    result = subprocess.run(args, capture_output=True, text=True)
    (OUT / log).write_text(result.stderr + result.stdout)
    if result.returncode:
        raise RuntimeError(f"Command failed; see verification/final/{log}")
    return result


def cues(text):
    result = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        interval = re.fullmatch(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
        assert interval, block
        h, m, s, ms, h2, m2, s2, ms2 = map(int, interval.groups())
        result.append({"start": h * 3600 + m * 60 + s + ms / 1000,
                       "end": h2 * 3600 + m2 * 60 + s2 + ms2 / 1000,
                       "text": " ".join(lines[2:])})
    return result


assert VIDEO.is_file(), "Render the final MP4 first"
assert TIMING["storySha256"] == sha(ROOT / "src/story.json")
probe = command(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(VIDEO)], "ffprobe.json")
metadata = json.loads(probe.stdout)
v = next(s for s in metadata["streams"] if s["codec_type"] == "video")
a = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
assert all(s["codec_type"] != "subtitle" for s in metadata["streams"]), "Avoid duplicated burned and soft subtitles"
assert (v["codec_name"], v["width"], v["height"]) == ("h264", 1920, 1080)
assert v["pix_fmt"] in ("yuv420p", "yuvj420p")
assert v["avg_frame_rate"] == f"{FPS}/1"
assert int(v["nb_frames"]) == TIMING["durationInFrames"]
assert abs(float(v["duration"]) - SECONDS) < 1 / FPS
assert a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and a["channels"] == 2
assert abs(float(a["duration"]) - SECONDS) < 0.05
assert a["tags"]["language"] == "eng"
atoms = []
with VIDEO.open("rb") as file:
    while header := file.read(8):
        size, kind = struct.unpack(">I4s", header)
        atoms.append(kind.decode("ascii"))
        consumed = 8
        if size == 1:
            size = struct.unpack(">Q", file.read(8))[0]
            consumed = 16
        if size == 0:
            break
        assert size >= consumed
        file.seek(size - consumed, 1)
assert atoms.index("moov") < atoms.index("mdat"), "MP4 must support faststart"

command(["ffmpeg", "-hide_banner", "-nostats", "-v", "warning", "-xerror", "-i", str(VIDEO),
         "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], "full-decode.log")
scan = command(["ffmpeg", "-hide_banner", "-nostats", "-i", str(VIDEO),
                "-vf", "blackdetect=d=0.03:pix_th=0.10:pic_th=0.98",
                "-af", "silencedetect=noise=-50dB:d=0.35", "-f", "null", "-"], "black-silence.log")
black = re.findall(r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)", scan.stderr)
silence = re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", scan.stderr)
assert not black, f"Unexpected black interval: {black}"
assert not silence, f"Unexpected silent interval at -50 dB for >= 0.35 s: {silence}"
loud = command(["ffmpeg", "-hide_banner", "-nostats", "-i", str(VIDEO), "-vn",
                "-af", "loudnorm=I=-16:TP=-1.8:LRA=8:print_format=json", "-f", "null", "-"], "loudness.log")
loudness, _ = json.JSONDecoder().raw_decode(loud.stderr[loud.stderr.rfind("{"):])
assert abs(float(loudness["input_i"]) + 16) < 1
assert float(loudness["input_tp"]) <= -1

audio = []
for clip in TIMING["audio"]:
    source = ROOT / "public" / clip["file"]
    record = json.loads(source.with_suffix(".json").read_text())
    assert sha(source) == clip["sha256"] == record["sha256"]
    wave, rate = sf.read(source)
    assert np.isfinite(wave).all() and len(wave) == record["samples"]
    assert np.max(np.abs(wave)) < 1 and np.sqrt(np.mean(wave ** 2)) > 0.03
    end = clip["fromFrame"] / FPS + len(wave) / rate
    shot = next(shot for shot in TIMING["scenes"] if shot["id"] == clip["scene"])
    assert clip["fromFrame"] >= shot["start"]
    assert end <= (shot["start"] + shot["duration"]) / FPS - 0.6
    audio.append({"file": clip["file"], "sha256": clip["sha256"], "seconds": len(wave) / rate})

expected = [c for c in TIMING["captions"] if c["scene"] not in ("intro", "outro")]
sidecar = cues((ROOT / "public/audio/narration-en.srt").read_text())
assert len(sidecar) == len(expected)
for received, planned in zip(sidecar, expected):
    assert received["text"] == planned["text"]
    assert abs(received["start"] - planned["start"]) < 0.002
    assert abs(received["end"] - planned["end"]) < 0.002

samples = [{"name": shot["id"], "frame": shot["keyframe"]} for shot in TIMING["scenes"]]
for shot in (TIMING["scenes"][0], TIMING["scenes"][-1]):
    samples.append({"name": f"{shot['id']}-during-narration", "frame": shot["voiceStart"] + 15})
for name in ("context", "bind", "outro"):
    shot = next(s for s in TIMING["scenes"] if s["id"] == name)
    samples.append({"name": f"{name}-transition", "frame": shot["start"] + 6})
samples.append({"name": "final-frame", "frame": TIMING["durationInFrames"] - 1})
frames = OUT / "frames"
frames.mkdir(exist_ok=True)
selected = sorted({item["frame"] for item in samples})
selection = "+".join(f"eq(n\\,{frame})" for frame in selected)
command(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(VIDEO), "-vf",
         f"select={selection}", "-fps_mode", "vfr", str(frames / "decoded-%02d.png")], "extract-frames.log")
sheet = Image.new("RGB", (2008, ((len(samples) + 2) // 3) * 404 + 24), "#f0f0e9")
draw = ImageDraw.Draw(sheet)
for i, item in enumerate(samples):
    target = frames / f"decoded-{selected.index(item['frame']) + 1:02}.png"
    with Image.open(target) as image:
        assert image.size == (1920, 1080)
        if "during-narration" in item["name"]:
            band = np.array(image.convert("RGB"))[940:1060, 130:1790]
            assert not np.any(np.mean(band, axis=2) < 150), "Bookend subtitle band must be empty"
        x, y = (i % 3) * 660 + 24, (i // 3) * 404 + 24
        sheet.paste(image.resize((640, 360), Image.Resampling.LANCZOS), (x, y))
        draw.text((x, y + 366), f"{item['name']} / frame {item['frame']} / {item['frame']/FPS:.2f}s", fill="#30372e")
    item.update({"file": str(target.relative_to(ROOT)), "sha256": sha(target)})
sheet.save(OUT / "contact-sheet.jpg", quality=94)

pages = json.loads((ROOT / "public/slides/slides.json").read_text())["pages"]
assert len(pages) == len(STORY["scenes"]) == 11
assert len(PdfReader(ROOT / "public/slides/hermes-context-en.pdf").pages) == 11
with zipfile.ZipFile(ROOT / "public/slides/hermes-context-en.pptx") as pptx:
    notes = [n for n in pptx.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
    assert len(notes) == 11
    for i, page in enumerate(pages, 1):
        xml = ET.fromstring(pptx.read(f"ppt/notesSlides/notesSlide{i}.xml"))
        words = " ".join(xml.itertext())
        assert " ".join(page["notes"].split()) in " ".join(words.split())
        assert sha(ROOT / "public" / page["file"]) == page["imageSha256"]
with zipfile.ZipFile(ROOT / "public/slides/hermes-context-en.odp") as odp:
    xml = ET.fromstring(odp.read("content.xml"))
    ns = {"draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
          "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"}
    slide_pages = xml.findall(".//draw:page", ns)
    assert len(slide_pages) == 11
    for page, expected_page in zip(slide_pages, pages):
        notes = page.find("presentation:notes", ns)
        assert notes is not None and expected_page["notes"] in "".join(notes.itertext())

protected = json.loads((REPO / "video/20260912T135851+0800/research/local-sources.json").read_text())["protectedMedia"]
for previous in protected:
    assert sha(REPO / previous["file"]) == previous["sha256"], "Historical video changed"
report = {"checkedAt": datetime.now(timezone.utc).isoformat(), "status": "passed",
          "file": str(VIDEO.relative_to(ROOT)), "sha256": sha(VIDEO), "bytes": VIDEO.stat().st_size,
          "width": v["width"], "height": v["height"], "fps": FPS, "frames": int(v["nb_frames"]),
          "seconds": SECONDS, "videoCodec": v["codec_name"], "pixelFormat": v["pix_fmt"],
          "audioCodec": a["codec_name"], "sampleRate": int(a["sample_rate"]), "channels": a["channels"],
          "faststart": True, "fullDecode": "passed", "blackIntervals": black, "silenceIntervals": silence,
          "silenceThreshold": "-50 dB for 0.35 seconds", "loudness": loudness,
          "subtitleCues": len(sidecar), "embeddedSubtitles": False,
          "bookendSubtitles": "absent in both pixels and sidecar captions",
          "audioClips": audio, "samples": samples, "slidePages": len(pages), "protectedMedia": protected}
(OUT / "media.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("status", "file", "bytes", "seconds", "frames", "sha256", "subtitleCues")}, indent=2))
