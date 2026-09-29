# Modern Player

Desktop media player for anime, movies and shows with a library, online metadata, a dub merger, torrent RAW search, LAN sharing and a tool-using AI assistant.

Python backend (Bottle + pywebview) and a dependency-free ES-module frontend. No build step.

## Run

```bash
pip install bottle pywebview
python app.py            # desktop window
python dev_server.py     # backend only, open http://127.0.0.1:8765 in a browser (no native dialogs)
python build.py          # PyInstaller EXE → dist/ModernPlayer.exe
```

FFmpeg/ffprobe on PATH (or `ffmpeg.exe` next to the app) enables TS remux, playback fixes and merging.
Optional: `libtorrent` (internal downloads), `pychromecast` (casting), `numpy` (merger auto-sync), `demucs` (voice overlay).

## Layout

| Path | What |
|---|---|
| `app.py` | Bottle routes, `PlayerAPI` (media, merger, torrents, rooms), window startup |
| `bridge.py` | HTTP bridge: `/api/boot`, `/api/rpc`, `/api/settings`, `/api/meta/*`, `/api/assistant/*` |
| `assistant.py` | :3 agent: OpenAI-compatible tool-calling loop over the app's features |
| `metadata.py` | TMDB / Jikan proxy with disk cache and rate limiting |
| `nohomo_merger_core.py` | RAW + DUB matching, auto-sync, ffmpeg merge |
| `templates/` | frontend: `index.html`, `css/app.css`, `js/{core,player,views,features}` |

The UI never waits on pywebview's JS bridge: everything goes through the local HTTP API, so the window is usable as soon as the server answers (typically under 100 ms).

## Settings

Everything is edited from **Settings** inside the app and stored in `keys.json` next to the app (never commit it).

* **AI assistant** — provider (OpenAI, DeepSeek, OpenRouter, Groq or any OpenAI-compatible base URL), model, key. The model must support tool calling. Optional Tavily key for web search.
* **Playback** — auto-next, mini player, default skip markers, seek step, subtitle size, catalog language.
* **Folders & merger** — raw/dub/output folders, library root, ffmpeg paths, Demucs.
* **Downloads & sources** — Prowlarr (movies/shows), qBittorrent fallback, DUB source URL for the in-app browser, optional external DUB provider command.

## Assistant tools

The agent can: read app state, search the library and catalog, add titles, play/resume episodes, control the player, navigate, read watch progress, search torrents (Nyaa / Prowlarr), add torrents and check progress, scan/merge with the dub merger, import downloads, open the DUB browser, call the configured external DUB provider, search the web, open folders, and remember preferences.

The DUB browser is user-driven: the assistant can open it, but logging in, choosing a voice and downloading happen in that window. Files that land in `~/Downloads` are picked up by the merger watcher.

## Hotkeys

Space/K play · ←/→ seek · J/L ±10 s · Shift+←/→ prev/next · ↑/↓ volume · M mute · F fullscreen · S skip intro/outro · A aspect · C subtitles · B bookmark · P playlist · , . speed · 0–9 jump · Esc mini player · `/` search · Ctrl+K assistant · `?` help
