#!/usr/bin/env bash
# One-time setup. macOS on Apple Silicon only (MLX).
set -euo pipefail
cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Needs macOS on Apple Silicon (arm64); got $(uname -s) $(uname -m)."
  echo "On an M-series Mac, x86_64 means the terminal is running under Rosetta."
  exit 1
fi
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
command -v uv >/dev/null || brew install uv
command -v ffmpeg >/dev/null || brew install ffmpeg

rm -rf .venv
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
[[ -f .env ]] || cp .env.example .env
mkdir -p voices/raw out

.venv/bin/python -c "import mlx.core as mx; print('MLX', mx.__version__, 'on', mx.default_device())"
cat <<'MSG'

Done. Next:
  source .venv/bin/activate
  # add a voice: voices/<name>.wav (10-20 s, one speaker), set VOICE="<name>" in .env
  python scripts/clone.py                  # first run downloads ~3 GB TTS + ~1.6 GB Whisper
MSG
