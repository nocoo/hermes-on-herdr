"""Generate original English Kokoro speech and derive the film from measured WAVs."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
STORY = json.loads((ROOT / "src/story.json").read_text())
SOURCES = json.loads((ROOT / "research/voice-sources.lock.json").read_text())
VOICE = STORY["voice"]
SR = 24000
FPS = STORY["fps"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spoken(text):
    # Performance spellings only; product spelling stays intact in visible copy.
    for name, pronunciation in (("Herdr", "Herder"), ("Hexly AI", "Hex lee A I"),
                                ("M2", "M two"), ("TUI", "T U I"),
                                ("SSH", "S S H"), ("VPN", "V P N")):
        text = text.replace(name, pronunciation)
    return text


def signature(text):
    value = {"text": text, "spoken": spoken(text), "voice": VOICE,
             "padding": "80ms/160ms", "rms": 0.10, "version": 1}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def generate(limit=None):
    import torch
    from kokoro import KModel, KPipeline

    assert SOURCES["revision"] == VOICE["revision"]
    cache = ROOT / ".cache/tts"
    for entry in SOURCES["files"]:
        target = cache / entry["file"]
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".part")
            subprocess.run(["curl", "-fL", "--retry", "3", "--connect-timeout", "20",
                            "--max-time", "600", entry["url"], "-o", str(temporary)], check=True)
            assert sha(temporary) == entry["sha256"], entry["file"]
            temporary.replace(target)
        assert sha(target) == entry["sha256"], entry["file"]
    torch.set_num_threads(min(6, os.cpu_count() or 2))
    torch.manual_seed(20260912)
    model = KModel(repo_id=VOICE["repo"], config=str(cache / "config.json"),
                   model=str(cache / "kokoro-v1_0.pth")).to("cpu").eval()
    pipeline = KPipeline(lang_code="a", repo_id=VOICE["repo"], model=model)
    pack = str(cache / f"voices/{VOICE['voice']}.pt")
    count = 0
    for scene in STORY["scenes"]:
        for index, text in enumerate(scene["narration"]):
            target = ROOT / f"public/audio/en/{scene['id']}-{index + 1:02}.wav"
            record_path = target.with_suffix(".json")
            sig = signature(text)
            if target.exists() and record_path.exists():
                previous = json.loads(record_path.read_text())
                if previous["signature"] == sig and previous["sha256"] == sha(target):
                    continue
            if limit is not None and count >= limit:
                return
            pieces = list(pipeline(spoken(text), voice=pack, speed=VOICE["speed"], split_pattern=r"\n+"))
            assert pieces and all(p.audio is not None for p in pieces), "Missing speech"
            wave = np.concatenate([p.audio.numpy() for p in pieces])
            assert np.isfinite(wave).all(), "Non-finite audio"
            audible = np.flatnonzero(np.abs(wave) > 0.0008)
            assert len(audible), "Silent narration is not a fallback"
            first = max(0, int(audible[0]) - round(SR * 0.08))
            last = min(len(wave), int(audible[-1]) + round(SR * 0.16))
            wave = wave[first:last].copy()
            rms = float(np.sqrt(np.mean(wave**2)))
            gain = min(0.10 / max(rms, 1e-8), 0.85 / float(np.max(np.abs(wave))))
            wave *= gain
            edge = round(SR * 0.004)
            wave[:edge] *= np.linspace(0, 1, edge)
            wave[-edge:] *= np.linspace(1, 0, edge)
            sf.write(target, wave, SR, subtype="PCM_16")
            record = {"text": text, "spoken": spoken(text), "signature": sig, "voice": VOICE,
                      "generatedAt": datetime.now(timezone.utc).isoformat(), "sampleRate": SR,
                      "samples": len(wave), "seconds": len(wave) / SR, "sha256": sha(target),
                      "gain": gain, "sourceTrimSamples": [first, last],
                      "phonemes": [p.phonemes for p in pieces],
                      "provenance": "research/voice-sources.lock.json",
                      "attribution": "Kokoro by hexgrad, Apache-2.0. Synthetic narration; no cloned or scraped human voice."}
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            count += 1
            print(f"{target.stem}: {record['seconds']:.2f}s", flush=True)


def stamp(seconds, dot=False):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{'.' if dot else ','}{ms:03}"


def timeline():
    result = {"fps": FPS, "width": STORY["width"], "height": STORY["height"],
              "storySha256": sha(ROOT / "src/story.json"), "measured": True,
              "scenes": [], "audio": [], "captions": []}
    start = 0
    for index, scene in enumerate(STORY["scenes"]):
        lead = round(scene.get("voiceLeadSeconds", 0.6) * FPS)
        gap = round(0.25 * FPS)
        cursor = lead
        for sentence, text in enumerate(scene["narration"]):
            file = f"audio/en/{scene['id']}-{sentence + 1:02}.wav"
            target = ROOT / "public" / file
            record = json.loads(target.with_suffix(".json").read_text())
            assert record["signature"] == signature(text), f"Stale speech: {file}"
            assert record["sha256"] == sha(target), file
            duration = math.ceil(record["seconds"] * FPS)
            result["audio"].append({"scene": scene["id"], "file": file, "text": text,
                                    "fromFrame": start + cursor, "durationFrames": duration,
                                    "seconds": record["seconds"], "sha256": record["sha256"]})
            result["captions"].append({"scene": scene["id"], "text": text,
                                      "start": (start + cursor) / FPS,
                                      "end": (start + cursor + duration) / FPS})
            cursor += duration + gap
        voice_end = cursor - gap
        tail = round((1.15 if scene["id"] == "weekend" else 0.8) * FPS)
        duration = math.ceil(max(scene["minSeconds"] * FPS, voice_end + tail) / 15) * 15
        keyframe = start + min(round(duration * 0.57), duration - 24)
        if scene["id"] == "outro":
            keyframe = start + duration - 30
        result["scenes"].append({"id": scene["id"], "index": index, "start": start,
                                  "duration": duration, "keyframe": keyframe,
                                  "voiceStart": start + lead, "voiceEnd": start + voice_end})
        start += duration
    result["durationInFrames"] = start
    (ROOT / "src/timing.json").write_text(json.dumps(result, indent=2) + "\n")
    subtitles = result["captions"]
    srt = "\n\n".join(f"{i + 1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i, c in enumerate(subtitles)) + "\n"
    vtt = "WEBVTT\n\n" + "\n\n".join(f"{stamp(c['start'], True)} --> {stamp(c['end'], True)}\n{c['text']}" for c in subtitles) + "\n"
    (ROOT / "public/audio/narration-en.srt").write_text(srt)
    (ROOT / "public/audio/narration-en.vtt").write_text(vtt)
    notes = "# English narration\n\n" + "\n\n".join("## " + s["id"] + "\n\n" + "\n\n".join(s["narration"]) for s in STORY["scenes"])
    (ROOT / "public/audio/narration-en.md").write_text(notes + "\n")
    print(f"Measured timeline: {start} frames / {start / FPS:.2f}s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timing-only", action="store_true")
    args = parser.parse_args()
    if not args.timing_only:
        generate(args.limit)
    if args.limit is None:
        timeline()
