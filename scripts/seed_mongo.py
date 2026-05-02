"""
seed_mongo.py — One-shot seed of the Lettr MongoDB Atlas database.

Run once after creating your Atlas cluster:
    python scripts/seed_mongo.py

Reads:
    data/listings.json
    data/letting_agents.json

Writes to MongoDB collections:
    users, preferences, listings, letting_agents, lettr_tasks, conversations
And creates the Atlas Vector Search indexes for `preferences.taste_vector`
and `listings.embedding`.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

import voyageai

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DB = os.environ.get("MONGODB_DB", "lettr")
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
VOYAGE_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-3-large")

EMBED_DIMS = 1024


def now() -> datetime:
    return datetime.now(timezone.utc)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed via Voyage AI. Falls back to a deterministic dummy vector if the
    Voyage key isn't set yet (so the seed script still works for local dev)."""
    if VOYAGE_API_KEY:
        client = voyageai.Client(api_key=VOYAGE_API_KEY)
        result = client.embed(texts, model=VOYAGE_MODEL, input_type="document")
        return result.embeddings
    print("⚠️  VOYAGE_API_KEY not set — using deterministic dummy vectors. "
          "Re-run the seed once you've added the key.")
    import hashlib
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        # turn 32 bytes into 1024 floats by repeating + scaling
        seed = [b / 255.0 - 0.5 for b in h]
        out.append((seed * (EMBED_DIMS // len(seed) + 1))[:EMBED_DIMS])
    return out


def listing_text(listing: dict) -> str:
    return (
        f"{listing['title']}. {listing['area']} (zone {listing['zone']}). "
        f"£{listing['price_pcm']}/mo, {listing['bedrooms']} bed. "
        f"{listing['description']} Light: {listing['light']}. Noise: {listing['noise']}."
    )


def upsert_listings(db, listings: list[dict]) -> None:
    print(f"Embedding {len(listings)} listings...")
    embs = embed([listing_text(l) for l in listings])
    docs = []
    for l, emb in zip(listings, embs):
        d = dict(l)
        d["_id"] = l["id"]
        d["embedding"] = emb
        d["ingested_at"] = now()
        docs.append(d)
    db.listings.delete_many({})
    db.listings.insert_many(docs)
    print(f"  inserted {len(docs)} listings")


def upsert_letting_agents(db, agents: list[dict]) -> None:
    docs = []
    for a in agents:
        b = a["behaviour"]
        scores = {
            "responsiveness": round(1.0 - min(b["response_delay_hours"] / 96, 1.0), 2),
            "honesty": b["honesty_score"],
            "reliability": b["viewings_kept_rate"],
        }
        scores["overall"] = round(sum(scores.values()) / 3, 2)
        flags = []
        if b["ghost_probability"] > 0.5:
            flags.append("chronic_ghoster")
        if b["honesty_score"] < 0.5:
            flags.append("low_honesty")
        docs.append({
            "_id": a["id"],
            "agent_name": a["agent_name"],
            "agency": a["agency"],
            "phone": a["phone"],
            "email": a["email"],
            "persona": a["persona"],
            "stats": {
                "total_enquiries": 0,
                "replies": 0,
                "ghost_count": 0,
                "median_response_hours": b["response_delay_hours"],
                "viewings_booked": 0,
                "viewings_kept": 0,
                "voicemails_left": 0,
                "voicemails_answered": 0,
            },
            "scores": scores,
            "flags": flags,
            "templates": a["templates"],
            "behaviour_seed": b,
            "notes": a.get("notes", ""),
            "last_interaction_at": None,
        })
    db.letting_agents.delete_many({})
    db.letting_agents.insert_many(docs)
    print(f"  inserted {len(docs)} letting agents")


def seed_user_and_preferences(db) -> None:
    db.users.update_one(
        {"_id": "U_stephen"},
        {"$set": {
            "_id": "U_stephen",
            "name": "Stephen",
            "email": "stephen@lettr.demo",
            "phone": "+44 7000 000 000",
            "calendar_busy": [],
            "created_at": now(),
        }},
        upsert=True,
    )
    nl = ("1-bed flat in zones 1-2, under £2400 per month, by mid-June 2026, "
          "good natural light, quiet street, would prefer pet-friendly.")
    taste = embed([nl])[0]
    db.preferences.delete_many({"user_id": "U_stephen"})
    db.preferences.insert_one({
        "user_id": "U_stephen",
        "version": 1,
        "as_of": now(),
        "natural_language": nl,
        "structured": {
            "min_bedrooms": 1,
            "max_bedrooms": 1,
            "max_price_pcm": 2400,
            "preferred_zones": [1, 2],
            "available_by": "2026-06-15",
            "must_haves": ["good_light", "quiet_street"],
            "nice_to_haves": ["balcony", "pet_friendly"],
            "deal_breakers": ["high_noise"],
        },
        "taste_vector": taste,
        "feedback_log": [],
    })
    print("  seeded user + preferences")


def ensure_vector_indexes(db) -> None:
    """Create Atlas Vector Search indexes (idempotent)."""
    for coll, field in [("listings", "embedding"), ("preferences", "taste_vector")]:
        idx_name = f"{coll}_vector_idx"
        try:
            existing = list(db[coll].list_search_indexes())
            if any(i.get("name") == idx_name for i in existing):
                print(f"  index {idx_name} already exists")
                continue
            db[coll].create_search_index({
                "name": idx_name,
                "type": "vectorSearch",
                "definition": {
                    "fields": [{
                        "type": "vector",
                        "path": field,
                        "numDimensions": EMBED_DIMS,
                        "similarity": "cosine",
                    }],
                },
            })
            print(f"  created index {idx_name}")
        except OperationFailure as e:
            print(f"  ⚠️  could not create {idx_name}: {e}")


def main() -> int:
    print(f"Connecting to MongoDB ({MONGODB_DB})…")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    db = client[MONGODB_DB]

    listings = json.loads((ROOT / "data" / "listings.json").read_text())
    agents = json.loads((ROOT / "data" / "letting_agents.json").read_text())

    upsert_letting_agents(db, agents)
    upsert_listings(db, listings)
    seed_user_and_preferences(db)
    ensure_vector_indexes(db)

    print("\n✅ Seed complete.")
    print(f"   users: {db.users.count_documents({})}")
    print(f"   preferences: {db.preferences.count_documents({})}")
    print(f"   listings: {db.listings.count_documents({})}")
    print(f"   letting_agents: {db.letting_agents.count_documents({})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
