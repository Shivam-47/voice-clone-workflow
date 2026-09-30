"""Settings from .env (repo root). Every value can also be set as a normal environment variable."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# huggingface_hub reads HF_TOKEN; accept the longer name too
if os.getenv("HUGGING_FACE_TOKEN") and not os.getenv("HF_TOKEN"):
    os.environ["HF_TOKEN"] = os.environ["HUGGING_FACE_TOKEN"]


def env(key: str, default: str) -> str:
    return os.getenv(key) or default


VOICES_DIR = ROOT / "voices"
OUT_DIR = ROOT / "out"

TTS_MODEL = env("TTS_MODEL", "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit")
STT_MODEL = env("STT_MODEL", "mlx-community/whisper-large-v3-turbo-asr-fp16")
LLM_MODEL = env("LLM_MODEL", "mlx-community/Qwen3-8B-4bit")

VOICE = env("VOICE", "gilfoyle")                                     # default voice = voices/<VOICE>.*
STREAM_INTERVAL = float(env("TTS_STREAM_INTERVAL", "0.64"))           # s of audio per streamed chunk
MAX_REF_SECONDS = float(env("TTS_MAX_REF_SECONDS", "20"))             # longer refs are slow and degrade output
LOCK_WAIT_SECONDS = float(env("TTS_LOCK_WAIT", "60"))                 # server: max wait for the model

LLM_PORT = int(env("LLM_PORT", "8080"))
STT_PORT = int(env("STT_PORT", "8000"))
TTS_PORT = int(env("TTS_PORT", "8001"))

CHARACTER_PROMPT = env(
    "CHARACTER_PROMPT",
    "You are a witty, dramatic film character. Stay in character. Keep replies to 1-3 short spoken "
    "sentences, no markdown or emojis. /no_think",
)
