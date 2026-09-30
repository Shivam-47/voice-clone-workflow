"""Cut the best part of a long recording into a voice sample + transcript.

You can also just drop a clip into voices/<name>.<ext> (the first 20 s are used). Use this when the good part
is in the middle of a scene.

    python scripts/make_ref.py erlich voices/raw/erlich-scene.mp4 --start 42 --duration 14

Writes voices/<name>.wav (mono 24 kHz) and plays it, then voices/<name>.txt (Whisper). Pick 10-20 s where only
that character speaks (no music, laughs, other voices), ending on a pause. Fix misheard words in the .txt.
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice_clone import config, voices  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("name", help="voice name, e.g. erlich (-> voices/erlich.wav)")
p.add_argument("source", help="source recording (any format ffmpeg reads)")
p.add_argument("--start", type=float, default=0.0, help="window start, seconds")
p.add_argument("--duration", type=float, default=15.0, help="window length, seconds (10-20)")
p.add_argument("--no-play", action="store_true")
args = p.parse_args()

out = voices.to_reference_wav(Path(args.source).expanduser().resolve(), config.VOICES_DIR / f"{args.name}.wav",
                              start=args.start, duration=args.duration)
print(f"wrote {out.relative_to(config.ROOT)}")
if not args.no_play:
    subprocess.run(["afplay", str(out)])
out.with_suffix(".txt").unlink(missing_ok=True)  # new clip -> new transcript
voice = voices.load_voice(args.name, out)
print(f"wrote {out.with_suffix('.txt').relative_to(config.ROOT)}:\n  {voice.ref_text}\nCheck it by ear.")
