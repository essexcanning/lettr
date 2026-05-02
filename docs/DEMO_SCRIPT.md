# Lettr — demo script

> 3 minutes total. 1–2 min Q&A after. Live demo only — no slides per hackathon rules.
>
> **Goal:** make the room *feel* the broken rental market and want Lettr to fix it.
> **Vehicle:** voice + dashboard + the voicemail moment.

## Setup before going on

- Laptop on stage, mirrored to projector.
- Three windows tiled:
  1. **LiveKit Agents Playground** (https://agents-playground.livekit.io) — left third
  2. **Lettr Dashboard** (http://localhost:8000) — middle third
  3. **MongoDB Atlas → Collections** (cloud.mongodb.com) — right third (collapsed unless judge asks)
- Fresh terminal scrollback. LangSmith open in a 4th tab.
- Mic checked. ElevenLabs voice tested.
- `python scripts/seed_mongo.py` re-run to reset state to a clean baseline.

## Script (memorise the bones, not the words)

### 0:00–0:20 — The hook

> "Two months ago I tried to rent a flat in London. I sent twelve enquiries. Four estate agents replied. One showed up to the viewing. So I built Lettr — a voice agent that does the job a London letting agent should do, but for the renter."

[Open palm towards laptop — Lettr is *running.*]

### 0:20–0:50 — The intake

[Click mic on the playground. Speak naturally:]

> "Lettr — I'm looking for a 1-bed in zones 1 and 2, under £2,400 a month, by mid-June, good light, quiet street, would prefer pet-friendly."

Lettr replies in voice. *Don't read the reply over her — let her speak.*

[Switch to the dashboard. Point at the Taste Vector panel.]

> "That natural-language brief just became a 1024-dimension taste vector in MongoDB Atlas. As I react to listings, this vector tightens. Day three, Lettr will know what I want better than I do."

### 0:50–1:30 — The work

[Speak again:]

> "Go ahead and contact the top match."

Lettr emails the letting agent. *Show the timeline event landing on the right.*

[Click "Fast-forward 5 days."]

> "I've moved time forward five days. Watch the reputation graph populate."

[Point at the table. The chronic_ghoster flag lights up on Marcus Hale.]

> "This is what's interesting. Every interaction Lettr has with a letting agent feeds a shared reputation database. Marcus Hale at Skyline Lettings — chronic ghoster. 8 enquiries, 1 reply. Now imagine 10,000 London renters running this. No agent in this city can hide their behaviour."

### 1:30–2:10 — The killer moment

[Voice change — slightly louder, slightly slower:]

> "Marcus has been ghosting Lettr. Three days. Two follow-up emails. Nothing. Lettr decides to escalate."

[Click into the timeline event with the audio player. Press play.]

[Audio plays — Lettr's polite, dryly weary voicemail to Marcus.]

> *"Hi, this is a message for Marcus Hale at Skyline Lettings. This is Lettr calling on behalf of Stephen Canning..."*

[Audience reaction lands. Wait for it. Don't rush.]

> "ElevenLabs voice. The agent didn't just chase by email — it picked up the phone. And in the next refresh, Marcus replies."

[Refresh dashboard. Inbound message from Marcus appears.]

### 2:10–2:40 — The Twin

[Switch to the preferences panel.]

> "Two more things while we're here. The taste vector — version 4 already, having seen 12 listings and learned I hate north of the river. The MongoDB Checkpointer — this whole workflow is durable. I can kill the process right now…"

[Open terminal. Ctrl+C the agent. Restart it.]

> "…restart it, and Lettr picks up exactly where it left off. Theme 1 of this hackathon was Prolonged Coordination. This is what that looks like."

### 2:40–3:00 — The close

[Look up. Stop demoing.]

> "Lettr is built on MongoDB Atlas Vector Search, the LangGraph MongoDB Checkpointer, the LiveKit voice pipeline, ElevenLabs for inbound and outbound voice, and Fireworks for inference. It's running live. We built it today.
>
> The renter's market in London is broken because letting agents have no accountability. We've built the receipt."

[Stop. Smile. Hand to the judges.]

## Q&A — likely questions and the right answers

| Q | A |
|---|---|
| "Doesn't the letting agent get angry?" | "Today they get away with ghosting. Lettr is polite, it's persistent, and every interaction is on the record. That's not aggression — that's accountability." |
| "How do you scale the reputation graph honestly without becoming defamation?" | "We score behaviour, not subjective judgements. Reply rate, viewing-attended rate, listing accuracy. All audit-trailed. We'd consult counsel before going live publicly." |
| "What's the business model?" | "Renter pays a flat fee per search — say, £29. Premium tier adds the voicemail escalation and the reputation alerts. The reputation graph is a moat that compounds." |
| "Why MongoDB?" | "We have a single, evolving agent state — preferences, conversations, tasks, agent reputation. Atlas Vector Search for the search layer; Checkpointer for the durable graph; document model for the agent persona shape that doesn't fit a relational schema." |
| "How is this different from Rightmove etc?" | "They list. We act. They serve the agent. We serve the renter. They have no memory; Lettr's memory grows the longer it runs." |

## What to cut if the clock starts hurting

- The taste vector v1→v4 reveal is nice-to-have. Voicemail is the hill we die on.
- The Checkpointer kill+restart is showy but only if it works first time. Skip if uncertain.
- The dashboard taste-vector reveal is a back-pocket move during Q&A.

## Pre-flight checklist (the moment before going on)

- [ ] Mic check
- [ ] Lettr greeting on demand: speak "Hi" and confirm reply
- [ ] One end-to-end run completed in the last 10 minutes
- [ ] Reputation dashboard open and refreshing
- [ ] One voicemail audio file already pre-rendered in `audio_out/` as backup
- [ ] LangSmith trace from the latest run open in a tab (back-pocket for techy judges)
- [ ] Reset Mongo state (`python scripts/seed_mongo.py`) so the demo starts clean
