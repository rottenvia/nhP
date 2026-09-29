"""
Metadata provider for the player.

All external catalog lookups (TMDB for movies/shows, Jikan/MyAnimeList for anime)
go through this module instead of the WebView. Benefits:

* one normalized item shape for every source, so the UI renders every card the same way;
* an in-memory + on-disk cache, so re-opening the app or a title page is instant;
* a polite rate limiter for Jikan (3 req/s) with automatic retry on 429;
* no CORS / mixed-content surprises inside WebView2.

Only the standard library is used so the packaged EXE has no new dependencies.
"""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

# Public TMDB key that already shipped inside the old frontend. Can be overridden in keys.json.
DEFAULT_TMDB_KEY = "3d1cb94d909aab088231f5af899dffdc"
TMDB_IMG = "https://image.tmdb.org/t/p/"

_lock = threading.Lock()
_mem_cache = {}
_disk_cache_path = None
_disk_dirty = False
_last_jikan_call = 0.0
_jikan_lock = threading.Lock()
_get_keys = lambda: {}  # replaced by app.py

CACHE_TTL = {
    "search": 6 * 3600,
    "details": 24 * 3600,
    "trending": 3 * 3600,
    "relations": 7 * 24 * 3600,
    "episodes": 12 * 3600,
    "season": 24 * 3600,
}


def configure(data_dir, keys_getter):
    """Called once by app.py: where to persist the cache and how to read keys.json."""
    global _disk_cache_path, _get_keys
    _get_keys = keys_getter
    try:
        os.makedirs(data_dir, exist_ok=True)
        _disk_cache_path = os.path.join(data_dir, "metadata_cache.json")
        if os.path.exists(_disk_cache_path):
            with open(_disk_cache_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                now = time.time()
                for k, v in loaded.items():
                    if isinstance(v, dict) and v.get("exp", 0) > now:
                        _mem_cache[k] = v
    except Exception:
        pass


def _flush_disk_cache():
    global _disk_dirty
    if not _disk_cache_path or not _disk_dirty:
        return
    try:
        with _lock:
            snapshot = {k: v for k, v in _mem_cache.items() if v.get("exp", 0) > time.time()}
            _disk_dirty = False
        tmp = _disk_cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False)
        os.replace(tmp, _disk_cache_path)
    except Exception:
        pass


def _cache_get(key):
    with _lock:
        entry = _mem_cache.get(key)
        if entry and entry.get("exp", 0) > time.time():
            return entry.get("data")
    return None


def _cache_set(key, data, ttl):
    global _disk_dirty
    with _lock:
        _mem_cache[key] = {"exp": time.time() + ttl, "data": data}
        _disk_dirty = True
    threading.Timer(2.0, _flush_disk_cache).start()


def _http_json(url, timeout=12, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "ModernPlayer/2.0", "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _jikan(path, params=None, retries=3):
    """Jikan v4 with 3 req/s throttle and 429 retry."""
    global _last_jikan_call
    url = "https://api.jikan.moe/v4" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(retries + 1):
        with _jikan_lock:
            wait = 0.36 - (time.time() - _last_jikan_call)
            if wait > 0:
                time.sleep(wait)
            _last_jikan_call = time.time()
        try:
            return _http_json(url)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(0.8 * (attempt + 1))
                continue
            raise
    return {}


def _tmdb_key():
    try:
        keys = _get_keys() or {}
        return (keys.get("TMDB_API_KEY") or "").strip() or DEFAULT_TMDB_KEY
    except Exception:
        return DEFAULT_TMDB_KEY


def _tmdb(path, params=None):
    p = {"api_key": _tmdb_key()}
    p.update(params or {})
    return _http_json("https://api.themoviedb.org/3" + path + "?" + urllib.parse.urlencode(p))


def _year(s):
    m = re.search(r"(19|20)\d{2}", str(s or ""))
    return int(m.group(0)) if m else None


# ────────────────────────── normalizers ──────────────────────────

def _norm_anime(a):
    images = (a.get("images") or {}).get("jpg") or {}
    titles = []
    for t in a.get("titles") or []:
        if t.get("title") and t["title"] not in titles:
            titles.append(t["title"])
    for k in ("title", "title_english", "title_japanese"):
        if a.get(k) and a[k] not in titles:
            titles.append(a[k])
    aired = a.get("aired") or {}
    status = (a.get("status") or "").lower()
    if "airing" in status and "not" not in status and "finished" not in status:
        status_norm = "airing"
    elif "not yet" in status:
        status_norm = "upcoming"
    else:
        status_norm = "finished"
    return {
        "id": a.get("mal_id"),
        "source": "jikan",
        "category": "anime",
        "title": a.get("title_english") or a.get("title") or "",
        "title_original": a.get("title_japanese") or a.get("title") or "",
        "all_titles": titles,
        "poster": images.get("large_image_url") or images.get("image_url") or "",
        "backdrop": "",
        "year": a.get("year") or _year(aired.get("from")),
        "synopsis": (a.get("synopsis") or "").replace("[Written by MAL Rewrite]", "").strip(),
        "status": status_norm,
        "status_text": a.get("status") or "",
        "type": a.get("type") or "TV",
        "episodes": a.get("episodes") or 0,
        "score": a.get("score"),
        "genres": [g.get("name") for g in (a.get("genres") or []) if g.get("name")],
        "studio": ", ".join(s.get("name") for s in (a.get("studios") or []) if s.get("name")),
        "source_material": a.get("source") or "",
        "aired_from": aired.get("from"),
        "broadcast": (a.get("broadcast") or {}).get("string") or "",
        "url": a.get("url") or "",
    }


def _norm_tmdb(m, category, details=None):
    d = details or {}
    is_movie = category == "movie"
    title = m.get("title") if is_movie else m.get("name")
    orig = m.get("original_title") if is_movie else m.get("original_name")
    date = m.get("release_date") if is_movie else m.get("first_air_date")
    status_raw = (d.get("status") or "").lower()
    if is_movie:
        status = "finished" if status_raw in ("released", "") else "upcoming"
    else:
        status = "airing" if d.get("in_production") or status_raw == "returning series" else "finished"
    seasons = []
    for s in d.get("seasons") or []:
        if s.get("season_number", 0) > 0:
            seasons.append({"season": s.get("season_number"), "episodes": s.get("episode_count") or 0, "name": s.get("name") or "", "air_date": s.get("air_date")})
    episodes = 1 if is_movie else (d.get("number_of_episodes") or sum(s["episodes"] for s in seasons) or 0)
    return {
        "id": m.get("id"),
        "source": "tmdb",
        "category": category,
        "title": title or orig or "",
        "title_original": orig or title or "",
        "all_titles": list(dict.fromkeys(t for t in [title, orig] if t)),
        "poster": (TMDB_IMG + "w500" + m["poster_path"]) if m.get("poster_path") else "",
        "backdrop": (TMDB_IMG + "w1280" + m["backdrop_path"]) if m.get("backdrop_path") else "",
        "year": _year(date),
        "synopsis": m.get("overview") or "",
        "status": status,
        "status_text": d.get("status") or "",
        "type": "Movie" if is_movie else "TV",
        "episodes": episodes,
        "seasons": seasons,
        "score": round(float(m.get("vote_average") or 0), 1) or None,
        "genres": [g.get("name") for g in (d.get("genres") or []) if g.get("name")],
        "studio": ", ".join(n.get("name") for n in (d.get("networks") or d.get("production_companies") or [])[:2] if n.get("name")),
        "runtime": d.get("runtime") or ((d.get("episode_run_time") or [None])[0]),
        "next_episode": d.get("next_episode_to_air"),
        "url": "",
    }


# ────────────────────────── public API ──────────────────────────

def search(category, query, lang="en-US", limit=24):
    category = (category or "anime").lower()
    query = (query or "").strip()
    if not query:
        return {"status": "success", "items": []}
    key = f"search:{category}:{lang}:{query.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return {"status": "success", "items": cached, "cached": True}
    items = []
    try:
        if category == "anime":
            data = _jikan("/anime", {"q": query, "limit": min(limit, 25), "sfw": "false"})
            items = [_norm_anime(a) for a in data.get("data") or []]
        elif category == "movie":
            data = _tmdb("/search/movie", {"query": query, "language": lang, "include_adult": "false"})
            items = [_norm_tmdb(m, "movie") for m in (data.get("results") or [])[:limit]]
        else:
            data = _tmdb("/search/tv", {"query": query, "language": lang, "include_adult": "false"})
            items = [_norm_tmdb(m, "show") for m in (data.get("results") or [])[:limit]]
    except Exception as e:
        return {"status": "error", "message": str(e), "items": []}
    items = [i for i in items if i.get("title")]
    _cache_set(key, items, CACHE_TTL["search"])
    return {"status": "success", "items": items}


def details(category, item_id, lang="en-US"):
    category = (category or "anime").lower()
    key = f"details:{category}:{lang}:{item_id}"
    cached = _cache_get(key)
    if cached is not None:
        return {"status": "success", "item": cached, "cached": True}
    try:
        if category == "anime":
            data = _jikan(f"/anime/{int(item_id)}/full")
            item = _norm_anime(data.get("data") or {})
        elif category == "movie":
            d = _tmdb(f"/movie/{int(item_id)}", {"language": lang})
            item = _norm_tmdb(d, "movie", d)
        else:
            d = _tmdb(f"/tv/{int(item_id)}", {"language": lang})
            item = _norm_tmdb(d, "show", d)
    except Exception as e:
        return {"status": "error", "message": str(e)}
    _cache_set(key, item, CACHE_TTL["details"])
    return {"status": "success", "item": item}


def trending(category="anime", lang="en-US"):
    category = (category or "anime").lower()
    key = f"trending:{category}:{lang}"
    cached = _cache_get(key)
    if cached is not None:
        return {"status": "success", "items": cached, "cached": True}
    try:
        if category == "anime":
            data = _jikan("/top/anime", {"limit": 24, "filter": "airing"})
            items = [_norm_anime(a) for a in data.get("data") or []]
        elif category == "movie":
            data = _tmdb("/trending/movie/week", {"language": lang})
            items = [_norm_tmdb(m, "movie") for m in (data.get("results") or [])[:24]]
        else:
            data = _tmdb("/trending/tv/week", {"language": lang})
            items = [_norm_tmdb(m, "show") for m in (data.get("results") or [])[:24]]
    except Exception as e:
        return {"status": "error", "message": str(e), "items": []}
    _cache_set(key, items, CACHE_TTL["trending"])
    return {"status": "success", "items": items}


def anime_relations(mal_id):
    key = f"relations:{mal_id}"
    cached = _cache_get(key)
    if cached is not None:
        return {"status": "success", "relations": cached, "cached": True}
    try:
        data = _jikan(f"/anime/{int(mal_id)}/relations")
        rels = []
        for group in data.get("data") or []:
            for e in group.get("entry") or []:
                if e.get("type") == "anime":
                    rels.append({"relation": group.get("relation"), "id": e.get("mal_id"), "title": e.get("name")})
    except Exception as e:
        return {"status": "error", "message": str(e), "relations": []}
    _cache_set(key, rels, CACHE_TTL["relations"])
    return {"status": "success", "relations": rels}


def anime_episodes(mal_id, page=1):
    key = f"episodes:{mal_id}:{page}"
    cached = _cache_get(key)
    if cached is not None:
        return {"status": "success", **cached, "cached": True}
    try:
        data = _jikan(f"/anime/{int(mal_id)}/episodes", {"page": int(page)})
        eps = []
        for e in data.get("data") or []:
            eps.append({
                "number": e.get("mal_id"),
                "title": e.get("title") or "",
                "title_romanji": e.get("title_romanji") or "",
                "aired": e.get("aired"),
                "filler": bool(e.get("filler")),
                "recap": bool(e.get("recap")),
            })
        pag = data.get("pagination") or {}
        result = {"episodes": eps, "has_next": bool(pag.get("has_next_page")), "last_page": pag.get("last_visible_page") or 1}
    except Exception as e:
        return {"status": "error", "message": str(e), "episodes": []}
    _cache_set(key, result, CACHE_TTL["episodes"])
    return {"status": "success", **result}


def tv_season(tmdb_id, season, lang="en-US"):
    key = f"season:{tmdb_id}:{season}:{lang}"
    cached = _cache_get(key)
    if cached is not None:
        return {"status": "success", "episodes": cached, "cached": True}
    try:
        d = _tmdb(f"/tv/{int(tmdb_id)}/season/{int(season)}", {"language": lang})
        eps = [{
            "number": e.get("episode_number"),
            "season": e.get("season_number"),
            "title": e.get("name") or "",
            "aired": e.get("air_date"),
            "overview": e.get("overview") or "",
            "still": (TMDB_IMG + "w300" + e["still_path"]) if e.get("still_path") else "",
            "runtime": e.get("runtime"),
        } for e in d.get("episodes") or []]
    except Exception as e:
        return {"status": "error", "message": str(e), "episodes": []}
    _cache_set(key, eps, CACHE_TTL["season"])
    return {"status": "success", "episodes": eps}


def franchise(mal_id, max_depth=12):
    """Walks Jikan relations (prequel/sequel/side story) into an ordered watch list."""
    key = f"franchise:{mal_id}"
    cached = _cache_get(key)
    if cached is not None:
        return {"status": "success", "parts": cached, "cached": True}
    seen = set()
    parts = []
    # Walk to the earliest prequel first.
    root = int(mal_id)
    guard = 0
    while guard < max_depth:
        guard += 1
        rel = anime_relations(root).get("relations") or []
        pre = [r for r in rel if (r.get("relation") or "").lower() == "prequel"]
        if not pre:
            break
        root = int(pre[0]["id"])
    # Then walk sequels forward from the root, collecting side stories along the way.
    cur = root
    guard = 0
    while cur and guard < max_depth * 2:
        guard += 1
        if cur in seen:
            break
        seen.add(cur)
        det = details("anime", cur).get("item") or {}
        if det:
            parts.append({"id": cur, "title": det.get("title"), "episodes": det.get("episodes"), "type": det.get("type"), "year": det.get("year"), "poster": det.get("poster"), "relation": "main"})
        rel = anime_relations(cur).get("relations") or []
        for r in rel:
            rl = (r.get("relation") or "").lower()
            if rl in ("side story", "spin-off", "alternative version", "summary", "other") and r["id"] not in seen:
                d2 = details("anime", r["id"]).get("item") or {}
                if d2 and d2.get("type") not in ("Music",):
                    seen.add(r["id"])
                    parts.append({"id": r["id"], "title": d2.get("title"), "episodes": d2.get("episodes"), "type": d2.get("type"), "year": d2.get("year"), "poster": d2.get("poster"), "relation": rl})
        seq = [r for r in rel if (r.get("relation") or "").lower() == "sequel" and r["id"] not in seen]
        cur = int(seq[0]["id"]) if seq else None
    _cache_set(key, parts, CACHE_TTL["relations"])
    return {"status": "success", "parts": parts}
