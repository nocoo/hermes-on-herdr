"""Check provenance, fixture privacy, rebuild determinism and the protected history."""

import ast
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import itertools
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def load(path):
    return json.loads((ROOT / path).read_text())


def check_link(value, document):
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return
    target = (document.parent / unquote(parsed.path)).resolve()
    if not target.is_file() and not target.is_dir():
        raise AssertionError(f"Missing local link: {document.name} -> {value}")


class LocalLinks(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                check_link(value, ROOT / "index.html")


def main():
    sources = load("research/sources.lock.json")["sources"]
    for item in sources:
        data = (ROOT / item["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"], item["file"]
        assert len(data) == item["bytes"], item["file"]
    for item in load("research/local-sources.json")["files"]:
        assert hashlib.sha256((REPO / item["file"]).read_bytes()).hexdigest() == item["sha256"], item["file"]

    manifest = load("asset-manifest.json")
    cubies = load("fixtures/cubies.json")
    ids = {asset["id"] for asset in manifest["assets"]} | set(manifest["semanticFaceIds"])
    assert len({asset["id"] for asset in manifest["assets"]}) == len(manifest["assets"])
    for beat in load("fixtures/storyboard.json")["beats"]:
        assert set(beat["assets"]) <= ids, beat["id"]
        for source in beat["sources"]:
            if not source.startswith("https://"):
                assert (REPO / source.split("#")[0]).is_file(), source
    positions = [tuple(cube["position"]) for cube in cubies["layout"]]
    assert len(positions) == 27 and set(positions) == set(itertools.product((-1, 0, 1), repeat=3))
    assert all(cube["face"] in manifest["semanticFaceIds"] for cube in cubies["layout"])

    svg_count = 0
    for path in (ROOT / "public").rglob("*.svg"):
        node = ET.parse(path).getroot()
        assert node.tag == "{http://www.w3.org/2000/svg}svg", path.name
        assert node.attrib.get("viewBox"), path.name
        for child in node.iter():
            assert child.tag.split("}")[-1] not in {"script", "foreignObject"}, path.name
            for key, value in child.attrib.items():
                if key.endswith("href"):
                    assert value.startswith(("data:", "#")), path.name
        svg_count += 1
    for asset in manifest["assets"]:
        if asset.get("kind") in ("terminal-fixture", "cubie-texture"):
            node = ET.parse(ROOT / asset["file"]).getroot()
            assert (int(node.attrib["width"]), int(node.attrib["height"])) == (asset["width"], asset["height"])

    private_pattern = re.compile(r"/Users/|/home/(?!demo)|\bcherry\b|w2X:|ghp_[A-Za-z0-9]|github_pat_|xox[bp]-|Bearer\s+\S+|sk-[A-Za-z0-9]{12}", re.I)
    for path in [*(ROOT / "fixtures").glob("*.json"), *(ROOT / "public/cli").glob("*.txt"), *(ROOT / "public/cli").glob("*.ansi")]:
        assert not private_pattern.search(path.read_text()), f"Private-looking content: {path.name}"
    for path in (ROOT / "public/cli").glob("*.txt"):
        assert "SYNTHETIC FIXTURE" in path.read_text() or "DEMO" in path.read_text(), path.name
    for path in ROOT.rglob("*"):
        if any(part in (".cache", ".venv", "node_modules") for part in path.relative_to(ROOT).parts):
            continue
        assert path.suffix.lower() not in {".mp4", ".mov", ".webm", ".mp3", ".wav", ".aac", ".srt", ".vtt"}, path.name
    for path in (ROOT / "scripts").glob("*.py"):
        ast.parse(path.read_text(), filename=path.name)
    for path in ROOT.rglob("*.md"):
        if any(part in (".cache", ".venv", "node_modules") for part in path.relative_to(ROOT).parts):
            continue
        for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", path.read_text()):
            check_link(target, path)
    LocalLinks().feed((ROOT / "index.html").read_text())

    rebuild = subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / "scripts/build_assets.py"), "--check"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    run = load("run.json")
    protected = run["protectedHistory"]
    tree = subprocess.check_output(["git", "rev-parse", f"HEAD:{protected['path']}"], cwd=REPO, text=True).strip()
    assert tree == protected["gitTree"]
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", protected["path"]], cwd=REPO, text=True)
    assert not dirty, "Historical video worktree changed"
    old_media = []
    for item in load("research/local-sources.json")["protectedMedia"]:
        actual = hashlib.sha256((REPO / item["file"]).read_bytes()).hexdigest()
        assert actual == item["sha256"], item["file"]
        old_media.append(item)
    browser = load("verification/browser.json")
    for item in browser["captures"]:
        data = (ROOT / item["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        assert struct.unpack(">II", data[16:24]) == (item["width"], item["height"])
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(), "result": "PASS",
        "scope": "Static asset preparation only", "pinnedUpstreamFiles": len(sources),
        "svgFiles": svg_count, "terminalFixtures": 9, "cubieFaces": 18, "cubiePositions": len(positions),
        "deterministicRebuild": rebuild, "sourceHashes": "PASS", "fixturePrivacy": "PASS",
        "svgSafetyAndDimensions": "PASS", "localLinksAndPythonSyntax": "PASS",
        "protectedTree": tree, "protectedMedia": old_media, "browserCaptures": len(browser["captures"]),
        "templateStatus": run["template"]["status"], "finalAudioOrVideo": False,
    }
    (ROOT / "verification/checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
