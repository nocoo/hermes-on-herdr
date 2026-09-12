# Product films

## Current English film

https://github.com/user-attachments/assets/c19ff537-9637-44bf-a9ba-3b4f4a6ce065

[Context is control](20260912T142005+0800/README.md) is the approved English film: 96.5 seconds, 1920 × 1080, 30 fps. Its original 2D animation uses authentic product logos, plain body captions and subtitle-free bookends. The complete published Hexly Video Kit is vendored at `e1b220a7643e8275134b0bff0a11d703c047abbe`; the current Hexly checkout is not a build dependency.

[The Weekend Protocol / 周末交接](20260912T102534+0800/README.md) is the historical bilingual production. Its source and production records remain in the original dated directory.

## Media storage

At the owner's request, MP4 and audio binaries under `video/` are ignored and removed from the current Git index. Local media files are retained unchanged. Source, narration text, subtitles, voice metadata, licenses, checksums, still images, slides and verification records remain tracked. This policy also applies to media inside historical production directories; their source and records are unchanged.

The owner-uploaded attachment above is the current viewing link. The exact original media remain in published commit `dfd8e2e96d4ef82e0169da6ced23f1a6b54c6943`; stopping tracking does not remove those bytes from Git history. Historical reports describe the artifacts at their original verification time.

To restore missing original media for local preview, rerendering or verification, run this from the repository root. It reads Git history, skips existing files and leaves the restored files ignored:

```sh
python3 - <<'PY'
from pathlib import Path
import subprocess

revision = "dfd8e2e96d4ef82e0169da6ced23f1a6b54c6943"
files = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", "-z", revision, "--", "video/"]
).decode().split("\0")
for name in filter(None, files):
    path = Path(name)
    if path.suffix not in {".mp4", ".wav", ".m4a"} or path.exists():
        continue
    data = subprocess.check_output(["git", "show", f"{revision}:{name}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(data)
PY
```

A shallow clone must first fetch that commit. Alternatively, use each production's pinned narration and soundtrack scripts to generate new local audio before rendering. Regeneration can vary across runtime/hardware versions; the original media and hashes define the approved masters. No other repository is modified or required for this recovery.
