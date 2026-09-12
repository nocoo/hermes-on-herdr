"""Repack unchanged upstream PptxGenJS without its unused image-size dependency."""

import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

VERSION = "4.0.1"
INTEGRITY = "TeJISr8wouAuXw4C1F/mC33xbZs/FuEG6nH9FG1Zj+nuPcGMP5YRHl6X+j3HSUnS1f3at6k75ZZXPMZlA5Lj9A=="
URL = f"https://packagefeedproxy.microsoft.io/npm/pptxgenjs/-/pptxgenjs-{VERSION}.tgz"
DESTINATION = Path(__file__).resolve().parents[1] / "vendor"

with urllib.request.urlopen(URL, timeout=30) as response:
    original = response.read()
if base64.b64encode(hashlib.sha512(original).digest()).decode() != INTEGRITY:
    raise SystemExit("Upstream package integrity mismatch")

output = io.BytesIO()
files = []
with tarfile.open(fileobj=io.BytesIO(original), mode="r:gz") as archive:
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as target:
        for item in archive.getmembers():
            if not item.isfile():
                raise SystemExit(f"Unexpected package entry: {item.name}")
            source = archive.extractfile(item)
            if source is None:
                raise SystemExit(f"Missing package entry: {item.name}")
            data = source.read()
            if item.name.endswith(".js") and b"image-size" in data:
                raise SystemExit("Upstream now references image-size; review required")
            if item.name == "package/package.json":
                manifest = json.loads(data)
                if manifest["dependencies"].pop("image-size") != "^1.2.1":
                    raise SystemExit("Unexpected dependency version")
                manifest["version"] = f"{VERSION}-hexly.1"
                data = (json.dumps(manifest, indent=2) + "\n").encode()
                item.size = len(data)
            else:
                files.append({"path": item.name, "sha256": hashlib.sha256(data).hexdigest()})
            target.addfile(item, io.BytesIO(data))

packed = gzip.compress(output.getvalue(), mtime=0)
DESTINATION.mkdir(exist_ok=True)
path = DESTINATION / f"pptxgenjs-{VERSION}-hexly.1.tgz"
path.write_bytes(packed)
(DESTINATION / "pptxgenjs-source.json").write_text(json.dumps({
    "upstream": f"pptxgenjs@{VERSION}",
    "license": "MIT; upstream LICENSE is inside the archive",
    "source": URL,
    "integrity": f"sha512-{INTEGRITY}",
    "change": "Only package.json: remove unused image-size; label local version 4.0.1-hexly.1. All upstream code, types and license bytes are unchanged.",
    "reason": ["GHSA-5p2g-fcmc-qvqq", "GHSA-w3rx-r6r6-pgpr"],
    "archive": path.name,
    "sha256": hashlib.sha256(packed).hexdigest(),
    "unchangedFiles": files,
}, indent=2) + "\n")
print(f"Wrote {path.name}; {len(files)} unchanged upstream files")
