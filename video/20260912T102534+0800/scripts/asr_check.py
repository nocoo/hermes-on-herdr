# /// script
# requires-python = ">=3.11"
# dependencies = ["mlx-whisper==0.4.2"]
# ///
"""Optional Apple Silicon transcription check of the generated narration stems.

This is an ASR cross-check, not a claim that a human has reviewed the voices.
Run after soundtrack.py: uv run scripts/asr_check.py
"""
import json
from pathlib import Path
import mlx_whisper

ROOT = Path(__file__).resolve().parents[1]
for language in ['zh', 'en']:
    audio = ROOT/f'.cache/audio/voice-{language}.wav'
    result = mlx_whisper.transcribe(str(audio), path_or_hf_repo='mlx-community/whisper-small-mlx',
        language=language, temperature=0, condition_on_previous_text=False, word_timestamps=True)
    result['verificationMethod'] = 'Local independent Whisper ASR of the exact narration stem; transcript is review evidence, not source captions.'
    result['source'] = str(audio.relative_to(ROOT))
    result['model'] = 'mlx-community/whisper-small-mlx'
    (ROOT/f'verification/asr-{language}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(language, result['text'], flush=True)
