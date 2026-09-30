"""OpenAI-compatible TTS server that speaks in cloned voices: POST /v1/audio/speech, GET /health.

voice = file name in voices/ (see voice_clone/voices.py). New files are picked up on the first request for
an unknown voice; edited transcripts need a restart. Audio is streamed as raw PCM (24 kHz s16le mono), which
LiveKit's `openai.TTS(response_format="pcm")` plays as it arrives.

    uvicorn server.tts_server:app --host 127.0.0.1 --port 8001      # from the repo root

Log per sentence: "first audio in N ms" and "done: X s audio for N chars (RTF)". ~13-16 chars per second of
audio is normal; much less means audio was dropped (see .claude/docs/troubleshooting.md).
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from voice_clone import config, voices
from voice_clone.engine import OUT_SR, CloneTTS, to_pcm16

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tts")

TTS = CloneTTS()
GEN_LOCK = threading.Lock()  # one generation at a time; MLX generate isn't meant to run concurrently

VOICES: dict[str, voices.Voice] = voices.load_all()
for _v in VOICES.values():
    TTS.warm_up(_v)
if not VOICES:
    log.warning("no voices yet: add voices/<name>.wav (or .mp3, .m4a, ...) and request voice=<name>")
log.info("ready: %s, voices=%s", config.TTS_MODEL, sorted(VOICES))


def get_voice(name: str) -> voices.Voice | None:
    """Known voice, or pick up a file added to voices/ since startup. Callers hold GEN_LOCK."""
    if name not in VOICES and (source := voices.find_sources().get(name)):
        VOICES[name] = voices.load_voice(name, source)
        TTS.warm_up(VOICES[name])
    return VOICES.get(name)


app = FastAPI()


class SpeechRequest(BaseModel):
    # OpenAI speech request shape; extra fields LiveKit sends (instructions, stream_format, ...) are ignored
    input: str
    voice: str
    model: str | None = None
    response_format: str = "pcm"
    speed: float | None = None


@app.get("/health")
def health():
    return {"model": config.TTS_MODEL, "voices": sorted(VOICES), "available": sorted(voices.find_sources()),
            "output_sample_rate": OUT_SR}


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest):
    if req.voice not in VOICES and req.voice not in voices.find_sources():
        raise HTTPException(400, f"unknown voice {req.voice!r}: add voices/{req.voice}.wav (have {sorted(VOICES)})")
    if req.response_format != "pcm":
        raise HTTPException(400, "only response_format='pcm' (24 kHz s16le mono) is supported")
    text = req.input.strip()
    rid = uuid.uuid4().hex[:12]

    # Generation runs in its own thread and hands chunks to the response through a queue. When the client goes
    # away (interrupted, or the agent quit) the response generator's `finally` sets `cancel`; the worker stops
    # at the next chunk and releases GEN_LOCK. (Holding the lock inside a sync response generator leaked it on
    # disconnect, and every later request hung silently.)
    loop = asyncio.get_running_loop()
    chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
    cancel = threading.Event()

    def put(item: bytes | None) -> None:
        loop.call_soon_threadsafe(chunks.put_nowait, item)

    def worker() -> None:
        t0 = time.perf_counter()
        if not GEN_LOCK.acquire(timeout=config.LOCK_WAIT_SECONDS):
            log.error("[%s] model busy for %.0fs, dropping %r", rid, config.LOCK_WAIT_SECONDS, text[:80])
            put(None)
            return
        try:
            voice = get_voice(req.voice)
            if voice is None:
                raise RuntimeError(f"voice {req.voice!r} disappeared")
            waited, first, samples = time.perf_counter() - t0, True, 0
            for audio in TTS.generate(text, voice, stream=True):
                if cancel.is_set():
                    log.info("[%s] client gone, stopped generating", rid)
                    break
                if first:
                    log.info("[%s] %s: first audio in %.0f ms (waited %.0f ms for model/voice): %r", rid,
                             req.voice, (time.perf_counter() - t0) * 1000, waited * 1000, text[:80])
                    first = False
                samples += audio.size
                put(to_pcm16(audio))
            else:
                gen_s, audio_s = time.perf_counter() - t0, samples / OUT_SR
                log.info("[%s] done: %.1fs audio for %d chars in %.2fs (RTF %.2f)", rid, audio_s, len(text),
                         gen_s, gen_s / audio_s if audio_s else float("inf"))
        except Exception:
            log.exception("[%s] generation failed", rid)
        finally:
            GEN_LOCK.release()
            put(None)

    async def stream():
        try:
            while (chunk := await chunks.get()) is not None:
                yield chunk
        finally:
            cancel.set()

    if text:
        threading.Thread(target=worker, name=f"tts-{rid}", daemon=True).start()
    else:
        chunks.put_nowait(None)
    # x-request-id: the OpenAI client reports it as request_id (silences LiveKit's "no request_id" warning)
    return StreamingResponse(stream(), media_type="audio/pcm", headers={"x-request-id": rid})
