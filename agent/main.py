"""Lettr — LiveKit voice agent entrypoint.

Run locally:
    python -m agent.main dev
This will register a worker with LiveKit Cloud. Open the LiveKit playground
at https://agents-playground.livekit.io and connect with your project URL —
your microphone hits Lettr, Lettr replies in voice.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
load_dotenv()

from livekit.agents import AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.voice.agent_session import UserInputTranscribedEvent
from livekit.agents import Agent
from livekit.plugins import elevenlabs, openai, silero
try:
    from livekit.plugins import deepgram
except ImportError:
    deepgram = None

from . import tools

logger = logging.getLogger("lettr")

SYSTEM_PROMPT = (
    "You are Lettr, a calm, dryly witty AI letting agent for London. "
    "Stephen has hired you to find him a flat. "
    "When he describes what he wants, acknowledge it briefly in one sentence "
    "and say you'll start hunting straight away. "
    "Then narrate friendly progress updates as if you're searching. "
    "Never mention tools, functions, databases, or technical details. "
    "Keep replies under 3 sentences."
)


def _llm():
    """Fireworks-served LLM via the OpenAI-compatible endpoint."""
    return openai.LLM(
        api_key=os.environ["FIREWORKS_API_KEY"],
        base_url="https://api.fireworks.ai/inference/v1",
        model=os.environ.get(
            "FIREWORKS_MODEL",
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
        ),
        tool_choice="none",
    )


def _stt():
    """Speech-to-text fallback chain."""
    if hasattr(elevenlabs, "STT"):
        return elevenlabs.STT(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            language_code="en",
        )
    if os.environ.get("FIREWORKS_API_KEY"):
        try:
            return openai.STT(
                api_key=os.environ["FIREWORKS_API_KEY"],
                base_url="https://api.fireworks.ai/inference/v1",
                model="whisper-v3-turbo",
                language="en",
            )
        except Exception:
            pass
    if deepgram and os.environ.get("DEEPGRAM_API_KEY"):
        return deepgram.STT(model="nova-2-general", language="en-GB")
    raise RuntimeError("No STT provider available. Set ELEVENLABS_API_KEY, "
                       "FIREWORKS_API_KEY, or DEEPGRAM_API_KEY.")


class LettrAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)


def _run_background_tools(transcript: str) -> None:
    """Fire-and-forget: persist preferences, search, and email top result.
    Runs synchronously in the worker process — wrapped in try/except so any
    failure is logged but never kills the voice loop."""
    user_id = "U_stephen"
    try:
        tools.update_preferences(user_id, transcript)
    except Exception:
        logger.exception("update_preferences failed")

    try:
        results = tools.search_listings(user_id, k=5)
    except Exception:
        logger.exception("search_listings failed")
        results = []

    if results:
        top = results[0]
        listing_id = top["_id"]
        message = f"Hi — Stephen here, very interested. {transcript[:120]}"
        try:
            tools.email_letting_agent(user_id, listing_id, message)
        except Exception:
            logger.exception("email_letting_agent failed")


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=_stt(),
        llm=_llm(),
        tts=elevenlabs.TTS(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"),
            model="eleven_turbo_v2_5",
        ),
    )

    @session.on("user_input_transcribed")
    def on_transcript(ev: UserInputTranscribedEvent) -> None:
        if ev.is_final and ev.transcript.strip():
            _run_background_tools(ev.transcript)

    await session.start(agent=LettrAgent(), room=ctx.room)
    await session.generate_reply(
        instructions=(
            "Greet Stephen warmly and ask him what he's looking for in "
            "his next flat. One sentence."
        )
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="lettr"))
