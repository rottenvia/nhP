"""
:3 assistant — a real tool-calling agent for the player.

Works with any OpenAI-compatible chat completions endpoint (OpenAI, DeepSeek,
OpenRouter, Groq, LM Studio, Ollama with the OpenAI shim ...). The provider is
chosen in Settings → AI (or keys.json):

    AI_PROVIDER   openai | deepseek | openrouter | groq | custom
    AI_BASE_URL   only for custom, e.g. http://127.0.0.1:1234/v1
    AI_MODEL      e.g. gpt-4o-mini, deepseek-chat, ...
    AI_API_KEY    falls back to OPENAI_API_KEY / DEEPSEEK_API_KEY

The agent loop:
  user message → model → (tool calls → results → model)* → final answer.

Tools either return data to the model (search results, torrent status ...) or
queue a UI command (play this episode, open this view, add to library ...).
UI commands are shipped back to the frontend together with the answer and are
executed there, so the model can act on the app without the backend needing
to know the frontend's in-memory state.

Everything is streamed as JSON events so the chat can show
"searching catalog…", "adding torrent…" while the model works.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

PROVIDERS = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "key_env": "OPENAI_API_KEY"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "key_env": "DEEPSEEK_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini", "key_env": "OPENROUTER_API_KEY"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "key_env": "GROQ_API_KEY"},
    "custom": {"base_url": "http://127.0.0.1:1234/v1", "model": "local-model", "key_env": "AI_API_KEY"},
}

MAX_TOOL_ROUNDS = 10
HISTORY_LIMIT = 40

SYSTEM_PROMPT = """You are :3, the built-in assistant of Modern Player, a desktop media player.
You can actually operate the app through tools. Prefer doing things over explaining how to do them.

What the app has:
- Library: titles the user saved (anime / movies / shows) with episodes linked to local files.
- Catalog: online metadata search (MyAnimeList for anime, TMDB for movies and shows).
- Player: plays local files; supports subtitles, skip intro, next episode.
- Downloader: torrent RAW search (anime via Nyaa; movies/shows via Prowlarr when configured) and an internal torrent engine.
- Merger: matches RAW video + DUB audio files and merges them (with auto-sync) into a dubbed episode.
- DUB Browser: an in-app browser window the user can open on a dub source site. It is user-driven: you can open it, but you cannot browse or download on the user's behalf.
- Watch Together / TV mode: shares playback with friends on the LAN.

Rules:
- Use tools to look things up instead of guessing (library contents, torrent results, metadata).
- When the user asks to watch something that is in the library, play it.
- When the user asks to download something: search torrents, pick the best candidate (quality, size, seeders), and add it. Tell them what you picked and why in one or two lines.
- When something is not possible (no provider configured, file not linked, site requires a manual step) say so plainly and offer the closest thing you can do.
- Keep answers short. No markdown headers. Use the user's language (Russian or English).
- After acting, summarize what you did in one line."""


def _now_ms():
    return int(time.time() * 1000)


class AssistantError(Exception):
    pass


class Assistant:
    def __init__(self, api, keys_getter, db_loader, metadata_module, data_dir, logger=None):
        self.api = api
        self.get_keys = keys_getter
        self.load_db = db_loader
        self.meta = metadata_module
        self.data_dir = data_dir
        self.log = logger or (lambda m: None)
        self._lock = threading.Lock()
        self._history_path = os.path.join(data_dir, "assistant_history.json")
        self.history = self._load_history()

    # ────────────────────────── config ──────────────────────────

    def provider_config(self):
        keys = self.get_keys() or {}
        env = os.environ
        provider = (env.get("AI_PROVIDER") or keys.get("AI_PROVIDER") or "").strip().lower()
        if not provider:
            # Infer from whichever key exists.
            for name in ("openai", "deepseek", "openrouter", "groq"):
                k = PROVIDERS[name]["key_env"]
                if (env.get(k) or keys.get(k)):
                    provider = name
                    break
            provider = provider or "openai"
        base = PROVIDERS.get(provider, PROVIDERS["custom"])
        base_url = (env.get("AI_BASE_URL") or keys.get("AI_BASE_URL") or "").strip() if provider == "custom" else base["base_url"]
        base_url = (base_url or base["base_url"]).rstrip("/")
        model = (env.get("AI_MODEL") or keys.get("AI_MODEL") or "").strip() or base["model"]
        api_key = (env.get("AI_API_KEY") or keys.get("AI_API_KEY") or env.get(base["key_env"]) or keys.get(base["key_env"]) or "").strip()
        return {"provider": provider, "base_url": base_url, "model": model, "api_key": api_key, "configured": bool(api_key) or provider == "custom"}

    def public_config(self):
        cfg = self.provider_config()
        return {k: v for k, v in cfg.items() if k != "api_key"} | {"has_key": bool(cfg["api_key"])}

    # ────────────────────────── history ──────────────────────────

    def _load_history(self):
        try:
            if os.path.exists(self._history_path):
                with open(self._history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data[-HISTORY_LIMIT:]
        except Exception:
            pass
        return []

    def _save_history(self):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            tmp = self._history_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.history[-HISTORY_LIMIT:], f, ensure_ascii=False)
            os.replace(tmp, self._history_path)
        except Exception as e:
            self.log(f"assistant history save failed: {e}")

    def clear_history(self):
        with self._lock:
            self.history = []
            self._save_history()
        return {"status": "success"}

    def get_history(self):
        # Only user/assistant turns are shown in the UI.
        return [m for m in self.history if m.get("role") in ("user", "assistant") and m.get("content")]

    # ────────────────────────── tools ──────────────────────────

    def tool_schemas(self):
        def t(name, desc, props=None, required=None):
            return {"type": "function", "function": {"name": name, "description": desc,
                    "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}
        s = {"type": "string"}
        i = {"type": "integer"}
        return [
            t("get_app_state", "Current app state: what is playing, current view, library counts, downloads in progress, whether ffmpeg/torrent engine/providers are available."),
            t("search_library", "Find titles in the user's library by (partial) name. Returns id, category, title, episodes and which episodes have a linked file.",
              {"query": s}, ["query"]),
            t("get_library_item", "Full details of one library title including episode file links and watching progress.",
              {"id": {"type": ["integer", "string"]}, "category": s}, ["id"]),
            t("search_catalog", "Search online metadata (anime via MyAnimeList, movie/show via TMDB). Returns candidates with id, title, year, episodes, synopsis.",
              {"query": s, "category": {"type": "string", "enum": ["anime", "movie", "show"]}}, ["query", "category"]),
            t("add_to_library", "Add a catalog result to the user's library. Use the id and category from search_catalog.",
              {"id": i, "category": {"type": "string", "enum": ["anime", "movie", "show"]}}, ["id", "category"]),
            t("play", "Play an episode of a library title (or the file where it left off). Opens the player.",
              {"id": {"type": ["integer", "string"]}, "episode": i, "resume": {"type": "boolean"}}, ["id"]),
            t("player_control", "Control the player: play, pause, toggle, next, prev, seek (seconds), volume (0-100), speed (0.5-2), fullscreen, subtitles_toggle.",
              {"action": {"type": "string", "enum": ["play", "pause", "toggle", "next", "prev", "seek", "volume", "speed", "fullscreen", "subtitles_toggle"]}, "value": {"type": "number"}}, ["action"]),
            t("navigate", "Open a view of the app.", {"view": {"type": "string", "enum": ["home", "library", "catalog", "watching", "downloader", "merger", "settings"]}}, ["view"]),
            t("open_title_page", "Open the detailed page of a library title (episodes, watch order, linking).",
              {"id": {"type": ["integer", "string"]}}, ["id"]),
            t("get_watching_progress", "Titles the user is in the middle of watching plus recent history."),
            t("search_torrents", "Search torrent RAW releases. Anime goes to Nyaa; movie/show goes to Prowlarr (needs configuration). Returns ranked candidates with size, seeders, quality tags and links.",
              {"query": s, "kind": {"type": "string", "enum": ["anime", "movie", "show"]}}, ["query"]),
            t("download_torrent", "Add a torrent (magnet or .torrent URL) to the internal download engine. Files land in the raw/ folder.",
              {"magnet_link": s, "torrent_link": s, "title": s}, []),
            t("torrent_status", "Progress of active torrent downloads."),
            t("merger_scan", "Scan raw/ and dub/ folders and return matched RAW+DUB episode pairs."),
            t("merger_merge_all", "Auto-sync and merge every matched RAW+DUB pair. Long operation; runs in the background.",
              {"voice_mode": {"type": "string", "enum": ["off", "demucs"]}, "sync_mode": {"type": "string", "enum": ["auto", "global", "multipoint"]}}),
            t("merger_import_downloads", "Move finished downloads from the Downloads folder into raw/ or dub/.",
              {"target": {"type": "string", "enum": ["raw_folder", "dub_folder"]}}, ["target"]),
            t("open_dub_browser", "Open the in-app DUB browser window for the user (they browse and download manually). Optionally with a title/season/episode hint.",
              {"url": s, "title": s, "season": i, "episode": i}, []),
            t("dub_provider", "Use the user-configured external DUB provider command (DUB_PROVIDER_COMMAND in keys.json). action=list_voices or download.",
              {"action": {"type": "string", "enum": ["list_voices", "download"]}, "title": s, "season": i, "episode": i, "voice": s}, ["action", "title"]),
            t("web_search", "Search the web (Tavily). Use for recommendations, release dates, watch orders and identifying a film from a description.",
              {"query": s}, ["query"]),
            t("open_folder", "Open one of the workflow folders (raw_folder, dub_folder, output_folder, library) in the file manager.",
              {"folder": {"type": "string", "enum": ["raw_folder", "dub_folder", "output_folder", "library"]}}, ["folder"]),
            t("remember", "Save a short fact about the user's preferences for future conversations (e.g. preferred dub studio, favourite genres).",
              {"fact": s}, ["fact"]),
        ]

    # helpers ---------------------------------------------------------------

    def _parse(self, raw):
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {"raw": str(raw)[:2000]}

    def _library(self):
        lib = self._parse(self.load_db("library"))
        items = []
        if isinstance(lib, dict):
            for cat, arr in lib.items():
                for it in arr or []:
                    if isinstance(it, dict):
                        it = dict(it)
                        it.setdefault("category", cat)
                        items.append(it)
        return items

    def _lib_summary(self, it):
        eps = it.get("episodes") or []
        linked = [e.get("num") for e in eps if isinstance(e, dict) and e.get("path")]
        return {
            "id": it.get("id"), "category": it.get("category"), "title": it.get("title"),
            "status": it.get("status"), "episodes_total": len(eps) if eps else it.get("episodes_count") or 0,
            "linked_episodes": linked[:60], "year": it.get("year"),
        }

    def _memory_path(self):
        return os.path.join(self.data_dir, "assistant_memory.json")

    def _memory(self):
        try:
            with open(self._memory_path(), "r", encoding="utf-8") as f:
                m = json.load(f)
            return m if isinstance(m, list) else []
        except Exception:
            return []

    # execution -------------------------------------------------------------

    def run_tool(self, name, args, ctx, ui):
        """Executes one tool. `ui` is the list of UI commands to send back to the frontend."""
        args = args or {}
        api = self.api
        if name == "get_app_state":
            state = dict(ctx or {})
            state["library_counts"] = {}
            for it in self._library():
                c = it.get("category") or "other"
                state["library_counts"][c] = state["library_counts"].get(c, 0) + 1
            try:
                state["downloads"] = self._parse(api.torrent_status()).get("downloads", [])[:10]
            except Exception:
                state["downloads"] = []
            state["ai_provider"] = self.public_config()
            state["memory"] = self._memory()[-10:]
            return state
        if name == "search_library":
            q = (args.get("query") or "").lower().strip()
            out = []
            for it in self._library():
                names = [it.get("title") or ""] + list(it.get("all_titles") or [])
                if not q or any(q in (n or "").lower() for n in names):
                    out.append(self._lib_summary(it))
            return {"results": out[:30], "total": len(out)}
        if name == "get_library_item":
            wanted = str(args.get("id"))
            for it in self._library():
                if str(it.get("id")) == wanted and (not args.get("category") or it.get("category") == args.get("category")):
                    summary = self._lib_summary(it)
                    summary["synopsis"] = (it.get("synopsis") or "")[:600]
                    summary["episodes"] = [{"num": e.get("num"), "linked": bool(e.get("path")), "file": os.path.basename(e.get("path") or "")} for e in (it.get("episodes") or []) if isinstance(e, dict)][:200]
                    prog = self._parse(self.load_db("watching_progress"))
                    if isinstance(prog, list):
                        summary["progress"] = [p for p in prog if str(p.get("id")) == wanted]
                    return summary
            return {"error": "not found in library"}
        if name == "search_catalog":
            res = self.meta.search(args.get("category") or "anime", args.get("query") or "")
            items = [{k: it.get(k) for k in ("id", "category", "title", "title_original", "year", "episodes", "type", "status", "score")} | {"synopsis": (it.get("synopsis") or "")[:200]} for it in res.get("items") or []]
            return {"results": items[:12], "error": res.get("message")}
        if name == "add_to_library":
            det = self.meta.details(args.get("category") or "anime", args.get("id"))
            if det.get("status") != "success":
                return {"error": det.get("message") or "lookup failed"}
            ui.append({"type": "library.add", "item": det["item"]})
            return {"ok": True, "added": det["item"].get("title")}
        if name == "play":
            ui.append({"type": "player.play_library", "id": args.get("id"), "episode": args.get("episode"), "resume": bool(args.get("resume", True))})
            return {"ok": True, "queued": "play"}
        if name == "player_control":
            ui.append({"type": "player.control", "action": args.get("action"), "value": args.get("value")})
            return {"ok": True}
        if name == "navigate":
            ui.append({"type": "navigate", "view": args.get("view")})
            return {"ok": True}
        if name == "open_title_page":
            ui.append({"type": "open_title", "id": args.get("id")})
            return {"ok": True}
        if name == "get_watching_progress":
            prog = self._parse(self.load_db("watching_progress"))
            hist = self._parse(self.load_db("viewing_history"))
            return {"watching": (prog if isinstance(prog, list) else [])[:20], "history": (hist if isinstance(hist, list) else [])[-15:]}
        if name == "search_torrents":
            kind = (args.get("kind") or "anime").lower()
            q = args.get("query") or ""
            if kind == "anime":
                data = self._parse(api.search_nyaa_torrents(q, fast=True))
                results = data.get("results") or []
                slim = [{k: r.get(k) for k in ("title", "size", "seeders", "leechers", "score", "source", "group", "resolution", "tags", "magnet_link", "torrent_link", "date") if k in r} for r in results[:12]]
                return {"provider": "nyaa", "results": slim, "error": data.get("message")}
            data = self._parse(api.movie_raw_search(q))
            results = data.get("results") or []
            slim = [{k: r.get(k) for k in ("title", "size_gb", "seeders", "indexer", "score", "magnetUrl", "downloadUrl") if k in r} for r in results[:12]]
            return {"provider": "prowlarr", "status": data.get("status"), "message": data.get("message"), "results": slim}
        if name == "download_torrent":
            res = self._parse(api.torrent_add_raw(args.get("torrent_link") or "", args.get("magnet_link") or "", args.get("title") or ""))
            ui.append({"type": "downloads.refresh"})
            return res
        if name == "torrent_status":
            return self._parse(api.torrent_status())
        if name == "merger_scan":
            data = self._parse(api.merger_scan())
            pairs = data.get("matched") or data.get("pairs") or []
            return {"status": data.get("status"), "pairs": [{"episode": p.get("episode"), "raw": os.path.basename(p.get("raw") or ""), "dub": os.path.basename(p.get("dub") or "")} for p in pairs[:40]], "message": data.get("message")}
        if name == "merger_merge_all":
            def worker():
                try:
                    api.merger_autosync_merge_all("", args.get("voice_mode") or "off", args.get("sync_mode") or "auto")
                except Exception as e:
                    self.log(f"assistant merge_all failed: {e}")
            threading.Thread(target=worker, daemon=True).start()
            ui.append({"type": "navigate", "view": "merger"})
            return {"ok": True, "started": True}
        if name == "merger_import_downloads":
            return self._parse(api.merger_import_downloads(args.get("target") or "raw_folder", True))
        if name == "open_dub_browser":
            ok = api.open_internal_url(args.get("url") or "", args.get("title") or "", args.get("season") or 1, args.get("episode") or 0)
            return {"ok": bool(ok), "note": "The user must browse and download manually in that window."}
        if name == "dub_provider":
            if args.get("action") == "list_voices":
                return self._parse(api.dub_provider_list_voices(args.get("title") or ""))
            return self._parse(api.dub_provider_download_episode(args.get("title") or "", args.get("season") or 1, args.get("episode") or 1, args.get("voice") or ""))
        if name == "web_search":
            return self.web_search(args.get("query") or "")
        if name == "open_folder":
            folder = args.get("folder")
            if folder == "library":
                return self._parse(api.open_library_folder())
            return self._parse(api.merger_open_folder(folder or "raw_folder"))
        if name == "remember":
            mem = self._memory()
            fact = (args.get("fact") or "").strip()
            if fact and fact not in mem:
                mem.append(fact)
                try:
                    with open(self._memory_path(), "w", encoding="utf-8") as f:
                        json.dump(mem[-50:], f, ensure_ascii=False)
                except Exception:
                    pass
            return {"ok": True}
        return {"error": f"unknown tool {name}"}

    def web_search(self, query):
        keys = self.get_keys() or {}
        key = os.environ.get("TAVILY_API_KEY") or keys.get("TAVILY_API_KEY") or ""
        if not key:
            return {"error": "TAVILY_API_KEY is not configured (Settings → AI)."}
        try:
            body = json.dumps({"api_key": key, "query": query, "search_depth": "basic", "include_answer": True, "max_results": 5}).encode("utf-8")
            req = urllib.request.Request("https://api.tavily.com/search", data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            return {"answer": data.get("answer"), "results": [{"title": x.get("title"), "url": x.get("url"), "content": (x.get("content") or "")[:400]} for x in (data.get("results") or [])[:5]]}
        except Exception as e:
            return {"error": str(e)}

    # ────────────────────────── model call ──────────────────────────

    def _chat_completion(self, cfg, messages, tools):
        payload = {"model": cfg["model"], "messages": messages, "temperature": 0.3}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        if cfg["provider"] == "openrouter":
            headers["HTTP-Referer"] = "https://modernplayer.local"
            headers["X-Title"] = "Modern Player"
        req = urllib.request.Request(cfg["base_url"] + "/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:600]
            except Exception:
                pass
            raise AssistantError(f"{cfg['provider']} returned HTTP {e.code}: {body or e.reason}")
        except Exception as e:
            raise AssistantError(f"{cfg['provider']} request failed: {e}")
        if data.get("error"):
            raise AssistantError(str(data["error"].get("message") if isinstance(data["error"], dict) else data["error"]))
        try:
            return data["choices"][0]["message"]
        except Exception:
            raise AssistantError("Model returned an unexpected response.")

    def _system_messages(self, ctx):
        mem = self._memory()
        extra = ""
        if mem:
            extra += "\n\nThings you remembered about the user:\n- " + "\n- ".join(mem[-20:])
        if ctx:
            slim = {k: ctx.get(k) for k in ("view", "now_playing", "current_title", "language", "platform") if ctx.get(k) is not None}
            extra += "\n\nCurrent app context: " + json.dumps(slim, ensure_ascii=False)[:1500]
        return [{"role": "system", "content": SYSTEM_PROMPT + extra}]

    # ────────────────────────── public entry points ──────────────────────────

    def chat_events(self, user_message, ctx=None):
        """Generator of event dicts: status / tool_call / tool_result / answer / ui / error / done."""
        user_message = (user_message or "").strip()
        if not user_message:
            yield {"type": "answer", "text": "Tell me what to do: play something, find a RAW, merge a dub, or recommend a show."}
            yield {"type": "done"}
            return
        cfg = self.provider_config()
        if not cfg["configured"]:
            yield {"type": "answer", "text": "No AI provider configured yet. Open Settings → AI and add an API key (OpenAI, DeepSeek, OpenRouter, Groq or a custom OpenAI-compatible endpoint).", "needs_setup": True}
            yield {"type": "ui", "commands": [{"type": "navigate", "view": "settings", "section": "ai"}]}
            yield {"type": "done"}
            return

        ui_commands = []
        with self._lock:
            self.history.append({"role": "user", "content": user_message, "ts": _now_ms()})
            convo = [{k: v for k, v in m.items() if k != "ts"} for m in self.history[-HISTORY_LIMIT:]]
        messages = self._system_messages(ctx) + convo
        tools = self.tool_schemas()
        yield {"type": "status", "text": "thinking", "model": cfg["model"], "provider": cfg["provider"]}

        final_text = ""
        try:
            for round_no in range(MAX_TOOL_ROUNDS + 1):
                msg = self._chat_completion(cfg, messages, tools if round_no < MAX_TOOL_ROUNDS else None)
                calls = msg.get("tool_calls") or []
                content = msg.get("content") or ""
                if not calls:
                    final_text = content.strip() or "Done."
                    break
                assistant_msg = {"role": "assistant", "content": content or None, "tool_calls": calls}
                messages.append(assistant_msg)
                with self._lock:
                    self.history.append(assistant_msg | {"ts": _now_ms()})
                for call in calls:
                    fn = (call.get("function") or {})
                    name = fn.get("name") or ""
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = {}
                    yield {"type": "tool_call", "name": name, "args": args}
                    started = time.time()
                    try:
                        result = self.run_tool(name, args, ctx, ui_commands)
                    except Exception as e:
                        result = {"error": str(e)}
                    result_json = json.dumps(result, ensure_ascii=False, default=str)
                    if len(result_json) > 12000:
                        result_json = result_json[:12000] + "…(truncated)"
                    tool_msg = {"role": "tool", "tool_call_id": call.get("id"), "content": result_json}
                    messages.append(tool_msg)
                    with self._lock:
                        self.history.append(tool_msg | {"ts": _now_ms()})
                    yield {"type": "tool_result", "name": name, "ok": not (isinstance(result, dict) and result.get("error")), "ms": int((time.time() - started) * 1000), "preview": result_json[:300]}
                    if ui_commands:
                        yield {"type": "ui", "commands": list(ui_commands)}
                        ui_commands.clear()
            else:
                final_text = "I hit the tool limit for one request. Ask me to continue."
        except AssistantError as e:
            yield {"type": "error", "text": str(e)}
            with self._lock:
                self.history.append({"role": "assistant", "content": f"(error) {e}", "ts": _now_ms()})
                self._save_history()
            yield {"type": "done"}
            return

        with self._lock:
            self.history.append({"role": "assistant", "content": final_text, "ts": _now_ms()})
            self._save_history()
        if ui_commands:
            yield {"type": "ui", "commands": list(ui_commands)}
        yield {"type": "answer", "text": final_text}
        yield {"type": "done"}

    def chat(self, user_message, ctx=None):
        """Non-streaming variant: returns the collected result."""
        out = {"status": "success", "answer": "", "events": [], "ui": []}
        for ev in self.chat_events(user_message, ctx):
            out["events"].append(ev)
            if ev["type"] == "answer":
                out["answer"] = ev["text"]
            elif ev["type"] == "ui":
                out["ui"].extend(ev["commands"])
            elif ev["type"] == "error":
                out["status"] = "error"
                out["answer"] = ev["text"]
        return out

    def test_connection(self):
        cfg = self.provider_config()
        if not cfg["configured"]:
            return {"status": "error", "message": "No API key configured."}
        try:
            msg = self._chat_completion(cfg, [{"role": "user", "content": "Reply with the single word: ok"}], None)
            return {"status": "success", "provider": cfg["provider"], "model": cfg["model"], "reply": (msg.get("content") or "")[:80]}
        except AssistantError as e:
            return {"status": "error", "message": str(e)}
