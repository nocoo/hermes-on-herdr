"""Subset the OFL Noto Sans SC variable font to all authored production text."""
import hashlib
import json
from pathlib import Path
import subprocess

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / '.cache/fonts/NotoSansSC.ttf'
url = 'https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf'
if not source.exists():
    source.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['curl', '-fL', '--retry', '3', url, '-o', str(source)], check=True)
text = (ROOT / 'src/story.json').read_text()
for file in (ROOT / 'src').rglob('*.tsx'):
    text += file.read_text()
for file in (ROOT / 'src').rglob('*.ts'):
    text += file.read_text()
# Common UI glyphs, punctuation and the authored subtitle language.
chars = set(text + '中文英文旁白播放暂停动画成片下载章节项目许可字幕简体中英全屏返回回放制作手记周末交接')
font = TTFont(source, recalcTimestamp=False)
cmap = font.getBestCmap()
needed = {ord(c) for c in chars if ord(c) >= 0x3000}
missing = sorted(needed - cmap.keys())
if missing:
    raise ValueError(f'Missing CJK glyphs: {missing}')
options = subset.Options()
options.flavor = 'woff2'
options.layout_features = ['*']
subsetter = subset.Subsetter(options=options)
subsetter.populate(unicodes=needed | set(range(32, 127)))
subsetter.subset(font)
font.flavor = 'woff2'
target = ROOT / 'public/fonts/noto-sans-sc.woff2'
font.save(target)
record = {'source': url, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'outputSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'glyphs': len(needed), 'license': 'SIL Open Font License 1.1'}
(ROOT/'public/fonts/noto-sans-sc.json').write_text(json.dumps(record, indent=2)+'\n')
print(record)
