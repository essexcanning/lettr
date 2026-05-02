"""Lettr — LiveKit voice agent entrypoint.

Run locally:
    python -m agent.main dev
This will register a worker with LiveKit Cloud. Open the LiveKit playground
at https://agents-playground.livekit.io and connect with your project URL —
your microphone hits Lettr, Lettr replies in voice.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv()

from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import elevenlabs, openai, silero
try:
    from livekit.plugins import deepgram  # available as a fallback STT
except ImportError:
    deepgram = None

from . import tools
from .graph import build_graph


SYSTEM_PROMPT = """You are Lettr — a calm, dryly witty AI letting agent that
works *for* the renter, against the broken London lettings market.

Your user is Stephen. You've been hired to find him a flat without him having
to chase a single estate agent.

Tone:
- Warm, brief, slightly weary about the industry — like a friend who's been a
  letting agent for 15 years and is now on the renter's side.
- Never apologise on behalf of letting agents. Skewer them gently.
- Keep voice replies under three sentences when possible. The user is talking,
  not reading.

Behaviour:
- When Stephen describes what he wants, call `update_preferences` with his
  exact words plus a structured filter.
- After updating preferences, call `search_listings` and read the top result
  back to him conversationally — never list five flats out loud.
- When he says "go ahead" or similar, call `email_letting_agent` on the top
  pick.
- If the agent doesn't reply, escalate: chase once, then leave a voicemail.
  Tell Stephen what you've done.
- When a viewing is booked, confirm it back via voice.

Always work via tool calls — never invent fake confirmations.
"""


def _llm():
    """Fireworks-served LLM via the OpenAI-compatible endpoint."""
    return openai.LLM(
        api_key=os.environ["FIREWORKS_API_KEY"],
        base_url="https://api.fireworks.ai/inference/v1",
        model=os.environ.get(
            "FIREWORKS_MODEL",
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
        ),
    )


def _stt():
    """Speech-to-text fallback chain. All sponsor-aligned with LiveKit's slide 34.
      1. ElevenLabs Scribe (if the LiveKit plugin exposes STT)
      2. Fireworks Whisper-v3-turbo via OpenAI-compatible API
      3. Deepgram Nova-2 (LiveKit's reference STT integration)
    """
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
        self._user_id = "U_stephen"
        self._graph = build_graph()

    # --- Tools the LLM can call ----------------------------------------- #

    @agents.function_tool
    async def update_preferences(self, natural_language: str) -> str:
        """Persist a fresh statement of what the user wants in plain English."""
        tools.update_preferences(self._user_id, natural_language)
        return "preferences updated"

    @agents.function_tool
    async def search_listings(self) -> str:
        """Return the current top-5 listings for the user's taste."""
        results = tools.search_listings(self._user_id, k=5)
        if not results:
            return "no matching listings yet"
        top = results[0]
        return (
            f"Top match is {top['title']} in {top['area']} for "
            f"£{top['price_pcm']}/mo. There are {len(results)} matches total."
        )

    @agents.function_tool
    async def start_outreach(self) -> str:
        """Begin the LangGraph workflow: contact the top letting agent and chase
        until reply or voicemail. State persists in MongoDB."""
        config = {"configurable": {"thread_id": f"thread:{self._user_id}"}}
        result = await self._graph.ainvoke({"user_id": self._user_id}, config)
        return f"Outreach started. Pending: {result.get('pending_action')}"


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
    await session.start(agent=LettrAgent(), room=ctx.room)
    await session.generate_reply(
        instructions=("Greet Stephen warmly, ask him what he's looking for in "
                      "his next flat. One sentence each.")
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
