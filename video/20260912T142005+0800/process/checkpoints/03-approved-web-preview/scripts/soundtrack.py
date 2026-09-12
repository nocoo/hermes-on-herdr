"""Compose an original bright score and master the measured English narration."""

import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
TIMING = json.loads((ROOT / "src/timing.json").read_text())
assert TIMING["measured"]
SR = 48000
SECONDS = TIMING["durationInFrames"] / TIMING["fps"]
COUNT = round(SECONDS * SR)
score = np.zeros((COUNT, 2), dtype=np.float32)
rng = np.random.default_rng(20260912)


def add(at, signal, pan=0):
    offset = round(at * SR)
    if offset < 0:
        signal = signal[-offset:]
        offset = 0
    count = min(len(signal), COUNT - offset)
    if count <= 0:
        return
    score[offset:offset + count, 0] += signal[:count] * math.sqrt((1 - pan) / 2)
    score[offset:offset + count, 1] += signal[:count] * math.sqrt((1 + pan) / 2)


def note(at, midi, duration, gain, kind="felt", pan=0):
    t = np.arange(round(duration * SR), dtype=np.float32) / SR
    hz = 440 * 2 ** ((midi - 69) / 12)
    if kind == "air":
        waveform = np.sin(2 * np.pi * hz * t) + 0.11 * np.sin(2 * np.pi * hz * 2.001 * t)
        envelope = np.minimum(t / 1.0, 1) * np.minimum((duration - t) / 1.4, 1)
    elif kind == "bass":
        waveform = np.sin(2 * np.pi * hz * t)
        envelope = (1 - np.exp(-t * 20)) * np.exp(-t * 1.8) * np.clip((duration - t) / 0.2, 0, 1)
    else:
        waveform = np.sin(2 * np.pi * hz * t) + 0.32 * np.sin(2 * np.pi * hz * 2 * t) * np.exp(-t * 7)
        waveform += 0.09 * np.sin(2 * np.pi * hz * 3.998 * t) * np.exp(-t * 11)
        envelope = (1 - np.exp(-t * 200)) * np.exp(-t / 0.62) * np.clip((duration - t) / 0.18, 0, 1)
    wave = waveform * envelope * gain
    add(at, wave, pan)
    if kind == "felt":
        add(at + 0.24, wave * 0.17, -pan)
        add(at + 0.43, wave * 0.07, pan)


BEAT = 60 / 108
# D major 9, G major 9, B minor 7, A suspended: original voicings, no samples.
chords = [(38, 57, 61, 66, 69), (43, 59, 62, 66, 69),
          (35, 57, 62, 66, 69), (45, 57, 62, 64, 71)]
for bar, at in enumerate(np.arange(0, SECONDS, BEAT * 8)):
    chord = chords[bar % len(chords)]
    for i, pitch in enumerate(chord[1:]):
        note(at, pitch, BEAT * 8 + 1.2, 0.0105, "air", (i - 1.5) * 0.29)
    for step in (0, 4):
        note(at + step * BEAT, chord[0], 2.3, 0.027, "bass")
    for step, index in ((0.5, 2), (2.5, 3), (4, 4), (6.5, 3)):
        note(at + step * BEAT, chord[index] + 12, 2, 0.030, "felt", -0.32 if step < 4 else 0.32)

for shot in TIMING["scenes"][1:]:
    at = shot["start"] / 30
    t = np.arange(round(0.42 * SR)) / SR
    noise = np.convolve(rng.standard_normal(len(t)), np.ones(90) / 90, mode="same")
    add(at - 0.19, noise * np.sin(np.pi * t / 0.42) ** 2 * 0.035, -0.2)
    note(at + 0.1, 85, 1.2, 0.032, pan=0.2)

weekend = next(s["start"] / 30 for s in TIMING["scenes"] if s["id"] == "weekend")
for offset in (2.6, 4.35, 6.0):
    t = np.arange(round(0.13 * SR)) / SR
    click = rng.standard_normal(len(t)) * np.exp(-t * 78) * (1 - np.exp(-t * 900))
    add(weekend + offset, click * 0.017, -0.15 if offset < 4 else 0.15)
    note(weekend + offset, 78, 0.8, 0.036, pan=0.1)

outro = TIMING["scenes"][-1]["start"] / 30
for i, pitch in enumerate((74, 81, 85)):
    note(outro + 0.12 + i * 0.20, pitch, 2.6, 0.047, pan=(i - 1) * 0.27)
time = np.arange(COUNT, dtype=np.float32) / SR
score *= (np.minimum((time + 0.03) / 0.45, 1) * np.clip((SECONDS - time) / 1.2, 0, 1))[:, None]
sf.write(ROOT / "public/audio/music.wav", score, SR, subtype="PCM_16")

voice = np.zeros(COUNT, dtype=np.float32)
duck = np.ones(COUNT, dtype=np.float32)
for clip in TIMING["audio"]:
    source = ROOT / "public" / clip["file"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == clip["sha256"]
    wave, sample_rate = sf.read(source, dtype="float32")
    wave = resample_poly(wave, SR // math.gcd(sample_rate, SR), sample_rate // math.gcd(sample_rate, SR))
    offset = round(clip["fromFrame"] / 30 * SR)
    end = offset + len(wave)
    assert end <= COUNT, "Never truncate narration to fit a visual"
    voice[offset:end] += wave
    envelope = np.minimum(np.clip((time - offset / SR + 0.20) / 0.25, 0, 1),
                          np.clip((end / SR + 0.28 - time) / 0.35, 0, 1))
    duck = np.minimum(duck, 1 - 0.72 * envelope)

cache = ROOT / ".cache/audio"
cache.mkdir(parents=True, exist_ok=True)
sf.write(cache / "voice.wav", voice, SR, subtype="PCM_16")
mix = voice[:, None] + score * duck[:, None]
assert np.max(np.abs(mix)) < 0.99, "Unmastered mix clips"
raw = cache / "mix.wav"
sf.write(raw, mix, SR, subtype="PCM_24")
analysis = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af",
    "loudnorm=I=-16:TP=-1.8:LRA=8:print_format=json", "-f", "null", "-"],
    capture_output=True, text=True, check=True)
measured, _ = json.JSONDecoder().raw_decode(analysis.stderr[analysis.stderr.rfind("{"):])
filter_text = ("loudnorm=I=-16:TP=-1.8:LRA=8:linear=true:print_format=json:"
    f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
    f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
    f"offset={measured['target_offset']}")
output = ROOT / "public/audio/mix-en.m4a"
master = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", str(raw), "-af", filter_text,
    "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-movflags", "+faststart", str(output)],
    capture_output=True, text=True, check=True)
mastered, _ = json.JSONDecoder().raw_decode(master.stderr[master.stderr.rfind("{"):])
report = {"analysis": measured, "mastering": mastered, "seconds": SECONDS, "sampleRate": SR,
          "channels": 2, "voiceClips": len(TIMING["audio"]), "ducking": "Music reduced 72% around speech",
          "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
(ROOT / "verification/audio-mastering.json").write_text(json.dumps(report, indent=2) + "\n")
(ROOT / "public/audio/music.json").write_text(json.dumps({
    "title": "Pieces in Place", "original": True, "source": "scripts/soundtrack.py", "bpm": 108,
    "harmony": "D major 9 / G major 9 / B minor 7 / A suspended", "seed": 20260912,
    "method": "Deterministic additive synthesis, felt-like plucks, sine bass, air pads, filtered noise and cube clicks",
    "rights": "Original score created for the repository owner; no third-party recording or sample",
    "sampleRate": SR, "seconds": SECONDS,
    "sha256": hashlib.sha256((ROOT / "public/audio/music.wav").read_bytes()).hexdigest(),
}, indent=2) + "\n")
print(json.dumps(report, indent=2))
