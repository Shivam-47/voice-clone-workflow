"""Fully local LiveKit voice agent: Silero VAD -> Whisper (mlx-audio) -> Qwen3 (mlx-lm) -> cloned voice.

Start the three servers first (`honcho start`), then:
    python agent/agent.py download-files   # once: Silero VAD weights
    python agent/agent.py console          # talk through the Mac's mic + speakers, no LiveKit server needed
    python agent/agent.py dev              # join LiveKit rooms (LIVEKIT_URL / _API_KEY / _API_SECRET in .env)

VOICE picks the cloned voice (voices/<VOICE>.*); CHARACTER_PROMPT is the system prompt.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from livekit import agents  # noqa: E402
from livekit.agents import Agent, AgentServer, AgentSession, JobProcess  # noqa: E402
from livekit.plugins import openai, silero  # noqa: E402

from voice_clone import config  # noqa: E402  (loads .env)

log = logging.getLogger("voice-agent")
LOCAL_KEY = "local"  # the local servers ignore it, but the OpenAI client needs one


def local_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/v1"


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server = AgentServer(setup_fnc=prewarm)


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext) -> None:
    log.info("voice=%s llm=%s stt=%s", config.VOICE, config.LLM_MODEL, config.STT_MODEL)
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        # batch transcription per VAD-detected turn (mlx-audio server has no realtime endpoint)
        stt=openai.STT(base_url=local_url(config.STT_PORT), api_key=LOCAL_KEY, model=config.STT_MODEL,
                       language="en", use_realtime=False),
        llm=openai.LLM(base_url=local_url(config.LLM_PORT), api_key=LOCAL_KEY, model=config.LLM_MODEL,
                       temperature=0.8),
        # raw 24 kHz PCM, streamed as it's generated; voice = file name in voices/
        tts=openai.TTS(base_url=local_url(config.TTS_PORT), api_key=LOCAL_KEY, model="local-clone",
                       voice=config.VOICE, response_format="pcm"),
    )
    await session.start(room=ctx.room, agent=Agent(instructions=config.CHARACTER_PROMPT))
    await session.generate_reply(instructions="Greet the user in character, in one short line.")


if __name__ == "__main__":
    agents.cli.run_app(server)
