"""Restore or verify the complete Hexly Video Kit at its published Git revision."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = "e1b220a7643e8275134b0bff0a11d703c047abbe"
PREFIX = "packages/video-kit/"
DEST = ROOT / "vendor/hexly-video-kit"
LOCK = ROOT / "research/hexly-kit.lock.json"


def fetch(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as response:
                return response.read()
        except OSError:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def restore(entry, check):
    target = DEST / entry["path"]
    if not target.resolve().is_relative_to(DEST.resolve()) or target.is_symlink():
        raise ValueError("Unsafe kit path")
    if target.is_file():
        data = target.read_bytes()
    elif check:
        raise FileNotFoundError(target)
    else:
        data = fetch(entry["url"])
    blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if blob != entry["gitBlob"] or len(data) != entry["bytes"]:
        raise ValueError(f"Kit bytes differ: {entry['path']}; never overwriting")
    digest = hashlib.sha256(data).hexdigest()
    if entry.get("sha256") and entry["sha256"] != digest:
        raise ValueError(f"SHA-256 differs: {entry['path']}")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {**entry, "sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if LOCK.exists():
        lock = json.loads(LOCK.read_text())
        assert lock["revision"] == REVISION
        entries = lock["files"]
    else:
        if args.check:
            raise FileNotFoundError(LOCK)
        tree = json.loads(fetch(f"https://api.github.com/repos/nocoo/hexly.ai/git/trees/{REVISION}?recursive=1"))
        assert not tree["truncated"]
        entries = [
            {"path": f["path"][len(PREFIX):], "gitBlob": f["sha"], "bytes": f["size"],
             "url": f"https://raw.githubusercontent.com/nocoo/hexly.ai/{REVISION}/{f['path']}"}
            for f in tree["tree"] if f["path"].startswith(PREFIX) and f["type"] == "blob"
        ]
        assert entries and any(e["path"] == "CREDITS.md" for e in entries)
    with ThreadPoolExecutor(max_workers=6) as pool:
        files = list(pool.map(lambda entry: restore(entry, args.check), entries))
    if not args.check:
        LOCK.write_text(json.dumps({"repository": "https://github.com/nocoo/hexly.ai", "revision": REVISION,
                                   "package": "@hexly/video-kit", "version": "1.0.0", "files": files}, indent=2) + "\n")
    for source in (DEST / "public").rglob("*"):
        if not source.is_file():
            continue
        target = ROOT / "public" / source.relative_to(DEST / "public")
        if target.exists():
            assert target.read_bytes() == source.read_bytes(), target
        elif args.check:
            raise FileNotFoundError(target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    print(f"Verified {len(files)} complete kit files at {REVISION}; licensed public assets match")


if __name__ == "__main__":
    main()
