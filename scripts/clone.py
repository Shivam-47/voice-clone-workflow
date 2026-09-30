"""Offline clone test: speak a line in a voice and save it. Prints load time and real-time factor.

    python scripts/clone.py                                   # default VOICE from .env
    python scripts/clone.py --voice erlich --text "This is my incubator."
    python scripts/clone.py --model mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit   # A/B another model
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from voice_clone import config, voices  # noqa: E402
from voice_clone.engine import OUT_SR, CloneTTS  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--voice", default=config.VOICE)
p.add_argument("--model", default=config.TTS_MODEL)
p.add_argument("--text", default="Well, well. Look who finally showed up. I was starting to think you'd forgotten about me.")
args = p.parse_args()

voice = voices.get(args.voice)
tts = CloneTTS(args.model)
t0 = time.perf_counter()
audio = np.concatenate(list(tts.generate(args.text, voice)))
gen_s, dur = time.perf_counter() - t0, len(audio) / OUT_SR

config.OUT_DIR.mkdir(exist_ok=True)
out = config.OUT_DIR / f"clone_{voice.name}_{args.model.split('/')[-1]}.wav"
sf.write(out, audio, OUT_SR)
print(f"{dur:.1f}s audio for {len(args.text)} chars in {gen_s:.1f}s (RTF {gen_s / dur:.2f}) -> {out}")
print("~13-16 chars per second of audio is normal; much less means audio was dropped.")
print(f"play: afplay '{out}'")
