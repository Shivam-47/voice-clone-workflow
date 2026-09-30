# voice-clone-workflow

Local zero-shot voice cloning + a real-time voice agent on Apple Silicon. Everything runs on the Mac via MLX:
Whisper (STT), Qwen3 (LLM), Qwen3-TTS (cloning), orchestrated by LiveKit Agents. Public repo: keep it generic
(no character-specific code, no audio). User-facing docs: README.md. Diagram: docs/architecture.svg (source:
docs/architecture.excalidraw).

Read @.claude/docs/troubleshooting.md before debugging: it has the incidents already solved and a checklist.

## Machine / environment
- Apple M5 Pro, 32 GB, macOS, arm64. MLX is Apple-Silicon-only: never create the venv under Rosetta or Linux.
- One venv `.venv` (Python 3.12, uv) from `setup.sh`; `requirements.txt` pins livekit-agents / plugins 1.8.3 and
  installs mlx-audio from git main (M5 fix, see troubleshooting).
- `.env` (gitignored, may hold LiveKit keys / HF token) ← `.env.example`. Values double-quoted: the Procfile
  `source`s it in bash. `voice_clone/config.py` loads it and maps HUGGING_FACE_TOKEN -> HF_TOKEN.

## Layout
```
voice_clone/   config.py (all settings), voices.py (voice library), engine.py (CloneTTS: load/generate/warm_up)
server/        tts_server.py: OpenAI-compatible /v1/audio/speech (pcm stream) + /health
agent/         agent.py: AgentServer + rtc_session; openai.STT/LLM/TTS -> localhost servers; VOICE + CHARACTER_PROMPT
scripts/       clone.py, stream_latency.py, make_ref.py, transcribe.py (run from repo root; add root to sys.path)
voices/        <name>.<audio> + <name>.txt; raw/ (ignored); .cache/ (prepared clips). Only README.md is tracked
docs/          architecture.svg + .excalidraw
Procfile       honcho: llm (mlx_lm.server :8080), stt (mlx_audio.server :8000), tts (uvicorn :8001)
```

## Key design decisions
- **Voice = file name.** `voices.find_sources()` scans top-level audio files; `.wav` wins on name clashes.
  `prepare_audio()` -> `voices/.cache/<name>.wav` (ffmpeg: mono, 24 kHz, loudnorm, first TTS_MAX_REF_SECONDS=20),
  redone when the source is newer.
- **Transcript is mandatory.** mlx-audio Qwen3-TTS only clones (ICL) with both ref_audio and ref_text. Missing or
  stale (older than the clip) `voices/<name>.txt` is created with Whisper (`generate_transcription`, output_path
  in the cache because it always writes a file).
- **TTS server concurrency:** one generation at a time (GEN_LOCK). Generation runs in a worker thread feeding an
  asyncio.Queue; the response generator's `finally` sets a cancel Event so a disconnect stops generation and
  frees the lock. Lock acquire has a timeout (TTS_LOCK_WAIT).
- **Wire format:** only `response_format="pcm"` (24 kHz s16le mono), streamed in TTS_STREAM_INTERVAL (0.64 s)
  chunks. LiveKit's openai.TTS 1.8.3 parses by response Content-Type (`audio/pcm` -> raw), assumes 24 kHz.
  `x-request-id` header avoids LiveKit's "no request_id" warning. LiveKit sends one request per sentence.
- **STT:** `openai.STT(..., use_realtime=False)` against `mlx_audio.server` (batch per VAD turn).
- **LLM:** Qwen3 thinks by default; `/no_think` at the end of CHARACTER_PROMPT keeps replies fast.
- New voice files are loaded on the first request for an unknown name; edited transcripts need a server restart.

## Status (2026-09-30)
- Originally a POC (`mlx-audio/`); cloning + streaming verified on the Mac with a Gilfoyle clip, and the same
  TTS server design runs in the user's `~/MyProjects/character-agent` (its tts/ folder), where it works.
- This refactor (package + voice library + LiveKit 1.8 AgentServer agent + fully local STT/LLM) is **not run yet**.
  First run: `./setup.sh` (the old .venv is invalid after the folder rename), `python scripts/clone.py`,
  `honcho start`, `python agent/agent.py console`.
- Not yet on GitHub (target: github.com/Shivam-47/voice-clone-workflow).

## Conventions
- Settings only in `voice_clone/config.py` / `.env`, never hardcoded in scripts.
- Never commit audio, transcripts, `.env`, or generated output (see .gitignore).
- Keep the README troubleshooting table and .claude/docs/troubleshooting.md in sync when fixing something new.
