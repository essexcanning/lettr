# Lettr

> Your AI letting agent. Voice-first. Chases ghosting estate agents on your behalf. Builds a public reputation database as it works.

Built at the **MongoDB Agentic Evolution Hackathon** (London, 2 May 2026).

## What it does

You speak to Lettr. Lettr listens, asks clarifying questions, then goes off and:

1. Searches London listings against your taste vector.
2. Emails letting agents to schedule viewings.
3. **Calls letting agents (with ElevenLabs voice) when they ghost.**
4. Books viewings into your calendar.
5. Reports back via voice.

Every interaction feeds a **shared reputation database** — over time, no London letting agent can hide their behaviour.

## Theme

**Prolonged Coordination** — multi-step workflows lasting hours/days, with MongoDB as the context engine and durable memory across failures and restarts.

## Architecture

```
You (voice) ── WebRTC ──► LiveKit Agent ──► LangGraph state machine
                                                    │
                  ┌─────────────────────────────────┼─────────────────────────────┐
                  ▼                 ▼                ▼                 ▼          ▼
              Deepgram STT     Fireworks LLM    ElevenLabs TTS    MongoDB Atlas    Tools
                                                                  ├─ Vector Search    │
                                                                  ├─ Checkpointer     │
                                                                  └─ Reputation DB    │
```

## Stack

- **MongoDB Atlas** — Vector Search (taste, listings), LangGraph Checkpointer (agent state), Reputation graph
- **Voyage AI** — embeddings (`voyage-3-large`)
- **LiveKit** — voice pipeline + Agents SDK
- **ElevenLabs** — TTS for the user voice + outbound voicemail to ghosting letting agents
- **Fireworks AI** — fast LLM inference
- **LangGraph + LangSmith** — orchestration and visible tracing
- **Deepgram** — STT

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in keys
python scripts/seed_mongo.py
python -m agent.main dev
```

Then open the LiveKit playground at https://agents-playground.livekit.io and connect with your project URL.

## Hackathon notes

- Public repo: required for finalist eligibility.
- All work in this repo was built on **2 May 2026** at the hackathon.
- Built by Stephen Canning + Lea Rattei.
