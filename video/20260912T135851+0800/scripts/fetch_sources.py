"""Restore only missing, hash-pinned public assets; never replace an existing file."""

import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    sources = json.loads((ROOT / "research/sources.lock.json").read_text())["sources"]
    for item in sources:
        path = ROOT / item["file"]
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Asset path must stay inside this preparation")
        if path.exists():
            data = path.read_bytes()
        else:
            if not item["url"].startswith("https://"):
                raise ValueError("Only pinned HTTPS public assets are supported")
            request = urllib.request.Request(
                item["url"], headers={"User-Agent": "hermes-on-herdr-asset-preparation"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"Source hash differs: {item['file']}")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as output:
                output.write(data)
        print(f"verified {item['id']}")


if __name__ == "__main__":
    main()
