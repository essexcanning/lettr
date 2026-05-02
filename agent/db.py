"""MongoDB client + helpers shared by the agent."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


@lru_cache(maxsize=1)
def get_db() -> Database:
    client = MongoClient(os.environ["MONGODB_URI"])
    return client[os.environ.get("MONGODB_DB", "lettr")]


def now() -> datetime:
    return datetime.now(timezone.utc)


def coll(name: str) -> Collection:
    return get_db()[name]
