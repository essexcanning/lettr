"""ElevenLabs outbound voicemail generation.

This is the demo's killer moment. When a letting agent ghosts, the agent calls
them and leaves a polite voicemail. We render the audio with ElevenLabs and
save it as an MP3 the dashboard can play."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from .db import coll, now


AUDIO_DIR = Path(__file__).resolve().parents[1] / "audio_out"
AUDIO_DIR.mkdir(exist_ok=True)


def _voicemail_text(agent_name: str, agency: str, listing: dict) -> str:
    return (
        f"Hi, this is a message for {agent_name} at {agency}. "
        f"This is Lettr calling on behalf of Stephen Canning. "
        f"Stephen sent you an enquiry about the property on {listing['title'].lower()} "
        f"a few days ago and hasn't heard back. He's a serious renter with "
        f"references ready and is keen to view this week. "
        f"Could you give him a call back on the number provided? "
        f"Many thanks, have a great day."
    )


def generate_voicemail(user_id: str, agent_id: str, listing_id: str) -> str:
    """Render the voicemail audio with ElevenLabs and store it on disk.

    Returns a path the dashboard can load (relative to the dashboard root).
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

    agent = coll("letting_agents").find_one({"_id": agent_id})
    listing = coll("listings").find_one({"_id": listing_id})
    if not agent or not listing:
        raise ValueError("agent or listing not found")
    text = _voicemail_text(agent["agent_name"], agent["agency"], listing)

    out_path = AUDIO_DIR / f"vm-{agent_id}-{listing_id}-{int(now().timestamp())}.mp3"

    def _script_fallback(reason: str) -> str:
        """Write the voicemail script as a .txt so the dashboard can still
        show the agent's escalation, even if ElevenLabs is unavailable."""
        txt_path = out_path.with_suffix(".txt")
        txt_path.write_text(f"[{reason}]\n\n{text}")
        return f"/audio/{txt_path.name}"

    if not api_key:
        return _script_fallback("ElevenLabs key not set — script-only fallback")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.75,
            "style": 0.30,
        },
    }
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(url, json=payload, headers=headers)
            if r.status_code == 402:
                return _script_fallback("ElevenLabs quota exhausted — redeem Creator coupon at elevenlabs.io")
            r.raise_for_status()
            out_path.write_bytes(r.content)
    except httpx.HTTPError as e:
        return _script_fallback(f"ElevenLabs error: {type(e).__name__}")

    return f"/audio/{out_path.name}"
