"""Same Noto Sans SC as the site; common Chinese plus optional project text.

uv run --with fonttools --with brotli python scripts/subset-font.py SOURCE.ttf [TEXT.json ...]
Source URL and hashes are recorded in brand-source.json. Never run during a build.
"""

import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1])
characters = set(chr(code) for code in range(32, 127))
characters.update(chr(code) for code in range(0x2000, 0x2070))
characters.update(chr(code) for code in range(0x3000, 0x3040))
for first in range(0xA1, 0xF8):
    for second in range(0xA1, 0xFF):
        try:
            characters.update(bytes([first, second]).decode("gb2312"))
        except UnicodeDecodeError:
            pass
for path in sys.argv[2:]:
    characters.update(Path(path).read_text())
font = TTFont(source, recalcTimestamp=False)
options = subset.Options()
options.flavor = "woff2"
options.recalc_timestamp = False
options.name_IDs = ["*"]
options.name_legacy = True
options.name_languages = ["*"]
subsetter = subset.Subsetter(options=options)
subsetter.populate(unicodes=sorted(ord(char) for char in characters))
subsetter.subset(font)
font.flavor = "woff2"
target = root / "public/video-kit/1.0.0/hexly/journey-cjk.woff2"
font.save(target)
print(f"{target}: {target.stat().st_size:,} bytes; {len(font.getBestCmap()):,} code points")
