"""Letting-agent simulator.

In production Lettr would interact with real estate agents over real email.
For the hackathon demo we drive the world ourselves: each fake agent has a
behaviour profile that determines how (and whether) they reply.

The simulator runs in a loop, picks up `lettr_tasks` of kind
`evaluate_agent_response`, and decides what the agent does:

  - reply quickly with a useful response
  - reply with a vague brush-off
  - say nothing (ghost)

It also handles the response to a voicemail, since most agents respond to
voicemail even if they ignore email.

Designed to feed the time-lapse demo mode: increase TIME_COMPRESSION and the
whole simulated week happens in 60 seconds.
"""
from __future__ import annotations

import os
import random
import time
from datetime import timedelta

from .db import coll, now
from .tools import recompute_scores


TIME_COMPRESSION = float(os.environ.get("LETTR_TIME_COMPRESSION", "1.0"))


def _maybe_reply_to_email(agent: dict, listing: dict, attempts: int) -> str | None:
    """Returns reply body, or None if the agent ghosts this round."""
    b = agent["behaviour_seed"]
    # Higher attempt count → ghoster eventually replies
    ghost_chance = max(b["ghost_probability"] - (attempts * 0.2), 0)
    if random.random() < ghost_chance:
        return None
    return agent["templates"].get("first_response")


def _reply_to_voicemail(agent: dict) -> str | None:
    if not agent["behaviour_seed"]["responds_to_voicemail"]:
        return None
    return agent["templates"].get("after_voicemail") or agent["templates"]["first_response"]


def step() -> int:
    """One simulator tick. Returns number of tasks processed."""
    due = list(coll("lettr_tasks").find({
        "status": "queued",
        "scheduled_for": {"$lte": now()},
    }).limit(10))

    for t in due:
        coll("lettr_tasks").update_one(
            {"_id": t["_id"]},
            {"$set": {"status": "in_flight", "last_attempt_at": now()}},
        )
        kind = t["kind"]
        if kind == "evaluate_agent_response":
            _handle_email_evaluation(t)
        elif kind == "evaluate_voicemail_response":
            _handle_voicemail_evaluation(t)
        else:
            coll("lettr_tasks").update_one(
                {"_id": t["_id"]}, {"$set": {"status": "done"}})

    return len(due)


def _handle_email_evaluation(task: dict) -> None:
    agent_id = task["target"]["agent_id"]
    listing_id = task["target"]["listing_id"]
    agent = coll("letting_agents").find_one({"_id": agent_id})
    listing = coll("listings").find_one({"_id": listing_id})
    body = _maybe_reply_to_email(agent, listing, task.get("attempts", 0))

    if body is None:
        # Ghost
        coll("letting_agents").update_one(
            {"_id": agent_id}, {"$inc": {"stats.ghost_count": 1}})
    else:
        coll("conversations").insert_one({
            "user_id": task["user_id"],
            "agent_id": agent_id,
            "listing_id": listing_id,
            "channel": "email",
            "direction": "inbound",
            "body": body,
            "at": now(),
        })
        coll("letting_agents").update_one(
            {"_id": agent_id}, {"$inc": {"stats.replies": 1}})

    recompute_scores(agent_id)
    coll("lettr_tasks").update_one(
        {"_id": task["_id"]}, {"$set": {"status": "done"}})


def _handle_voicemail_evaluation(task: dict) -> None:
    agent_id = task["target"]["agent_id"]
    listing_id = task["target"]["listing_id"]
    agent = coll("letting_agents").find_one({"_id": agent_id})
    body = _reply_to_voicemail(agent)
    if body:
        coll("conversations").insert_one({
            "user_id": task["user_id"],
            "agent_id": agent_id,
            "listing_id": listing_id,
            "channel": "email",
            "direction": "inbound",
            "body": body,
            "at": now(),
        })
        coll("letting_agents").update_one(
            {"_id": agent_id},
            {"$inc": {"stats.replies": 1, "stats.voicemails_answered": 1}},
        )
    recompute_scores(agent_id)
    coll("lettr_tasks").update_one(
        {"_id": task["_id"]}, {"$set": {"status": "done"}})


def run_forever(tick_seconds: float = 1.0) -> None:
    """Background loop. Run in a thread or as a separate process."""
    while True:
        try:
            step()
        except Exception as e:
            print(f"simulator error: {e}")
        time.sleep(tick_seconds / TIME_COMPRESSION)


if __name__ == "__main__":
    print(f"Lettr simulator running (compression x{TIME_COMPRESSION})")
    run_forever()
