"""Transcribe any audio file with Whisper (mlx-audio). Handy for checking a voice's .txt.

    python scripts/transcribe.py voices/erlich.wav
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice_clone import voices  # noqa: E402

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
t0 = time.perf_counter()
text = voices.transcribe(Path(sys.argv[1]).resolve())
print(f"[{time.perf_counter() - t0:.1f}s] {text}")
