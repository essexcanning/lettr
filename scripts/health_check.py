"""health_check.py — sanity-check the .env and that every external service answers.

Run before `seed_mongo.py` to catch credential / connectivity issues fast.
    python scripts/health_check.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()


REQUIRED = [
    "MONGODB_URI",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "FIREWORKS_API_KEY",
    "VOYAGE_API_KEY",
    "ELEVENLABS_API_KEY",
    "LANGSMITH_API_KEY",
]


def check_env() -> list[str]:
    issues = []
    for key in REQUIRED:
        v = os.environ.get(key)
        if not v:
            issues.append(f"missing: {key}")
        elif "TODO" in v or "PASTE" in v.upper():
            issues.append(f"placeholder: {key}")
    return issues


def check_mongo() -> str | None:
    try:
        from pymongo import MongoClient
        client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5_000)
        client.admin.command("ping")
        return None
    except Exception as e:
        return f"MongoDB: {type(e).__name__}: {e}"


def check_voyage() -> str | None:
    try:
        import voyageai
        c = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
        r = c.embed(["hello"], model=os.environ.get("VOYAGE_MODEL", "voyage-3-large"))
        if not r.embeddings or len(r.embeddings[0]) != 1024:
            return f"Voyage: unexpected embedding length {len(r.embeddings[0])}"
        return None
    except Exception as e:
        return f"Voyage: {type(e).__name__}: {e}"


def check_fireworks() -> str | None:
    try:
        import httpx
        r = httpx.post(
            "https://api.fireworks.ai/inference/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}"},
            json={
                "model": os.environ.get(
                    "FIREWORKS_MODEL",
                    "accounts/fireworks/models/llama-v3p1-70b-instruct"),
                "messages": [{"role": "user", "content": "say hi"}],
                "max_tokens": 5,
            },
            timeout=20,
        )
        r.raise_for_status()
        return None
    except Exception as e:
        return f"Fireworks: {type(e).__name__}: {e}"


def check_elevenlabs() -> str | None:
    try:
        import httpx
        r = httpx.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            timeout=10,
        )
        r.raise_for_status()
        return None
    except Exception as e:
        return f"ElevenLabs: {type(e).__name__}: {e}"


def main() -> int:
    print("=== Lettr health check ===\n")

    env_issues = check_env()
    if env_issues:
        print("ENV ISSUES:")
        for i in env_issues:
            print(f"  ✗ {i}")
        return 1
    print("✓ env vars present")

    checks = [
        ("MongoDB Atlas", check_mongo),
        ("Voyage AI",     check_voyage),
        ("Fireworks AI",  check_fireworks),
        ("ElevenLabs",    check_elevenlabs),
    ]
    failed = 0
    for name, fn in checks:
        err = fn()
        if err is None:
            print(f"✓ {name}")
        else:
            print(f"✗ {name}: {err}")
            failed += 1

    if failed:
        print(f"\n{failed} check(s) failed. Fix .env or sandbox network access "
              "(Atlas → Network Access → 0.0.0.0/0) and try again.")
        return 1
    print("\nAll green. Run: python scripts/seed_mongo.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
