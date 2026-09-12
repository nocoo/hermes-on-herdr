"""Generate licensed, local Kokoro speech and one measured bilingual timeline.

No recordings, reference voices, cloud credentials, or unlicensed speech APIs.
The pinned models are download caches; generated WAVs and provenance are assets.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
STORY = json.loads((ROOT / 'src/story.json').read_text())
SR = 24000
FPS = STORY['fps']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spoken(text, lang):
    # Written branding is unchanged. These expansions only guide pronunciation.
    text = text.replace('Herdr', 'Herder').replace('Hexly AI', 'Hex lee A I')
    if lang == 'zh':
        text = text.replace('M2', 'M 二').replace('IC', '独立贡献者')
        text = text.replace('monitor TUI', '终端监控面板')
    return text


def signature(text, lang):
    payload = dict(text=text, spoken=spoken(text, lang), language=lang,
                   model=STORY['voices'][lang], engine='kokoro-0.9.4',
                   mastering='rms-20dB-peak0.85', padding='80ms/140ms', version=1)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def download(url, target):
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + '.part')
        subprocess.run(['curl', '-fL', '--retry', '4', '--retry-all-errors',
                        '--connect-timeout', '20', '--max-time', '600',
                        url, '-o', str(temporary)], check=True)
        temporary.replace(target)
    return str(target)


def generate(lang, limit=None):
    import torch
    from kokoro import KModel, KPipeline

    torch.set_num_threads(min(6, os.cpu_count() or 2))
    torch.manual_seed(20260912)
    voice = STORY['voices'][lang]
    cache = ROOT / '.cache' / 'tts' / voice['revision']
    model_file = 'kokoro-v1_1-zh.pth' if lang == 'zh' else 'kokoro-v1_0.pth'
    names = ['config.json', model_file, f"voices/{voice['voice']}.pt"]
    sources = []
    for name in names:
        target = cache / name
        url = f"https://huggingface.co/{voice['repo']}/resolve/{voice['revision']}/{name}"
        download(url, target)
        sources.append(dict(file=name, url=url, sha256=sha(target), bytes=target.stat().st_size))
    model = KModel(repo_id=voice['repo'], config=str(cache / 'config.json'),
                   model=str(cache / model_file)).to('cpu').eval()
    english = KPipeline(lang_code='a', repo_id=voice['repo'], model=False)

    def english_phonemes(text):
        return next(english(text)).phonemes

    pipe = KPipeline(lang_code='z' if lang == 'zh' else 'a', repo_id=voice['repo'],
                     model=model, en_callable=english_phonemes if lang == 'zh' else None)
    pack = str(cache / f"voices/{voice['voice']}.pt")
    directory = ROOT / 'public/audio' / lang
    directory.mkdir(parents=True, exist_ok=True)
    generated = 0
    for scene in STORY['scenes']:
        for i, text in enumerate(scene['narration'][lang]):
            path = directory / f"{scene['id']}-{i+1:02}.wav"
            record = path.with_suffix('.json')
            sig = signature(text, lang)
            if path.exists() and record.exists():
                previous = json.loads(record.read_text())
                if previous.get('signature') == sig and previous.get('sha256') == sha(path):
                    continue
            if limit is not None and generated >= limit:
                return
            speed = voice['speed']
            if lang == 'zh':
                speed = lambda count: voice['speed'] * (1 if count <= 83 else max(.85, 1-(count-83)/500))
            pieces = list(pipe(spoken(text, lang), voice=pack, speed=speed, split_pattern=r'\n+'))
            if not pieces or any(p.audio is None or len(p.audio) < SR * .15 for p in pieces):
                raise ValueError(f'No valid speech for {lang}/{scene["id"]}/{i}')
            wave = np.concatenate([p.audio.numpy() for p in pieces])
            if not np.isfinite(wave).all():
                raise ValueError('Non-finite speech samples')
            audible = np.flatnonzero(np.abs(wave) > .0008)
            if not len(audible):
                raise ValueError('Silent speech is not a fallback')
            first = max(0, int(audible[0]) - round(SR * .08))
            last = min(len(wave), int(audible[-1]) + round(SR * .14))
            wave = wave[first:last]
            rms = float(np.sqrt(np.mean(wave**2)))
            gain = min(.1/max(rms, 1e-6), .85/float(np.max(np.abs(wave))))
            wave *= gain
            # Only a 4 ms de-click at waveform edges, after preserving speech padding.
            edge = round(SR * .004)
            wave[:edge] *= np.linspace(0, 1, edge)
            wave[-edge:] *= np.linspace(1, 0, edge)
            sf.write(path, wave, SR, subtype='PCM_16')
            info = dict(text=text, spoken=spoken(text, lang), language=lang,
                        engine={'name': 'kokoro', 'version': '0.9.4'},
                        generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        voice=voice, sampleRate=SR, samples=len(wave),
                        duration=len(wave)/SR, signature=sig, sha256=sha(path),
                        phonemes=[p.phonemes for p in pieces], gain=gain,
                        sourceTrimSamples=[first, last], sources=sources,
                        attribution='Kokoro by hexgrad; Apache-2.0 licensed model. Synthetic narration.')
            record.write_text(json.dumps(info, ensure_ascii=False, indent=2)+'\n')
            generated += 1
            print(f"{lang}/{path.stem}: {len(wave)/SR:.2f}s", flush=True)


def srt_stamp(seconds):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def caption_text(text, lang):
    # The English performance script spells out these acronyms for the voice.
    # Keep the published captions in their normal written form.
    return text.replace('M two', 'M2').replace('T U I', 'TUI') if lang == 'en' else text


def timeline():
    result = dict(fps=FPS, width=STORY['width'], height=STORY['height'],
                  sourceStorySha256=sha(ROOT / 'src/story.json'), scenes=[],
                  captions={'zh': [], 'en': []}, audio={'zh': [], 'en': []})
    start = 0
    for index, scene in enumerate(STORY['scenes']):
        lead = round(.8 * FPS)
        gap = round(.28 * FPS)
        local = {'zh': [], 'en': []}
        lengths = []
        for lang in ['zh', 'en']:
            offset = lead
            for i, text in enumerate(scene['narration'][lang]):
                audio = f"audio/{lang}/{scene['id']}-{i+1:02}.wav"
                record = json.loads((ROOT / 'public' / audio).with_suffix('.json').read_text())
                if record['signature'] != signature(text, lang):
                    raise ValueError(f'Stale voice: {audio}; run voice before rendering')
                duration = math.ceil(record['duration'] * FPS)
                clip = dict(scene=scene['id'], text=text, file=audio, fromFrame=start+offset,
                            durationFrames=duration, durationSeconds=record['duration'], sha256=record['sha256'])
                local[lang].append(clip)
                offset += duration + gap
            lengths.append(offset - gap if local[lang] else 0)
        tail = round((3.5 if scene['id'] == 'closing' else 1.0) * FPS)
        duration = math.ceil(max(scene['minSeconds']*FPS, max(lengths)+tail) / 15) * 15
        shot = dict(id=scene['id'], index=index, start=start, duration=duration,
                    keyframe=start+min(round(duration*.52), max(60, duration-50)),
                    voiceStart=lead, voiceEnd=start+max(lengths))
        result['scenes'].append(shot)
        for lang in ['zh', 'en']:
            result['audio'][lang].extend(local[lang])
            for clip in local[lang]:
                result['captions'][lang].append(dict(
                    scene=scene['id'], start=clip['fromFrame']/FPS,
                    end=(clip['fromFrame']+clip['durationFrames'])/FPS,
                    text=caption_text(clip['text'], lang)))
        start += duration
    result['durationInFrames'] = start
    (ROOT/'src/generated/timing.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    for lang in ['zh', 'en']:
        entries = result['captions'][lang]
        srt = '\n\n'.join(f"{i+1}\n{srt_stamp(c['start'])} --> {srt_stamp(c['end'])}\n{c['text']}" for i,c in enumerate(entries))+'\n'
        (ROOT/f'public/audio/narration-{lang}.srt').write_text(srt)
        vtt = 'WEBVTT\n\n' + '\n\n'.join(f"{srt_stamp(c['start']).replace(',', '.')} --> {srt_stamp(c['end']).replace(',', '.')}\n{c['text']}" for c in entries)+'\n'
        (ROOT/f'public/audio/narration-{lang}.vtt').write_text(vtt)
        (ROOT/f'public/audio/narration-{lang}.md').write_text('\n\n'.join(c['text'] for c in entries)+'\n')
    print(f'Shared timeline: {start} frames / {start/FPS:.2f}s', flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', choices=['zh', 'en', 'both'], default='both')
    parser.add_argument('--limit', type=int, help='Generate only N missing sentences for a voice sample')
    parser.add_argument('--timing-only', action='store_true')
    args = parser.parse_args()
    if not args.timing_only:
        for language in (['zh', 'en'] if args.language == 'both' else [args.language]):
            generate(language, args.limit)
    if args.limit is None:
        timeline()
