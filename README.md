# Kya Karein

Talk to it like a friend about how you feel. It picks the right book, movie, show and game for your mood tonight, in Hinglish.

## Live page

https://kya-karein.onrender.com

First load may take ~50s on free hosting (the server sleeps when idle).

## How it works

```
Phone call
   |
   v
Bolna voice agent (Deepgram STT, GPT-4.1, ElevenLabs voice)
   |
   v  show_picks function (POST /api/picks)
FastAPI on Render
   |
   v
OMDb / TVMaze / Open Library / RAWG   (posters, years, links)
   |
   v
Live page (polls /api/latest, shows the 4 picks while you're still on the call)
```

## Tech stack

- Voice: Bolna, Deepgram (STT), GPT-4.1 (LLM), ElevenLabs (TTS)
- Backend: Python 3, FastAPI, uvicorn, httpx, python-dotenv
- Frontend: plain HTML, CSS and vanilla JS (no build step)
- Data: OMDb, TVMaze, Open Library, RAWG
- Hosting: Render

## Run locally

```
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
```

Fill in `.env`:

```
OMDB_API_KEY=your_key
RAWG_API_KEY=your_key
```

Then start the server and open http://localhost:8000:

```
uvicorn main:app --reload
```

Restart the server after editing `.env`, because `--reload` only watches `.py` files.

## What's next

- Taste memory: remember what you liked across calls
- OTT availability: show where each pick is streaming
- Group watch-party mode: blend several people's moods
- Inbound number: call in directly instead of the agent calling out
