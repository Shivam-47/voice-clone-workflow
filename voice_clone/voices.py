"""Voice library: every audio file directly in voices/ is a cloneable voice named after the file.

    voices/erlich.mp3        -> voice "erlich"  (any format ffmpeg reads: wav, mp3, m4a, flac, mp4, ...)
    voices/erlich.txt        -> its exact transcript (created with Whisper on first use if missing)
    voices/raw/              -> untrimmed source recordings; ignored
    voices/.cache/erlich.wav -> prepared reference: mono, 24 kHz, loudness-normalized, <= MAX_REF_SECONDS

Qwen3-TTS only clones (ICL mode) with BOTH the clip and its transcript; without the transcript it silently
produces truncated, non-cloned audio. So a transcript is always made. Whisper can mishear a word: fix the
.txt by hand (it is re-created only when the clip is newer than it).
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from voice_clone import config

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".mp4", ".mov", ".mkv", ".webm"}
CACHE_DIR = config.VOICES_DIR / ".cache"

log = logging.getLogger("voice_clone.voices")


@dataclass
class Voice:
    name: str
    source: Path       # what was dropped in voices/
    ref_audio: Path    # prepared clip fed to the model
    ref_text: str      # exact transcript of ref_audio


def find_sources() -> dict[str, Path]:
    """name -> source file. If several files share a name (erlich.wav + erlich.mp3), .wav wins."""
    found: dict[str, Path] = {}
    for p in sorted(config.VOICES_DIR.glob("*")):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS and not p.name.startswith("."):
            if p.stem not in found or p.suffix.lower() == ".wav":
                found[p.stem] = p
    return found


def duration_s(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out or 0)


def to_reference_wav(source: Path, out: Path, start: float = 0.0, duration: float | None = None) -> Path:
    """Any audio/video -> mono 24 kHz loudness-normalized WAV (optionally a [start, start+duration] window)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if start:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(source), "-t", str(duration or config.MAX_REF_SECONDS),
            "-vn", "-ac", "1", "-ar", "24000", "-af", "loudnorm=I=-20:TP=-2", str(out)]
    subprocess.run(cmd, check=True)
    return out


def prepare_audio(name: str, source: Path) -> Path:
    """Cached reference clip for a voice; redone when the source file changes."""
    out = CACHE_DIR / f"{name}.wav"
    if out.exists() and out.stat().st_mtime >= source.stat().st_mtime:
        return out
    if (length := duration_s(source)) > config.MAX_REF_SECONDS:
        log.warning("%s: %s is %.0fs, using the first %.0fs (cut a better window with scripts/make_ref.py)",
                    name, source.name, length, config.MAX_REF_SECONDS)
    return to_reference_wav(source, out)


def transcribe(path: Path) -> str:
    from mlx_audio.stt.generate import generate_transcription  # lazy: slow import, only for new voices
    log.info("transcribing %s with %s ...", path.name, config.STT_MODEL)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # it always saves a copy of the transcript to output_path; keep that in the cache, not the CWD
    result = generate_transcription(model=config.STT_MODEL, audio=str(path),
                                    output_path=str(CACHE_DIR / f"{path.stem}-whisper"))
    return " ".join(result.text.split())


def load_voice(name: str, source: Path) -> Voice:
    ref_audio = prepare_audio(name, source)
    txt = source.with_suffix(".txt")
    if txt.exists() and txt.stat().st_mtime < source.stat().st_mtime:
        log.warning("%s: %s is older than the audio, re-transcribing", name, txt.name)
        txt.unlink()
    if not txt.exists():
        text = transcribe(ref_audio)
        txt.write_text(text + "\n", encoding="utf-8")
        log.info("%s: wrote %s (check it and fix misheard words): %r", name, txt.name, text)
    text = " ".join(txt.read_text(encoding="utf-8").split())
    if not text:
        raise ValueError(f"{txt} is empty")
    return Voice(name, source, ref_audio, text)


def get(name: str) -> Voice:
    source = find_sources().get(name)
    if source is None:
        raise SystemExit(f"no voice {name!r}: add voices/{name}.wav (have {sorted(find_sources())})")
    return load_voice(name, source)


def load_all() -> dict[str, Voice]:
    voices = {}
    for name, source in find_sources().items():
        try:
            voices[name] = load_voice(name, source)
        except Exception:
            log.exception("%s: couldn't prepare %s, skipping", name, source.name)
    return voices
