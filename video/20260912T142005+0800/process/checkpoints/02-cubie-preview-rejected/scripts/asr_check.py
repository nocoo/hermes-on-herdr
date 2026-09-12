# /// script
# requires-python = ">=3.11"
# dependencies = ["mlx-whisper==0.4.2", "huggingface-hub==0.34.4"]
# ///
"""Independent Apple Silicon ASR of this film's generated narration stem."""

import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download
import mlx_whisper

ROOT = Path(__file__).resolve().parents[1]
model = json.loads((ROOT / "research/asr-model.json").read_text())
cache = snapshot_download(model["repository"], revision=model["revision"])
source = ROOT / ".cache/audio/voice.wav"
result = mlx_whisper.transcribe(str(source), path_or_hf_repo=cache, language="en",
    temperature=0, condition_on_previous_text=False, word_timestamps=True,
    initial_prompt="Hermes on Herdr. Codex, Grok, Pi, Claude Code. M2. Discord, Telegram, Slack. Monitor TUI. Hexly AI.")
result["verificationMethod"] = "Independent local Whisper ASR, with a supplied proper-name vocabulary; not the source of subtitles and not a human listening claim."
result["source"] = ".cache/audio/voice.wav"
result["sourceSha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
result["model"] = model
(ROOT / "verification/asr-en.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(result["text"], flush=True)
