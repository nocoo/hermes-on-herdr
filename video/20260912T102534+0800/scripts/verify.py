"""Fail on stale assets, invalid media, black frames, silence/dropouts, or bad decks."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
STORY=json.loads((ROOT/'src/story.json').read_text())
TIMING=json.loads((ROOT/'src/generated/timing.json').read_text())
OUT=ROOT/'verification'
OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def run(args):
    return subprocess.run(args,capture_output=True,text=True,check=True)


def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]).stdout)


def contact(files, path, lang, label):
    width,height=640,360
    sheet=Image.new('RGB',(width*2,64+(height+42)*math.ceil(len(files)/2)), '#0b161c')
    draw=ImageDraw.Draw(sheet)
    font_path=ROOT/'.cache/fonts/NotoSansSC.ttf'
    font=ImageFont.truetype(str(font_path),18) if font_path.exists() else ImageFont.load_default(size=18)
    draw.text((22,19),f'HERMES ON HERDR / {lang.upper()} / {label}',fill='#d6b77a',font=font)
    for i,(file,title) in enumerate(files):
        with Image.open(file) as image:
            thumb=ImageOps.contain(image.convert('RGB'),(width,height))
        x=(i%2)*width;y=64+(i//2)*(height+42)
        sheet.paste(thumb,(x,y))
        draw.text((x+18,y+height+10),title,fill='#c4d5c6',font=font)
    sheet.save(path,quality=92)


def assets():
    assert not TIMING.get('provisional'), 'Only measured narration may be delivered'
    assert TIMING['sourceStorySha256']==sha(ROOT/'src/story.json')
    assert [TIMING['width'],TIMING['height'],TIMING['fps']]==[1920,1080,30]
    assert sum(s['duration'] for s in TIMING['scenes'])==TIMING['durationInFrames']
    report={'status':'passed','seconds':TIMING['durationInFrames']/TIMING['fps'],'languages':{}}
    for lang in ['zh','en']:
        files=[]
        for scene in TIMING['scenes']:
            path=ROOT/f"public/review/stills/{lang}/{scene['index']:02}-{scene['id']}.png"
            with Image.open(path) as image:
                assert image.size==(1920,1080)
            files.append((path,f"{scene['index']:02} / {scene['id']} / {scene['start']/30:.1f}s"))
        contact(files,ROOT/f'public/review/contact-{lang}.jpg',lang,'CLEAN CHAPTER FRAMES')
        clips=[]
        for clip in TIMING['audio'][lang]:
            path=ROOT/'public'/clip['file']
            assert sha(path)==clip['sha256']
            audio,sample_rate=sf.read(path)
            assert np.isfinite(audio).all() and sample_rate==24000
            assert abs(len(audio)/sample_rate-clip['durationSeconds'])<1e-6
            assert .001 < np.sqrt(np.mean(audio*audio)) < .3
            assert np.max(np.abs(audio)) < .99
            scan=run(['ffmpeg','-hide_banner','-i',str(path),'-af','silencedetect=noise=-48dB:d=0.85','-f','null','-'])
            silences=re.findall(r'silence_duration: ([\d.]+)',scan.stderr)
            assert not silences, f'Unexpected long internal speech pause: {clip["file"]}: {silences}'
            clips.append({'file':clip['file'],'duration':clip['durationSeconds'],'rms':float(np.sqrt(np.mean(audio*audio))),'peak':float(np.max(np.abs(audio)))})
        mix=probe(ROOT/f'public/audio/mix-{lang}.m4a')
        audio_stream=mix['streams'][0]
        assert audio_stream['codec_name']=='aac' and int(audio_stream['sample_rate'])==48000 and audio_stream['channels']==2
        assert abs(float(mix['format']['duration'])-report['seconds'])<.05
        report['languages'][lang]={'sentences':len(clips),'clips':clips,'audioMix':mix['format']['duration']}
    return report


def media(lang):
    movie=ROOT/f"public/review/{STORY['artifact']}-{lang}.mp4"
    info=probe(movie)
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    audio=next(s for s in info['streams'] if s['codec_type']=='audio')
    assert video['codec_name']=='h264' and video['pix_fmt'] in ['yuv420p','yuvj420p']
    assert [video['width'],video['height'],video['r_frame_rate']]==[1920,1080,'30/1']
    assert int(video['nb_frames'])==TIMING['durationInFrames']
    assert audio['codec_name']=='aac' and int(audio['sample_rate'])==48000 and audio['channels']==2
    assert abs(float(info['format']['duration'])-TIMING['durationInFrames']/30)<.05
    decode=run(['ffmpeg','-v','error','-i',str(movie),'-f','null','-'])
    assert not decode.stderr.strip(), 'Full decode produced errors'
    blacks=run(['ffmpeg','-hide_banner','-i',str(movie),'-vf','blackdetect=d=0:pix_th=0.02:pic_th=0.98','-an','-f','null','-'])
    intervals=re.findall(r'black_start:[^\r\n]+',blacks.stderr)
    assert not intervals, f'Black frames in {lang}: {intervals}'
    silences=run(['ffmpeg','-hide_banner','-i',str(movie),'-af','silencedetect=noise=-55dB:d=0.25','-vn','-f','null','-'])
    silent_intervals=re.findall(r'silence_(?:start|end|duration): [\d.]+',silences.stderr)
    assert not silent_intervals, f'Unexpected silent interval in the final mix: {silent_intervals}'
    loudness=run(['ffmpeg','-hide_banner','-i',str(movie),'-vn','-af','loudnorm=I=-16:TP=-1.8:LRA=9:print_format=json','-f','null','-'])
    stats,_=json.JSONDecoder().raw_decode(loudness.stderr[loudness.stderr.rfind('{'):])
    assert -17<float(stats['input_i'])<-15
    assert float(stats['input_tp'])<=-1.0
    folder=OUT/f'decoded-{lang}'
    folder.mkdir(exist_ok=True)
    select='+'.join(f"eq(n,{s['keyframe']})" for s in TIMING['scenes'])
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(movie),'-vf',f'select={select.replace(",",chr(92)+",")}',
         '-fps_mode','vfr',str(folder/'%02d.png')])
    comparisons=[];files=[]
    for index,scene in enumerate(TIMING['scenes']):
        decoded=folder/f'{index+1:02}.png'
        clean=ROOT/f"public/review/stills/{lang}/{index:02}-{scene['id']}.png"
        # Compare the actual full composition above captions, excluding only the
        # bottom caption band; encoded final frames intentionally have subtitles.
        a=np.asarray(Image.open(decoded).convert('RGB'),dtype=np.float32)[:860]
        b=np.asarray(Image.open(clean).convert('RGB'),dtype=np.float32)[:860]
        rmse=float(np.sqrt(np.mean((a-b)**2)))
        assert rmse < 9.0, f'Rendered motion and still differ at {scene["id"]}: {rmse}'
        comparisons.append({'scene':scene['id'],'frame':scene['keyframe'],'rmseAboveCaptions':rmse})
        files.append((decoded,f"{index:02} / {scene['id']} / FRAME {scene['keyframe']}"))
    contact(files,ROOT/f'public/review/decoded-contact-{lang}.jpg',lang,'DECODED FINAL MP4')
    # Final-frame proof includes the complete closing hold and brand.
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-sseof','-0.04','-i',str(movie),'-frames:v','1',str(folder/'last.png')])
    return {'file':str(movie.relative_to(ROOT)),'bytes':movie.stat().st_size,'sha256':sha(movie),
            'ffprobe':info,'fullDecode':'passed','blackFrames':intervals,'blackDetection':{'pixelThreshold':.02,'pictureThreshold':.98,'minimumDuration':0},
            'unexpectedSilence':silent_intervals,'silenceDetection':{'noise':'-55dB','duration':.25},
            'loudness':stats,'frameComparisons':comparisons,'storage':'ordinary Git' if movie.stat().st_size<100_000_000 else 'release or LFS required'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--assets-only',action='store_true')
    args=parser.parse_args()
    result={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'assets':assets()}
    if not args.assets_only:
        result['media']={lang:media(lang) for lang in ['zh','en']}
        slides=json.loads((ROOT/'public/slides/slides.json').read_text())
        assert slides['sourceStorySha256']==sha(ROOT/'src/story.json')
        assert slides['timingSha256']==sha(ROOT/'src/generated/timing.json')
        assert all(edition['verified'] for edition in slides['editions'].values())
        for edition in slides['editions'].values():
            for kind in ['pdf','odp']:
                assert sha(ROOT/'public/slides'/edition[kind]['file'])==edition[kind]['sha256']
            for page in edition['pages']:
                assert sha(ROOT/'public'/page['file'])==page['imageSha256']
        result['slides']='PDF pixels, ODP package and notes verified by slides.py; current story/timing hashes match'
    result['status']='passed'
    target=OUT/('assets.json' if args.assets_only else 'media.json')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f'PASS: {target}',flush=True)
