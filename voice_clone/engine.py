"""Thin wrapper around an mlx-audio TTS model: load once, clone a voice, yield float32 chunks."""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator

import numpy as np

from voice_clone import config
from voice_clone.voices import Voice

log = logging.getLogger("voice_clone.engine")
OUT_SR = 24000  # Qwen3-TTS native rate, and what LiveKit's openai.TTS assumes for "pcm"


class CloneTTS:
    def __init__(self, model_id: str = config.TTS_MODEL) -> None:
        from mlx_audio.tts.utils import load_model
        t0 = time.perf_counter()
        self.model_id = model_id
        self.model = load_model(model_id)
        self.sample_rate = int(getattr(self.model, "sample_rate", OUT_SR) or OUT_SR)
        log.info("loaded %s (sr=%d) in %.1fs", model_id, self.sample_rate, time.perf_counter() - t0)

    def generate(self, text: str, voice: Voice, stream: bool = False,
                 interval: float = config.STREAM_INTERVAL) -> Iterator[np.ndarray]:
        """Yields mono float32 audio at OUT_SR. stream=True yields ~`interval` s chunks as they're generated."""
        kwargs = {"stream": True, "streaming_interval": interval} if stream else {}
        for r in self.model.generate(text=text, ref_audio=str(voice.ref_audio), ref_text=voice.ref_text, **kwargs):
            sr = int(getattr(r, "sample_rate", self.sample_rate) or self.sample_rate)
            yield resample(np.asarray(r.audio, dtype=np.float32).reshape(-1), sr, OUT_SR)

    def warm_up(self, voice: Voice) -> None:
        """First call per voice compiles kernels and encodes the reference clip."""
        t0 = time.perf_counter()
        for _ in self.generate("Ready.", voice):
            pass
        log.info("voice %r ready (%s, warm-up %.1fs), transcript: %r", voice.name, voice.source.name,
                 time.perf_counter() - t0, voice.ref_text[:100])


def resample(a: np.ndarray, sr: int, target: int) -> np.ndarray:
    if sr == target or not a.size:
        return a
    n = int(round(a.size * target / sr))
    return np.interp(np.linspace(0, a.size - 1, n), np.arange(a.size), a).astype(np.float32)


def to_pcm16(a: np.ndarray) -> bytes:
    return (np.clip(a, -1.0, 1.0) * 32767).astype("<i2").tobytes()
