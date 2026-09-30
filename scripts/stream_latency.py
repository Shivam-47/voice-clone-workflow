"""Streaming test: time to first audio (what you feel in a conversation) and total real-time factor.

    python scripts/stream_latency.py
    python scripts/stream_latency.py --voice erlich --interval 0.32
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
p.add_argument("--interval", type=float, default=config.STREAM_INTERVAL, help="seconds of audio per chunk")
p.add_argument("--text", default="Listen carefully, because I'm only going to say this once, and I hate repeating myself.")
args = p.parse_args()

voice = voices.get(args.voice)
tts = CloneTTS(args.model)
tts.warm_up(voice)  # measure steady state, not first-call compile

t0 = time.perf_counter()
ttfa, chunks = None, []
for chunk in tts.generate(args.text, voice, stream=True, interval=args.interval):
    ttfa = ttfa if ttfa is not None else time.perf_counter() - t0
    chunks.append(chunk)
total = time.perf_counter() - t0

audio = np.concatenate(chunks)
config.OUT_DIR.mkdir(exist_ok=True)
out = config.OUT_DIR / f"stream_{voice.name}.wav"
sf.write(out, audio, OUT_SR)
print(f"time to first audio: {ttfa * 1000:.0f} ms | {len(chunks)} chunks | {len(audio) / OUT_SR:.1f}s audio "
      f"in {total:.2f}s (RTF {total / (len(audio) / OUT_SR):.2f}) -> {out}")
