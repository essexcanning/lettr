# Lettr — run guide

> Stephen + Lea, in that order. Open this guide on your phone and tick each block off.

## 0. Once-only setup (15 min)

1. Open this folder in **Cursor / VS Code / Replit** (Replit is easiest — sponsor + free).
2. Make sure `.env` is filled in. Right now the placeholders in `.env` that **must** be replaced are:
   - `MONGODB_URI` — paste the full connection string from Atlas → Connect → Drivers (substituting your DB password `tPQwLRonDWrJbCP8`).
   - `FIREWORKS_API_KEY` — sign up at https://fireworks.ai → API Keys.
   - `VOYAGE_API_KEY` — sign up at https://www.voyageai.com → Dashboard.
   - `ELEVENLABS_API_KEY` — once your free Creator coupon arrives, redeem it then copy the key from https://elevenlabs.io.
   - `DEEPGRAM_API_KEY` — sign up at https://deepgram.com (free tier).
   - `LANGSMITH_API_KEY` — sign up at https://smith.langchain.com.

3. **Allow IP access in Atlas:** Network Access → Add IP → "Allow access from anywhere" (`0.0.0.0/0`). For the hackathon demo only — tighten later.

4. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 1a. Health check (fail-fast — 30 sec)

```bash
python scripts/health_check.py
```

If anything is red, fix it before seeding.

## 1b. Seed MongoDB (1 min)

```bash
python scripts/seed_mongo.py
```

You should see:
```
✅ Seed complete.
   users: 1
   preferences: 1
   listings: 30
   letting_agents: 8
```

## 2. Run the dashboard (one terminal)

```bash
uvicorn dashboard.server:app --reload --port 8000
```

Open http://localhost:8000 — you should see all 8 letting agents with starting scores. Click "Fast-forward 5 days" to see the simulator move.

## 3. Run the voice agent (second terminal)

```bash
python -m agent.main dev
```

Then open https://agents-playground.livekit.io in a browser tab → connect using the project URL `wss://lettr-59cseizy.livekit.cloud` → click the mic icon → talk.

## 4. Demo flow on stage

1. Speak: *"I'm Stephen. I want a 1-bed in zones 1-2, under £2,400, by mid-June, good light, quiet street, pet considered."* Lettr replies via voice.
2. Show the dashboard: taste vector v1, top match is L008 or similar.
3. Say: *"Go ahead and contact them."* Lettr emails the top letting agent.
4. Click "Fast-forward 5 days." Watch reputation scores tick. Watch the chronic_ghoster flag light up on Marcus Hale.
5. **The voicemail moment.** Lettr escalates to voicemail. Audio plays in the timeline. Audience laughs.
6. The agent replies. Viewing booked. Lettr tells you out loud.
7. End on the dashboard: "After one renter. Imagine 10,000."

## 5. Submit

- Public repo: https://github.com/<your-handle>/lettr
- 1-min demo video: record with QuickTime or Loom showing the flow above
- Submission form: https://cerebralvalley.ai/e/mongo-db-london-hackathon/hackathon/submit
- Add Lea as a team member.
- Submit by **17:00**.
