# Lettr — MongoDB Atlas schema

Database: `lettr` · Cluster: hackathon sandbox · Embeddings: Voyage AI `voyage-3-large` (1024 dims)

## Collections

### 1. `users`
Identifies the renter. One per user; we'll seed Stephen's user for the demo.

```json
{
  "_id": "U_stephen",
  "name": "Stephen",
  "email": "stephen@lettr.demo",
  "phone": "+44 7000 000 000",
  "calendar_busy": [],
  "created_at": ISODate
}
```

### 2. `preferences`
Lettr's evolving understanding of what the user wants. The "Twin."

```json
{
  "_id": ObjectId,
  "user_id": "U_stephen",
  "version": 3,
  "as_of": ISODate,
  "natural_language": "1-bed, zones 1-2, under £2400, by mid-June, good light, quiet street, pet ok",
  "structured": {
    "min_bedrooms": 1,
    "max_bedrooms": 1,
    "max_price_pcm": 2400,
    "preferred_zones": [1, 2],
    "available_by": "2026-06-15",
    "must_haves": ["good_light", "quiet_street"],
    "nice_to_haves": ["balcony", "pet_friendly"],
    "deal_breakers": ["high_noise"]
  },
  "taste_vector": [/* 1024 floats from Voyage AI */],
  "feedback_log": [
    {"listing_id": "L004", "reaction": "loved", "at": ISODate},
    {"listing_id": "L016", "reaction": "rejected", "at": ISODate, "reason": "too dark"}
  ]
}
```

**Vector index:** `preferences_vector_idx` on `taste_vector` (1024 dims, cosine).

### 3. `listings`
Static seeded data for the demo. In production these would be ingested from portals.

```json
{
  "_id": "L001",
  "title": "...",
  "area": "Hackney",
  "postcode": "...",
  "zone": 2,
  "price_pcm": 2150,
  "bedrooms": 1,
  "letting_agent_id": "AG003",
  "description": "...",
  "embedding": [/* 1024 floats */],
  "ingested_at": ISODate
}
```

**Vector index:** `listings_vector_idx` on `embedding` (1024 dims, cosine).

### 4. `letting_agents`
The reputation graph — the "Bigger Idea." Each interaction updates the agent's stats.

```json
{
  "_id": "AG001",
  "agent_name": "Marcus Hale",
  "agency": "Skyline Lettings",
  "phone": "+44 20 7946 0011",
  "email": "marcus.hale@skyline-lettings.demo",
  "persona": "the_ghoster",
  "stats": {
    "total_enquiries": 12,
    "replies": 4,
    "ghost_count": 8,
    "median_response_hours": 96,
    "viewings_booked": 2,
    "viewings_kept": 1,
    "voicemails_left": 5,
    "voicemails_answered": 4
  },
  "scores": {
    "responsiveness": 0.22,
    "honesty": 0.40,
    "reliability": 0.50,
    "overall": 0.31
  },
  "flags": ["chronic_ghoster"],
  "last_interaction_at": ISODate,
  "behaviour_seed": { /* internal — controls simulator timing */ }
}
```

### 5. `lettr_tasks`
The pending-work queue. Survives restarts. The literal manifestation of "Prolonged Coordination."

```json
{
  "_id": ObjectId,
  "user_id": "U_stephen",
  "kind": "chase_letting_agent | book_viewing | follow_up_email | escalate_to_voicemail",
  "target": {"agent_id": "AG001", "listing_id": "L001"},
  "status": "queued | in_flight | done | failed",
  "scheduled_for": ISODate,
  "attempts": 2,
  "last_attempt_at": ISODate,
  "context": {"reason": "no reply for 72h", "prior_messages": [...]},
  "created_at": ISODate
}
```

### 6. `conversations`
Every email/voice interaction logged. Append-only.

```json
{
  "_id": ObjectId,
  "user_id": "U_stephen",
  "agent_id": "AG001",
  "listing_id": "L001",
  "channel": "email | voicemail | sms",
  "direction": "outbound | inbound",
  "subject": "...",
  "body": "...",
  "audio_url": "/audio/voicemail-AG001-001.mp3",
  "at": ISODate,
  "trace_id": "langsmith-trace-id"
}
```

### 7. `langgraph_checkpoints`
Managed by `langgraph-checkpoint-mongodb`. Don't write directly — LangGraph manages it.

This is what lets a judge unplug the laptop, plug it back in, and watch the agent resume mid-task. Theme 1 in three seconds.

## Vector indexes (Atlas Search)

Run once after seeding:

```js
db.preferences.createSearchIndex({
  name: "preferences_vector_idx",
  type: "vectorSearch",
  definition: {
    fields: [{type: "vector", path: "taste_vector", numDimensions: 1024, similarity: "cosine"}]
  }
});

db.listings.createSearchIndex({
  name: "listings_vector_idx",
  type: "vectorSearch",
  definition: {
    fields: [{type: "vector", path: "embedding", numDimensions: 1024, similarity: "cosine"}]
  }
});
```
