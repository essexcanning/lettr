"""LangGraph state machine for Lettr.

This is the core of the "Prolonged Coordination" theme — the agent's reasoning
state is checkpointed to MongoDB on every transition. Kill the process,
restart it, the agent picks up exactly where it left off.

Shape:
    intake → search → outreach → wait → evaluate → (escalate | book | done)
                                          │
                                          ▼
                                    chase / voicemail
"""
from __future__ import annotations

import os
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, StateGraph, START
from langgraph.checkpoint.mongodb import MongoDBSaver

from . import tools
from .db import get_db


# ------------------------------- state ------------------------------ #

class LettrState(TypedDict, total=False):
    user_id: str
    pending_action: str
    natural_language: str
    last_search_results: list[dict]
    in_flight_listing_id: str
    in_flight_agent_id: str
    chase_attempts: int
    voicemail_left: bool
    notes: list[str]


# ------------------------------- nodes ------------------------------ #

def intake(state: LettrState) -> LettrState:
    """Capture / refresh user preferences. Triggered by voice intake."""
    if state.get("natural_language"):
        tools.update_preferences(state["user_id"], state["natural_language"])
    return {**state, "pending_action": "search"}


def search(state: LettrState) -> LettrState:
    results = tools.search_listings(state["user_id"], k=5)
    return {**state, "last_search_results": results, "pending_action": "outreach"}


def outreach(state: LettrState) -> LettrState:
    """Pick the top-ranked listing and email its letting agent."""
    results = state.get("last_search_results", [])
    if not results:
        return {**state, "pending_action": "done"}
    top = results[0]
    msg = (
        f"Hi — Stephen here, very interested in {top['title']} "
        f"(listing {top['_id']}). Refs ready, can view this week. "
        "Could we set up a viewing?"
    )
    tools.email_letting_agent(state["user_id"], top["_id"], msg)
    return {
        **state,
        "in_flight_listing_id": top["_id"],
        "in_flight_agent_id": top["letting_agent_id"],
        "chase_attempts": 0,
        "voicemail_left": False,
        "pending_action": "wait",
    }


def wait_for_reply(state: LettrState) -> LettrState:
    """Just yield control. The simulator + checkpointing decides what happens."""
    return {**state, "pending_action": "evaluate"}


def evaluate(state: LettrState) -> LettrState:
    """Has the agent replied? If yes, book. If no, escalate.

    Terminates with 'done' after voicemail so the graph yields control back
    to the orchestrator — a fresh invocation later picks up where we left off
    via the MongoDB Checkpointer."""
    db = get_db()
    inbound = db.conversations.find_one({
        "user_id": state["user_id"],
        "agent_id": state["in_flight_agent_id"],
        "listing_id": state["in_flight_listing_id"],
        "direction": "inbound",
    })
    if inbound:
        return {**state, "pending_action": "book"}
    if state.get("voicemail_left"):
        return {**state, "pending_action": "done"}
    attempts = state.get("chase_attempts", 0)
    if attempts >= 2:
        return {**state, "pending_action": "voicemail"}
    return {**state, "pending_action": "chase"}


def chase(state: LettrState) -> LettrState:
    tools.chase_letting_agent(
        state["user_id"], state["in_flight_agent_id"],
        state["in_flight_listing_id"])
    return {
        **state,
        "chase_attempts": state.get("chase_attempts", 0) + 1,
        "pending_action": "wait",
    }


def voicemail(state: LettrState) -> LettrState:
    tools.leave_voicemail(
        state["user_id"], state["in_flight_agent_id"],
        state["in_flight_listing_id"])
    return {**state, "voicemail_left": True, "pending_action": "wait"}


def book(state: LettrState) -> LettrState:
    when = "2026-05-10T10:00:00Z"  # demo: hard-code
    tools.book_viewing(
        state["user_id"], state["in_flight_agent_id"],
        state["in_flight_listing_id"], when)
    return {**state, "pending_action": "done"}


# ----------------------------- routing ------------------------------ #

def _route(state: LettrState) -> str:
    return state.get("pending_action", "done")


# ----------------------------- builder ------------------------------ #

def build_graph():
    saver = MongoDBSaver(
        client=get_db().client,
        db_name=os.environ.get("MONGODB_DB", "lettr"),
        collection_name="langgraph_checkpoints",
    )

    g = StateGraph(LettrState)
    g.add_node("intake", intake)
    g.add_node("search", search)
    g.add_node("outreach", outreach)
    g.add_node("wait", wait_for_reply)
    g.add_node("evaluate", evaluate)
    g.add_node("chase", chase)
    g.add_node("voicemail", voicemail)
    g.add_node("book", book)

    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", _route, {"search": "search"})
    g.add_conditional_edges("search", _route, {"outreach": "outreach", "done": END})
    g.add_conditional_edges("outreach", _route, {"wait": "wait", "done": END})
    g.add_conditional_edges("wait", _route, {"evaluate": "evaluate"})
    g.add_conditional_edges(
        "evaluate", _route,
        {"book": "book", "chase": "chase", "voicemail": "voicemail", "done": END},
    )
    g.add_conditional_edges("chase", _route, {"wait": "wait"})
    g.add_conditional_edges("voicemail", _route, {"wait": "wait"})
    g.add_edge("book", END)

    return g.compile(checkpointer=saver)
