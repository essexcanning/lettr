"""Tools the Lettr agent can call.

Each tool is a function that the LLM can invoke. They all read/write MongoDB
so the state survives restarts and is visible in the dashboard."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from .db import coll, now
from .embeddings import embed


# --------------------------- preferences ---------------------------- #

def update_preferences(user_id: str, natural_language: str,
                       structured: dict | None = None) -> dict:
    """Persist a fresh preferences document and a new taste vector."""
    taste = embed(natural_language)
    latest = coll("preferences").find_one(
        {"user_id": user_id}, sort=[("version", -1)])
    version = (latest["version"] + 1) if latest else 1
    doc = {
        "user_id": user_id,
        "version": version,
        "as_of": now(),
        "natural_language": natural_language,
        "structured": structured or (latest.get("structured") if latest else {}),
        "taste_vector": taste,
        "feedback_log": latest.get("feedback_log", []) if latest else [],
    }
    coll("preferences").insert_one(doc)
    return {"ok": True, "version": version}


def record_reaction(user_id: str, listing_id: str, reaction: str,
                    reason: str | None = None) -> dict:
    """User said yes/no to a listing — fold it into the taste vector next refresh."""
    coll("preferences").update_one(
        {"user_id": user_id},
        {"$push": {"feedback_log": {
            "listing_id": listing_id,
            "reaction": reaction,
            "reason": reason,
            "at": now(),
        }}},
        upsert=False,
        sort=[("version", -1)],
    )
    return {"ok": True}


# ------------------------------- search ----------------------------- #

def search_listings(user_id: str, k: int = 5) -> list[dict]:
    """Vector search listings against the user's current taste, applying
    structured filters (price, zone, beds, deal-breakers)."""
    pref = coll("preferences").find_one(
        {"user_id": user_id}, sort=[("version", -1)])
    if not pref:
        return []
    taste = pref["taste_vector"]
    s = pref.get("structured", {})

    pipeline: list[dict] = [
        {
            "$vectorSearch": {
                "index": "listings_vector_idx",
                "path": "embedding",
                "queryVector": taste,
                "numCandidates": 100,
                "limit": k * 4,
            }
        },
        {
            "$match": {
                "$and": [
                    {"price_pcm": {"$lte": s.get("max_price_pcm", 999_999)}},
                    {"bedrooms": {"$gte": s.get("min_bedrooms", 0)}},
                    {"bedrooms": {"$lte": s.get("max_bedrooms", 99)}},
                    {"zone": {"$in": s.get("preferred_zones", [1, 2, 3, 4, 5, 6])}},
                ]
            }
        },
        {"$limit": k},
        {"$project": {"embedding": 0}},
    ]
    return list(coll("listings").aggregate(pipeline))


# --------------------------- letting agents ------------------------- #

def email_letting_agent(user_id: str, listing_id: str, message: str) -> dict:
    """Send an enquiry email. The simulator decides if/when there's a reply."""
    listing = coll("listings").find_one({"_id": listing_id})
    if not listing:
        return {"ok": False, "error": "unknown listing"}
    agent_id = listing["letting_agent_id"]
    coll("conversations").insert_one({
        "user_id": user_id,
        "agent_id": agent_id,
        "listing_id": listing_id,
        "channel": "email",
        "direction": "outbound",
        "body": message,
        "at": now(),
    })
    coll("letting_agents").update_one(
        {"_id": agent_id},
        {"$inc": {"stats.total_enquiries": 1},
         "$set": {"last_interaction_at": now()}},
    )
    # Schedule the simulator's response evaluation
    coll("lettr_tasks").insert_one({
        "user_id": user_id,
        "kind": "evaluate_agent_response",
        "target": {"agent_id": agent_id, "listing_id": listing_id},
        "status": "queued",
        "scheduled_for": now() + timedelta(seconds=10),  # demo-fast
        "attempts": 0,
        "context": {"original_message": message},
        "created_at": now(),
    })
    return {"ok": True, "agent_id": agent_id}


def chase_letting_agent(user_id: str, agent_id: str, listing_id: str) -> dict:
    """Follow up via email when the agent has gone quiet."""
    coll("conversations").insert_one({
        "user_id": user_id,
        "agent_id": agent_id,
        "listing_id": listing_id,
        "channel": "email",
        "direction": "outbound",
        "subject": "Following up",
        "body": "Hi — just chasing on the flat below, still keen and have refs ready. Stephen.",
        "at": now(),
    })
    return {"ok": True}


def leave_voicemail(user_id: str, agent_id: str, listing_id: str) -> dict:
    """Trigger an ElevenLabs outbound voicemail to a ghosting agent.

    The actual audio is generated by `voicemail.py` and stored as an MP3 the
    dashboard can play. We log the conversation here so the demo shows the
    escalation in real time."""
    from .voicemail import generate_voicemail
    audio_url = generate_voicemail(user_id, agent_id, listing_id)
    coll("conversations").insert_one({
        "user_id": user_id,
        "agent_id": agent_id,
        "listing_id": listing_id,
        "channel": "voicemail",
        "direction": "outbound",
        "body": "Polite voicemail left.",
        "audio_url": audio_url,
        "at": now(),
    })
    coll("letting_agents").update_one(
        {"_id": agent_id},
        {"$inc": {"stats.voicemails_left": 1}},
    )
    return {"ok": True, "audio_url": audio_url}


def book_viewing(user_id: str, agent_id: str, listing_id: str,
                 when_iso: str) -> dict:
    coll("conversations").insert_one({
        "user_id": user_id,
        "agent_id": agent_id,
        "listing_id": listing_id,
        "channel": "email",
        "direction": "outbound",
        "subject": "Viewing booked",
        "body": f"Booking confirmed for {when_iso}. Stephen.",
        "at": now(),
    })
    coll("users").update_one(
        {"_id": user_id},
        {"$push": {"calendar_busy": {
            "type": "viewing",
            "listing_id": listing_id,
            "agent_id": agent_id,
            "at": when_iso,
        }}},
    )
    coll("letting_agents").update_one(
        {"_id": agent_id},
        {"$inc": {"stats.viewings_booked": 1}},
    )
    return {"ok": True}


# ------------------------- reputation graph ------------------------- #

def reputation_dashboard() -> list[dict]:
    """Read the current reputation scoreboard."""
    return list(coll("letting_agents").find(
        {}, {"behaviour_seed": 0, "templates": 0}
    ).sort("scores.overall", -1))


def recompute_scores(agent_id: str) -> None:
    """Recalculate an agent's scores from their stats. Called by the simulator."""
    a = coll("letting_agents").find_one({"_id": agent_id})
    if not a:
        return
    s = a["stats"]
    enquiries = max(s["total_enquiries"], 1)
    bookings = max(s["viewings_booked"], 1)
    new_scores = {
        "responsiveness": round(s["replies"] / enquiries, 2),
        "honesty": a["scores"]["honesty"],  # static for demo
        "reliability": round(s["viewings_kept"] / bookings, 2) if s["viewings_booked"] else a["scores"]["reliability"],
    }
    new_scores["overall"] = round(sum(new_scores.values()) / 3, 2)
    flags = a.get("flags", [])
    if s["ghost_count"] >= 3 and "chronic_ghoster" not in flags:
        flags.append("chronic_ghoster")
    coll("letting_agents").update_one(
        {"_id": agent_id},
        {"$set": {"scores": new_scores, "flags": flags}},
    )
