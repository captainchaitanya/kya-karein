import asyncio
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv()

OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
RAWG_API_KEY = os.getenv("RAWG_API_KEY", "")

print(f"[startup] OMDB key loaded: {bool(OMDB_API_KEY)} | RAWG key loaded: {bool(RAWG_API_KEY)}")

BASE_DIR = Path(__file__).parent
TIMEOUT = 6

app = FastAPI(title="Kya Karein")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE = {"version": 0, "updated": None, "mood": "", "tags": [], "picks": []}

FIELDS = [
    "mood_summary", "mood_tags",
    "book_title", "book_author", "book_why",
    "movie_title", "movie_why",
    "show_title", "show_why",
    "game_title", "game_why",
]


def clean(v):
    """Return a usable string, or None for empty / N/A values."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.upper() == "N/A":
        return None
    return s


def year_of(v):
    s = clean(v)
    if not s:
        return None
    return s[:4] if s[:4].isdigit() else s


def log_resp(name, r):
    def mask(s):
        return s.replace(OMDB_API_KEY or "\0", "***").replace(RAWG_API_KEY or "\0", "***")
    print(mask(f"[{name}] status={r.status_code} url={r.request.url}"))
    print(mask(f"[{name}] body[:300]={r.text[:300]!r}"))


def base_card(kind, title, why, author=None):
    return {
        "kind": kind,
        "title": title or "",
        "year": None,
        "author": author,
        "image": None,
        "link": None,
        "why": why or "",
        "blurb": None,
    }


# ---------- Lookups (each returns a card, never raises) ----------

async def omdb_lookup(client, title, media_type):
    r = await client.get(
        "https://www.omdbapi.com/",
        params={"apikey": OMDB_API_KEY, "t": title, "type": media_type},
    )
    log_resp(f"OMDb {media_type}", r)
    d = r.json()
    if str(d.get("Response")).lower() != "true":
        return None
    imdb_id = clean(d.get("imdbID"))
    return {
        "title": clean(d.get("Title")),
        "year": year_of(d.get("Year")),
        "image": clean(d.get("Poster")),
        "link": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None,
        "blurb": clean(d.get("Plot")),
    }


async def tvmaze_lookup(client, title):
    r = await client.get("https://api.tvmaze.com/singlesearch/shows", params={"q": title})
    d = r.json()
    img = d.get("image") or {}
    return {
        "title": clean(d.get("name")),
        "year": year_of(d.get("premiered")),
        "image": clean(img.get("original") or img.get("medium")),
        "link": clean(d.get("url")),
    }


async def get_movie(client, title, why):
    card = base_card("Movie", title, why)
    try:
        if not title:
            return card
        info = await omdb_lookup(client, title, "movie")
        if info:
            card["title"] = info["title"] or title
            card["year"] = info["year"]
            card["image"] = info["image"]
            card["link"] = info["link"]
            card["blurb"] = info["blurb"]
    except Exception as e:
        print(f"[movie lookup failed] {e!r}")
    return card


async def get_show(client, title, why):
    card = base_card("Show", title, why)
    if not title:
        return card
    try:
        info = await omdb_lookup(client, title, "series")
        if info:
            card["title"] = info["title"] or title
            card["year"] = info["year"]
            card["image"] = info["image"]
            card["link"] = info["link"]
            card["blurb"] = info["blurb"]
    except Exception as e:
        print(f"[show omdb lookup failed] {e!r}")
    if not card["image"]:
        try:
            tv = await tvmaze_lookup(client, title)
            if tv:
                if not card["year"]:
                    card["year"] = tv["year"]
                card["image"] = tv["image"]
                card["link"] = card["link"] or tv["link"]
                if card["title"] == title and tv["title"]:
                    card["title"] = tv["title"]
        except Exception as e:
            print(f"[show tvmaze lookup failed] {e!r}")
    return card


async def get_book(client, title, author, why):
    card = base_card("Book", title, why, author=author)
    try:
        if not title:
            return card
        params = {"title": title, "limit": 1}
        if author:
            params["author"] = author
        r = await client.get("https://openlibrary.org/search.json", params=params)
        docs = r.json().get("docs") or []
        if docs:
            d = docs[0]
            card["title"] = clean(d.get("title")) or title
            card["year"] = year_of(d.get("first_publish_year"))
            names = d.get("author_name") or []
            if names:
                card["author"] = clean(names[0]) or author
            if d.get("cover_i"):
                card["image"] = f"https://covers.openlibrary.org/b/id/{d['cover_i']}-L.jpg"
            if d.get("key"):
                card["link"] = f"https://openlibrary.org{d['key']}"
    except Exception as e:
        print(f"[book lookup failed] {e!r}")
    return card


async def get_game(client, title, why):
    card = base_card("Game", title, why)
    try:
        if not title:
            return card
        r = await client.get(
            "https://api.rawg.io/api/games",
            params={"key": RAWG_API_KEY, "search": title, "page_size": 1},
        )
        log_resp("RAWG", r)
        results = r.json().get("results") or []
        if results:
            d = results[0]
            card["title"] = clean(d.get("name")) or title
            card["year"] = year_of(d.get("released"))
            card["image"] = clean(d.get("background_image"))
            if d.get("slug"):
                card["link"] = f"https://rawg.io/games/{d['slug']}"
    except Exception as e:
        print(f"[game lookup failed] {e!r}")
    return card


async def safe(coro, fallback):
    """Hard 6s cap per lookup; fall back to the plain card on anything."""
    try:
        return await asyncio.wait_for(coro, timeout=TIMEOUT)
    except Exception as e:
        print(f"[lookup timeout/error] {e!r}")
        return fallback


# ---------- Routes ----------

@app.post("/api/picks")
async def post_picks(request: Request):
    data = {}
    # Merge query params and JSON body (body wins on conflicts)
    data.update(dict(request.query_params))
    try:
        body = await request.json()
        if isinstance(body, dict):
            data.update(body)
    except Exception:
        pass

    print("---- /api/picks incoming ----")
    print(data)

    f = {k: (clean(data.get(k)) or "") for k in FIELDS}

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        picks = await asyncio.gather(
            safe(get_book(client, f["book_title"], f["book_author"], f["book_why"]),
                 base_card("Book", f["book_title"], f["book_why"], f["book_author"] or None)),
            safe(get_movie(client, f["movie_title"], f["movie_why"]),
                 base_card("Movie", f["movie_title"], f["movie_why"])),
            safe(get_show(client, f["show_title"], f["show_why"]),
                 base_card("Show", f["show_title"], f["show_why"])),
            safe(get_game(client, f["game_title"], f["game_why"]),
                 base_card("Game", f["game_title"], f["game_why"])),
        )

    STATE["version"] += 1
    STATE["updated"] = time.time()
    STATE["mood"] = f["mood_summary"]
    STATE["tags"] = [t.strip() for t in f["mood_tags"].split(",") if t.strip()]
    STATE["picks"] = list(picks)

    return {"result": "Picks are now on the user's screen. Tell them briefly, one short line each."}


@app.get("/api/latest")
async def latest():
    return STATE


@app.post("/api/reset")
async def reset():
    STATE["version"] += 1
    STATE["updated"] = time.time()
    STATE["mood"] = ""
    STATE["tags"] = []
    STATE["picks"] = []
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")
