"""Compose an original electronic score; mix and master both voice editions."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
TIMING = json.loads((ROOT / 'src/generated/timing.json').read_text())
SR = 48000
SECONDS = TIMING['durationInFrames'] / TIMING['fps']
COUNT = round(SECONDS * SR)
score = np.zeros((COUNT, 2), dtype=np.float32)
rng = np.random.default_rng(20260912)


def add(start, signal, pan=0):
    offset = round(start * SR)
    if offset < 0:
        signal = signal[-offset:]
        offset = 0
    count = min(len(signal), COUNT-offset)
    if count <= 0:
        return
    score[offset:offset+count, 0] += signal[:count] * math.sqrt((1-pan)/2)
    score[offset:offset+count, 1] += signal[:count] * math.sqrt((1+pan)/2)


def tone(start, midi, length, gain, kind='pad', pan=0):
    t = np.arange(round(length * SR), dtype=np.float32) / SR
    frequency = 440 * 2 ** ((midi-69)/12)
    if kind == 'pad':
        signal = np.sin(2*np.pi*frequency*t) + .22*np.sin(2*np.pi*frequency*1.0018*t)
        envelope = np.minimum(t/.85, 1) * np.clip((length-t)/1.35, 0, 1)
    elif kind == 'bass':
        signal = np.sin(2*np.pi*frequency*t) + .09*np.sin(2*np.pi*frequency*2*t)
        envelope = (1-np.exp(-t*18))*np.exp(-t/1.2)*np.minimum((length-t)/.25, 1)
    else:
        signal = np.sin(2*np.pi*frequency*t) + .16*np.sin(2*np.pi*frequency*2.002*t)*np.exp(-t*4)
        envelope = (1-np.exp(-t*85))*np.exp(-t/.68)*np.minimum((length-t)/.12, 1)
    sound = signal * envelope * gain
    add(start, sound, pan)
    if kind == 'bell':
        add(start+.24, sound*.2, -pan)
        add(start+.48, sound*.09, pan)


BEAT = 60/96
chords = [(40, 59, 64, 67, 71), (36, 55, 60, 64, 67), (43, 62, 67, 71, 74), (38, 57, 62, 66, 69)]
for bar, start in enumerate(np.arange(0, SECONDS, BEAT*8)):
    chord = chords[bar % len(chords)]
    for i, note in enumerate(chord[1:]):
        tone(start, note, BEAT*8+1.2, .016, pan=(i-1.5)*.24)
    for step in [0, 4]:
        tone(start+step*BEAT, chord[0], 3.0, .028, 'bass')
    for step, note in zip([1, 3.5, 6], [chord[2]+12, chord[4], chord[3]+12]):
        tone(start+step*BEAT, note, 2, .029, 'bell', -.3 if step<4 else .3)
for i, note in enumerate([76, 83, 78]):
    tone(.05+i*.29, note, 2.2, .065, 'bell', (i-1)*.3)
for shot in TIMING['scenes'][1:]:
    start = shot['start']/TIMING['fps']
    t = np.arange(round(1.0*SR))/SR
    noise = np.convolve(rng.standard_normal(len(t)), np.ones(35)/35, mode='same')
    add(start-.6, noise*np.sin(np.pi*t)**2*.021, -.25)
    tone(start+.08, 83, 2, .035, 'bell', .25)
closing = TIMING['scenes'][-1]['voiceEnd']/TIMING['fps']
for i, note in enumerate([55, 62, 67, 71]):
    tone(closing-.15+i*.19, note, 4.0, .036, 'pad', (i-1.5)*.2)
time = np.arange(COUNT)/SR
score *= (np.minimum((time+.025)/.4, 1)*np.clip((SECONDS-time)/1.6, 0, 1))[:, None]
sf.write(ROOT/'public/audio/music.wav', score, SR, subtype='PCM_16')
music_record = dict(title='The Weekend Protocol', original=True, source='scripts/soundtrack.py',
                    bpm=96, harmony='E minor / G major', sampleRate=SR, channels=2,
                    seconds=SECONDS, samples=COUNT, seed=20260912,
                    method='Oscillator pads, bass, stereo bell delay, filtered seeded noise; no stock samples',
                    rights='Original production for the repository owner. No third-party audio recordings.',
                    sha256=hashlib.sha256((ROOT/'public/audio/music.wav').read_bytes()).hexdigest())
(ROOT/'public/audio/music.json').write_text(json.dumps(music_record, indent=2)+'\n')
cache = ROOT/'.cache/audio'
cache.mkdir(parents=True, exist_ok=True)
reports = {}
for lang in ['zh', 'en']:
    voice = np.zeros(COUNT, dtype=np.float32)
    duck = np.ones(COUNT, dtype=np.float32)
    for clip in TIMING['audio'][lang]:
        waveform, sample_rate = sf.read(ROOT/'public'/clip['file'], dtype='float32')
        if sample_rate != SR:
            waveform = resample_poly(waveform, SR//math.gcd(sample_rate, SR), sample_rate//math.gcd(sample_rate, SR))
        offset = round(clip['fromFrame']/TIMING['fps']*SR)
        end = offset+len(waveform)
        if end > COUNT:
            raise ValueError('Speech must never be cut to the visual duration')
        voice[offset:end] += waveform
        begin_sec, end_sec = offset/SR, end/SR
        envelope = np.minimum(np.clip((time-begin_sec+.18)/.22, 0, 1), np.clip((end_sec+.28-time)/.32, 0, 1))
        duck = np.minimum(duck, 1-.66*envelope)
    sf.write(cache/f'voice-{lang}.wav', voice, SR, subtype='PCM_16')
    mixed = voice[:, None]*np.ones((1, 2), dtype=np.float32) + score*duck[:, None]
    if np.max(np.abs(mixed)) >= .99:
        raise ValueError('Mix clips before mastering')
    raw = cache/f'mix-{lang}.wav'
    sf.write(raw, mixed, SR, subtype='PCM_24')
    analysis = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(raw), '-af',
        'loudnorm=I=-16:TP=-1.8:LRA=9:print_format=json', '-f', 'null', '-'], capture_output=True, text=True, check=True)
    stats, _ = json.JSONDecoder().raw_decode(analysis.stderr[analysis.stderr.rfind('{'):])
    master = ('loudnorm=I=-16:TP=-1.8:LRA=9:linear=true:print_format=json:'
              f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
              f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
              f"offset={stats['target_offset']}")
    output = ROOT/f'public/audio/mix-{lang}.m4a'
    mastered = subprocess.run(['ffmpeg', '-hide_banner', '-y', '-i', str(raw), '-af', master,
        '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', '-movflags', '+faststart', str(output)],
        capture_output=True, text=True, check=True)
    final_stats, _ = json.JSONDecoder().raw_decode(mastered.stderr[mastered.stderr.rfind('{'):])
    reports[lang] = dict(analysis=stats, mastering=final_stats, samples=COUNT,
                        seconds=SECONDS, voiceClips=len(TIMING['audio'][lang]),
                        sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    print(f'{lang}: mastered {SECONDS:.2f}s / {final_stats["output_i"]} LUFS', flush=True)
(ROOT/'verification/audio-mastering.json').write_text(json.dumps(reports, indent=2)+'\n')
