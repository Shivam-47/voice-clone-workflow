# Troubleshooting log

Incidents already solved (2026-09-30, first in the POC and in ~/MyProjects/character-agent, which uses the same
TTS server design). Each: symptom -> diagnosis -> root cause -> fix -> how to confirm.

## Reading the logs
- TTS server, per sentence: `[rid] <voice>: first audio in N ms (waited M ms for model/voice)` then
  `[rid] done: X.Xs audio for N chars in Ys (RTF r)`, or `[rid] client gone, stopped generating`.
- ~13-16 chars per second of audio is normal. Far less audio than the text needs = dropped/truncated audio.
- Standalone test (no agent):
  ```bash
  curl localhost:8001/health
  curl -s -X POST localhost:8001/v1/audio/speech -H 'Content-Type: application/json' \
    -d '{"input":"Listen carefully, because I am only going to say this once, and I hate repeating myself.","voice":"gilfoyle","response_format":"pcm"}' \
    -o /tmp/t.pcm && ffmpeg -y -loglevel error -f s16le -ar 24000 -ac 1 -i /tmp/t.pcm /tmp/t.wav && afplay /tmp/t.wav
  ```
  That 88-char sentence should be ~5-7 s.
- `scripts/clone.py` prints the same chars-vs-seconds check offline, without any server.

## Harmless noise
- LiveKit: `turn_detection is deprecated`, `console mode is deprecated (use lk agent console)`,
  `no warmed process available for job`.
- `You are sending unauthenticated requests to the HF Hub` (set HF_TOKEN for speed only).
- `[transformers] You are using a model of type qwen3_tts to instantiate a model of type ''` on TTS load.

## 1. Agent goes silent after the first session (lock leak) - FIXED
- Symptom: first session speaks; after Ctrl+C and a new session, turns are transcribed and TTS is requested but
  nothing plays, no assistant messages in the agent log.
- Cause: old server held the generation lock inside a sync streaming generator; a client disconnect mid-sentence
  never closed it, so the lock stayed held and every later request blocked. The server outlives agent sessions.
- Fix: worker thread + queue + cancel Event; lock released in `finally`; acquire with timeout.
- Confirm: `waited 0 ms for model`, and `client gone, stopped generating` on interruptions.

## 2. Only the start and end of sentences are spoken - FIXED (two causes)
- A. M5 bug: mlx-audio issue #464 (Qwen3-TTS drops the middle of sentences on M5 Macs).
  Fix: current mlx + mlx-audio from git main (requirements.txt does this).
- B. Empty transcript (the real blocker): mlx-audio Qwen3-TTS uses ICL cloning only when
  `ref_audio is not None and ref_text is not None`. With ref_text=None: `done: 0.8s audio for 88 chars`, not cloned.
  Fix: transcripts are mandatory and auto-created (voices.py).
- Also raised TTS_STREAM_INTERVAL 0.32 -> 0.64 (tiny chunks can glitch; mlx-audio default 2.0).

## 3. `400 unknown voice '<name>'` right after adding a voice - FIXED (stale process)
- Diagnosis: the error wording came from the old server code and voices/.cache didn't exist -> an old uvicorn
  process was still on the port. Fix: restart (`lsof -ti:8001 | xargs kill`). uvicorn doesn't reload code.

## Reference clip gotchas
- 10-20 s, one speaker, no music / laugh track; cut with scripts/make_ref.py; Demucs for music.
- Transcript must match the *prepared* clip (first 20 s if the source is longer). Keep clip + .txt together.
- Compression artifacts (low-bitrate MP3) get cloned too.
- Whisper's generate_transcription always writes a file (default ./transcript.txt); voices.py redirects it.

## Checklist
1. Server is current code? (`/health` has `available`; voices/.cache exists)
2. Server log: first audio? `done:` length sane? `busy` / `client gone`?
3. curl test right? yes -> agent/LiveKit side; no -> model / clip / transcript side.
4. `voices/<name>.txt` matches `voices/.cache/<name>.wav`? single speaker?
5. `.venv/bin/python -c "import mlx.core as mx; print(mx.__version__)"` recent? mlx-audio from git main?
