# Kya Karein

Tell a voice agent how you feel. It picks one book, one movie, one show and one game for your mood, and they show up on a live web page while you're still on the call.

_Full README coming soon._

## Quick start

```
python -m venv .venv
.venv\Scripts\activate        # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env          # then add your OMDB_API_KEY and RAWG_API_KEY
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000
