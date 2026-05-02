# Lettr — public web frontend

Single-page voice frontend that talks to a deployed Lettr backend over LiveKit.
Designed to deploy on **Vercel** as a static site (no build step).

## Deploy on Vercel

1. Push this repo to GitHub (`essexcanning/lettr` — already done).
2. In Vercel, click "Add New… → Project" → import `lettr`.
3. Set the **Root Directory** to `web/`.
4. Framework preset: **Other** (no build).
5. Deploy. You get a URL like `https://lettr.vercel.app`.

The page reads `?api=...` if you want to point at a different backend during testing.
By default it calls `https://lettr.replit.app`.

## Local dev

Just open `web/index.html` in a browser, with `?api=http://localhost:8000` if your
dashboard server is running locally.

## What it does

- Fetches a guest LiveKit JWT from `<API_BASE>/api/livekit-token`
- Joins the `lettr-room` room
- Publishes the user's microphone
- Plays back Lettr's TTS audio (ElevenLabs)
- Embeds the reputation dashboard via iframe
