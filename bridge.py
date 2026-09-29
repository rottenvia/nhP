"""
HTTP bridge between the new frontend and PlayerAPI.

Why this exists: the old UI waited (up to 90 s) for pywebview's JS bridge before it
would unlock. Every call now goes over plain HTTP to the local Bottle server, which is
up before the window even opens. pywebview stays as the window shell only.

Routes installed here:
  GET  /api/boot                 everything the UI needs to render its first frame
  POST /api/rpc                  {"method": "...", "args": [...]} -> any public PlayerAPI method
  GET  /api/settings             keys.json + merger config (secrets masked)
  POST /api/settings             merge changes into keys.json / nohomo_config.json
  GET  /api/meta/<action>        metadata proxy (search/details/trending/...)
  POST /api/assistant/chat       agent (SSE stream when ?stream=1)
  GET  /api/assistant/history    chat history
  POST /api/assistant/clear      wipe history
  POST /api/assistant/test       connection test for the configured provider
  GET  /api/fs/list?path=        list media files in a folder (for folder linking)
"""
import inspect
import json
import os
import re
import threading
import time

import bottle

VIDEO_EXTS = {'.mkv', '.mp4', '.webm', '.ts', '.m4v', '.mov', '.avi'}
AUDIO_EXTS = {'.mp3', '.m4a', '.aac', '.flac', '.wav', '.ogg', '.opus'}
SUB_EXTS = {'.srt', '.vtt', '.ass'}
SECRET_KEYS = {'AI_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'OPENROUTER_API_KEY', 'GROQ_API_KEY', 'TAVILY_API_KEY',
               'TMDB_API_KEY', 'PROWLARR_API_KEY', 'QBIT_PASSWORD'}
SETTINGS_KEYS = ['AI_PROVIDER', 'AI_MODEL', 'AI_BASE_URL', 'AI_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'OPENROUTER_API_KEY',
                 'GROQ_API_KEY', 'TAVILY_API_KEY', 'TMDB_API_KEY', 'MOVIE_RAW_PROVIDER', 'PROWLARR_URL', 'PROWLARR_API_KEY',
                 'FLARESOLVERR_PATH', 'FLARESOLVERR_URL', 'FLARESOLVERR_AUTOSTART', 'QBIT_URL', 'QBIT_USERNAME', 'QBIT_PASSWORD',
                 'DUB_PROVIDER_COMMAND', 'PREFERRED_DUB_ORDER', 'DUB_SOURCE_URL', 'CATALOG_LANGUAGE', 'UI_LANGUAGE']
MERGER_KEYS = ['raw_folder', 'dub_folder', 'output_folder', 'library_root', 'ffmpeg_path', 'ffprobe_path', 'voice_isolation',
               'delete_ts_after_remux', 'organize_after_merge', 'dub_audio_track']

APP_VERSION = "2.0.0"

_h = None  # helpers namespace set by install()


def _json(data, status=200):
    bottle.response.status = status
    bottle.response.content_type = 'application/json; charset=utf-8'
    return json.dumps(data, ensure_ascii=False, default=str)


def _coerce(value):
    """PlayerAPI methods often return JSON strings; give the UI real objects."""
    if isinstance(value, str):
        v = value.strip()
        if (v.startswith('{') and v.endswith('}')) or (v.startswith('[') and v.endswith(']')):
            try:
                return json.loads(v)
            except Exception:
                pass
    return value


def _mask(v):
    v = str(v or '')
    if not v:
        return ''
    return '•' * 8 + v[-4:] if len(v) > 4 else '•' * 8


class ApiExtensions:
    """Mixed into PlayerAPI. Methods here are callable through /api/rpc."""

    # ---- dialogs (blocking; results are returned directly over HTTP) ----
    def _dialog(self, multiple, file_types, directory=False):
        win = getattr(self, '_window', None)
        if not win:
            return []
        import webview
        try:
            res = win.create_file_dialog(
                dialog_type=webview.FOLDER_DIALOG if directory else webview.OPEN_DIALOG,
                allow_multiple=multiple,
                file_types=() if directory else file_types,
            )
        except Exception as e:
            _h.log(f"dialog failed: {e}")
            return []
        if not res:
            return []
        return list(res) if isinstance(res, (list, tuple)) else [res]

    def dialog_open_files(self, kind="media", multiple=True):
        kinds = {
            "media": ('Media Files (*.mp4;*.mkv;*.webm;*.ts;*.m4v;*.mov;*.avi;*.mp3;*.m4a;*.aac;*.flac;*.wav;*.ogg)', 'All Files (*.*)'),
            "video": ('Video Files (*.mp4;*.mkv;*.webm;*.ts;*.m4v;*.mov;*.avi)', 'All Files (*.*)'),
            "subtitle": ('Subtitles (*.srt;*.vtt;*.ass)', 'All Files (*.*)'),
        }
        paths = self._dialog(bool(multiple), kinds.get(kind, kinds["media"]))
        return [self._file_info(p) for p in paths]

    def dialog_open_folder(self):
        paths = self._dialog(False, (), directory=True)
        return {"path": paths[0] if paths else ""}

    def _file_info(self, path):
        try:
            size = os.path.getsize(path)
        except Exception:
            size = 0
        ext = os.path.splitext(path)[1].lower()
        return {"path": path, "name": os.path.basename(path), "size": size,
                "kind": "audio" if ext in AUDIO_EXTS else ("subtitle" if ext in SUB_EXTS else "video"), "isTS": ext == '.ts'}

    def fs_list_media(self, folder, recursive=True):
        folder = str(folder or '')
        if not folder or not os.path.isdir(folder):
            return {"status": "error", "message": "folder not found", "files": []}
        out = []
        try:
            if recursive:
                for root, _dirs, files in os.walk(folder):
                    for f in files:
                        if os.path.splitext(f)[1].lower() in VIDEO_EXTS | AUDIO_EXTS:
                            out.append(self._file_info(os.path.join(root, f)))
                    if len(out) > 2000:
                        break
            else:
                for f in os.listdir(folder):
                    p = os.path.join(folder, f)
                    if os.path.isfile(p) and os.path.splitext(f)[1].lower() in VIDEO_EXTS | AUDIO_EXTS:
                        out.append(self._file_info(p))
        except Exception as e:
            return {"status": "error", "message": str(e), "files": out}
        out.sort(key=lambda x: x["name"].lower())
        return {"status": "success", "files": out}

    def read_text_file(self, path, max_bytes=4 * 1024 * 1024):
        """Used for subtitle files chosen through the native dialog."""
        try:
            with open(path, 'rb') as f:
                raw = f.read(int(max_bytes))
            for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'latin-1'):
                try:
                    return {"status": "success", "text": raw.decode(enc), "encoding": enc}
                except Exception:
                    continue
            return {"status": "error", "message": "undecodable"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def open_library_folder(self):
        return self.open_path(_h.DEFAULT_LIBRARY_DIR)

    def open_path(self, path):
        try:
            path = str(path or '')
            if not path or not os.path.exists(path):
                return {"status": "error", "message": "path not found"}
            import subprocess, sys
            if os.name == 'nt':
                os.startfile(path)  # noqa
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def link_media_files(self, title, files, copy_small=False):
        """Given selected files, decide per file: link directly, or remux .ts to mp4 inside the library folder.
        Returns [{path, name, size, ep_hint, is_remuxed, linked_directly}] synchronously."""
        import subprocess
        clean_title = re.sub(r'[\\/*?:"<>|]', "", str(title or "Unknown")).strip() or "Unknown"
        target_dir = os.path.join(_h.DEFAULT_LIBRARY_DIR, clean_title)
        results = []
        for f in files or []:
            fp = f.get("path") if isinstance(f, dict) else str(f)
            if not fp or not os.path.exists(fp):
                continue
            name = os.path.basename(fp)
            ext = os.path.splitext(name)[1].lower()
            info = self._file_info(fp)
            info["ep_hint"] = guess_episode_number(name)
            info["is_remuxed"] = False
            info["linked_directly"] = True
            if ext == '.ts':
                ffmpeg_bin = _h.get_ffmpeg_path()
                if ffmpeg_bin:
                    try:
                        os.makedirs(target_dir, exist_ok=True)
                        target = os.path.join(target_dir, os.path.splitext(name)[0] + ".mp4")
                        if not (os.path.exists(target) and os.path.getsize(target) > 1024 * 1024):
                            si = None
                            if os.name == 'nt':
                                si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            proc = subprocess.Popen([ffmpeg_bin, "-y", "-i", fp, "-c", "copy", "-map_metadata", "0", target],
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
                            try:
                                proc.communicate(timeout=120)
                            except subprocess.TimeoutExpired:
                                proc.kill(); proc.communicate()
                                try: os.remove(target)
                                except Exception: pass
                        if os.path.exists(target) and os.path.getsize(target) > 1024:
                            info = self._file_info(target)
                            info["ep_hint"] = guess_episode_number(name)
                            info["is_remuxed"] = True
                            info["linked_directly"] = False
                            info["source_path"] = fp
                    except Exception as e:
                        _h.log(f"link remux failed: {e}")
            results.append(info)
        return {"status": "success", "files": results, "library_dir": target_dir}

    def ffmpeg_status(self):
        bin_path = _h.get_ffmpeg_path()
        return {"ffmpeg": bool(bin_path), "path": bin_path or ""}

    def app_info(self):
        return {
            "version": APP_VERSION,
            "port": _h.PORT,
            "platform": os.name,
            "workflow_dir": _h.get_workflow_dir(),
            "library_dir": _h.DEFAULT_LIBRARY_DIR,
            "user_data_dir": _h.USER_DATA_DIR,
            "window": bool(getattr(self, '_window', None)),
            "libtorrent": _module_available("libtorrent"),
            "chromecast": _module_available("pychromecast"),
            "merger": _h.merger_available(),
        }


def guess_episode_number(name):
    n = str(name or '')
    pats = [r'[sS]\d{1,2}[eE](\d{1,3})', r'(?:[eE][pP]?|[eE]pisode|серия|Серия)\s*[._-]?\s*(\d{1,3})', r'\s-\s(\d{1,3})\b', r'\[(\d{1,3})\]', r'\b(\d{1,3})\b(?!\d*p)']
    for p in pats:
        m = re.search(p, n)
        if m:
            try:
                v = int(m.group(1))
                if 0 < v < 1000:
                    return v
            except Exception:
                pass
    return None


def _module_available(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


# ────────────────────────── settings ──────────────────────────

def _read_keys():
    try:
        p = _h.get_keys_file()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception as e:
        _h.log(f"keys.json read failed: {e}")
    return {}


def _write_keys(d):
    p = _h.get_keys_file()
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=4, ensure_ascii=False)
    os.replace(tmp, p)


def settings_snapshot():
    keys = _read_keys()
    out = {}
    for k in SETTINGS_KEYS:
        v = keys.get(k, '')
        if k in SECRET_KEYS:
            out[k] = _mask(v)
            out['has_' + k] = bool(v)
        else:
            out[k] = v
    merger = {}
    try:
        cfg = _h.merger_config()
        for k in MERGER_KEYS:
            if k in cfg:
                merger[k] = cfg[k]
    except Exception:
        pass
    return {"keys": out, "merger": merger, "keys_file": _h.get_keys_file(), "assistant": _h.assistant().public_config() if _h.assistant() else {}}


def settings_apply(payload):
    keys = _read_keys()
    changed = 0
    for k, v in (payload.get('keys') or {}).items():
        if k not in SETTINGS_KEYS:
            continue
        if k in SECRET_KEYS and isinstance(v, str) and v.startswith('•'):
            continue  # masked value came back untouched
        if isinstance(v, str):
            v = v.strip()
        if keys.get(k) != v:
            keys[k] = v
            changed += 1
    if changed:
        _write_keys(keys)
    merger_changes = payload.get('merger') or {}
    if merger_changes:
        _h.merger_config_update({k: v for k, v in merger_changes.items() if k in MERGER_KEYS})
    return settings_snapshot()


# ────────────────────────── install ──────────────────────────

def install(app, helpers):
    """helpers: object with attributes
       api() -> PlayerAPI | None, assistant() -> Assistant | None, metadata (module), log(msg),
       get_keys_file(), get_ffmpeg_path(), get_workflow_dir(), merger_config(), merger_config_update(d),
       merger_available(), PORT, DEFAULT_LIBRARY_DIR, USER_DATA_DIR, load_databases() -> dict of parsed dbs
    """
    global _h
    _h = helpers

    @app.get('/api/boot')
    def api_boot():
        api = _h.api()
        t0 = time.time()
        dbs = {}
        try:
            dbs = _h.load_databases()
        except Exception as e:
            _h.log(f"boot db load failed: {e}")
        info = api.app_info() if api else {"version": APP_VERSION, "port": _h.PORT, "window": False}
        try:
            info["ffmpeg"] = bool(_h.get_ffmpeg_path())
        except Exception:
            info["ffmpeg"] = False
        return _json({
            "status": "success",
            "app": info,
            "databases": dbs,
            "settings": settings_snapshot(),
            "boot_ms": int((time.time() - t0) * 1000),
        })

    @app.post('/api/rpc')
    def api_rpc():
        api = _h.api()
        if not api:
            return _json({"status": "error", "message": "API not ready"}, 503)
        try:
            payload = bottle.request.json or {}
        except Exception:
            return _json({"status": "error", "message": "invalid JSON"}, 400)
        method = str(payload.get('method') or '')
        args = payload.get('args') or []
        kwargs = payload.get('kwargs') or {}
        if not method or method.startswith('_') or not hasattr(api, method):
            return _json({"status": "error", "message": f"unknown method {method}"}, 404)
        fn = getattr(api, method)
        if not callable(fn):
            return _json({"status": "error", "message": f"{method} is not callable"}, 400)
        t0 = time.time()
        try:
            result = fn(*args, **kwargs)
        except TypeError as e:
            return _json({"status": "error", "message": f"bad arguments for {method}: {e}"}, 400)
        except Exception as e:
            _h.log(f"rpc {method} failed: {e}")
            return _json({"status": "error", "message": str(e)}, 500)
        return _json({"status": "success", "result": _coerce(result), "ms": int((time.time() - t0) * 1000)})

    @app.get('/api/settings')
    def api_settings_get():
        return _json({"status": "success", **settings_snapshot()})

    @app.post('/api/settings')
    def api_settings_post():
        try:
            payload = bottle.request.json or {}
            return _json({"status": "success", **settings_apply(payload)})
        except Exception as e:
            return _json({"status": "error", "message": str(e)}, 500)

    @app.get('/api/meta/<action>')
    def api_meta(action):
        q = bottle.request.query
        meta = _h.metadata
        lang = q.get('lang') or (_read_keys().get('CATALOG_LANGUAGE') or 'en-US')
        try:
            if action == 'search':
                return _json(meta.search(q.get('category', 'anime'), q.get('q', ''), lang))
            if action == 'details':
                return _json(meta.details(q.get('category', 'anime'), q.get('id'), lang))
            if action == 'trending':
                return _json(meta.trending(q.get('category', 'anime'), lang))
            if action == 'relations':
                return _json(meta.anime_relations(q.get('id')))
            if action == 'episodes':
                return _json(meta.anime_episodes(q.get('id'), int(q.get('page', 1) or 1)))
            if action == 'season':
                return _json(meta.tv_season(q.get('id'), int(q.get('season', 1) or 1), lang))
            if action == 'franchise':
                return _json(meta.franchise(q.get('id')))
        except Exception as e:
            return _json({"status": "error", "message": str(e)}, 500)
        return _json({"status": "error", "message": "unknown action"}, 404)

    @app.post('/api/assistant/chat')
    def api_assistant_chat():
        a = _h.assistant()
        if not a:
            return _json({"status": "error", "answer": "Assistant not ready"}, 503)
        payload = bottle.request.json or {}
        msg = payload.get('message', '')
        ctx = payload.get('context') or {}
        if str(bottle.request.query.get('stream', '')) in ('1', 'true'):
            bottle.response.content_type = 'text/event-stream; charset=utf-8'
            bottle.response.headers['Cache-Control'] = 'no-cache'
            bottle.response.headers['X-Accel-Buffering'] = 'no'

            def gen():
                try:
                    for ev in a.chat_events(msg, ctx):
                        yield 'data: ' + json.dumps(ev, ensure_ascii=False, default=str) + '\n\n'
                except Exception as e:
                    yield 'data: ' + json.dumps({"type": "error", "text": str(e)}) + '\n\n'
                    yield 'data: {"type": "done"}\n\n'
            return gen()
        return _json(a.chat(msg, ctx))

    @app.get('/api/assistant/history')
    def api_assistant_history():
        a = _h.assistant()
        return _json({"status": "success", "messages": a.get_history() if a else [], "config": a.public_config() if a else {}})

    @app.post('/api/assistant/clear')
    def api_assistant_clear():
        a = _h.assistant()
        return _json(a.clear_history() if a else {"status": "error"})

    @app.post('/api/assistant/test')
    def api_assistant_test():
        a = _h.assistant()
        return _json(a.test_connection() if a else {"status": "error", "message": "not ready"})

    @app.get('/api/fs/list')
    def api_fs_list():
        api = _h.api()
        if not api:
            return _json({"status": "error", "files": []}, 503)
        return _json(api.fs_list_media(bottle.request.query.get('path', ''), bottle.request.query.get('recursive', '1') == '1'))
