"""Dashboard server — FastAPI.

Run: uvicorn dashboard.server:app --reload --port 8000

Endpoints:
    GET /                      → reputation dashboard (HTML)
    GET /api/agents            → reputation rows (JSON)
    GET /api/timeline          → recent conversations (JSON)
    GET /api/preferences       → current taste vector summary
    GET /audio/{filename}      → outbound voicemail audio
    POST /demo/timelapse       → run N simulated days quickly
"""
from __future__ import annotations

import os
import threading
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from livekit import api as livekit_api

from agent.db import coll
from agent import simulator


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "dashboard" / "index.html"
TALK_HTML = ROOT / "web" / "index.html"
AUDIO_DIR = ROOT / "audio_out"

app = FastAPI(title="Lettr Reputation Dashboard")

# Allow the Vercel-hosted frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def start_simulator() -> None:
    t = threading.Thread(target=simulator.run_forever, daemon=True)
    t.start()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """The renter-facing landing page with the mic button."""
    return TALK_HTML.read_text()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    """The reputation dashboard (embedded in the landing page as an iframe)."""
    return INDEX_HTML.read_text()


@app.get("/talk", response_class=HTMLResponse)
def talk_alias() -> str:
    """Alias for /."""
    return TALK_HTML.read_text()


@app.get("/api/agents")
def api_agents():
    rows = list(coll("letting_agents").find({}, {"behaviour_seed": 0, "templates": 0}))
    rows.sort(key=lambda a: a["scores"]["overall"], reverse=True)
    return rows


@app.get("/api/timeline")
def api_timeline(limit: int = 25):
    rows = list(coll("conversations").find().sort("at", -1).limit(limit))
    for r in rows:
        r["_id"] = str(r["_id"])
        if "at" in r:
            r["at"] = r["at"].isoformat()
    return rows


@app.get("/api/preferences")
def api_preferences():
    pref = coll("preferences").find_one(
        {"user_id": "U_stephen"}, sort=[("version", -1)])
    if not pref:
        return {}
    pref["_id"] = str(pref["_id"])
    pref.pop("taste_vector", None)
    if "as_of" in pref:
        pref["as_of"] = pref["as_of"].isoformat()
    pref["taste_versions_seen"] = coll("preferences").count_documents(
        {"user_id": "U_stephen"})
    return pref


@app.get("/audio/{filename}")
def audio(filename: str):
    p = AUDIO_DIR / filename
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/livekit-token")
async def issue_livekit_token(identity: str = "guest"):
    """Issue a short-lived LiveKit JWT so an anonymous browser can join Lettr's
    room. Used by the public frontend on Vercel to talk to the agent worker."""
    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]
    lk_url = os.environ["LIVEKIT_URL"]
    room = "lettr-room"
    token = (
        livekit_api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(livekit_api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
        ))
        .with_ttl(timedelta(minutes=30))
        .to_jwt()
    )
    # Dispatch the Lettr agent to the room (LiveKit Agents v1.x explicit dispatch).
    # Safe to call even if a dispatch already exists — duplicates are ignored by
    # the server. Uses agent_name="lettr" matching WorkerOptions in agent/main.py.
    try:
        async with livekit_api.LiveKitAPI(
            url=lk_url, api_key=api_key, api_secret=api_secret
        ) as lk:
            await lk.agent_dispatch.create_dispatch(
                livekit_api.CreateAgentDispatchRequest(
                    room=room,
                    agent_name="lettr",
                )
            )
    except Exception:
        pass  # Best-effort: worker will still join once the room is created
    return {
        "token": token,
        "url": lk_url,
        "room": room,
        "identity": identity,
    }


@app.post("/demo/timelapse")
def timelapse(days: int = 5):
    # In a real demo run we'd push the simulator's clock forward. For the MVP
    # we just kick the simulator to drain its queue several times in quick
    # succession.
    drained = 0
    for _ in range(days * 5):
        drained += simulator.step()
    return {"ok": True, "drained": drained}
