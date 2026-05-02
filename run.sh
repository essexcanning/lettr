#!/usr/bin/env bash
set -e

# Replit boot: install deps, seed Mongo if empty, run the dashboard, run the
# LiveKit agent worker as a background process. Tail both into stdout.

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

# Seed only if the database is empty
python - <<'PY'
import os
from pymongo import MongoClient
client = MongoClient(os.environ["MONGODB_URI"])
db = client[os.environ.get("MONGODB_DB", "lettr")]
if db.listings.count_documents({}) == 0:
    print("Seeding empty database…")
    import subprocess; subprocess.check_call(["python", "scripts/seed_mongo.py"])
else:
    print(f"Database has {db.listings.count_documents({})} listings — skipping seed.")
PY

# Start the LiveKit agent worker in the background
python -m agent.main start &

# Foreground the dashboard
exec uvicorn dashboard.server:app --host 0.0.0.0 --port ${PORT:-8000}
