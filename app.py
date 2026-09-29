
import sys
import os

# ═══════════════════════════════════════════════════════
#  🚀 ULTRA HARDWARE ACCELERATION FORCE FLAGS FOR WINDOWS (WEBVIEW2)
#  Forces Chromium to bypass driver blocklists, activate zero-copy buffers,
#  and route video frames directly to GPU hardware overlay planes for 101% sharpness!
# ═══════════════════════════════════════════════════════
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
    "--ignore-gpu-blocklist "
    "--enable-gpu-rasterization "
    "--enable-zero-copy "
    "--enable-hardware-overlays "
    "--disable-features=LayoutNG "
    "--disable-gpu-vsync "
    "--enable-features=WebAssembly"
)

# ═══════════════════════════════════════════════════════
#  📂 PERSISTENT STORAGE ENGINE CONFIGURATION
#  Forces WebView2 to use a persistent user data folder in AppData,
#  preventing localStorage, viewing history, and library from resetting on close!
# ═══════════════════════════════════════════════════════
USER_DATA_DIR = ""
try:
    if os.name == 'nt':
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        user_data_dir = os.path.join(appdata, "MinimalMediaPlayerPro")
    else:
        user_data_dir = os.path.expanduser("~/.config/MinimalMediaPlayerPro")
        
    os.makedirs(user_data_dir, exist_ok=True)
    USER_DATA_DIR = user_data_dir
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = user_data_dir
    print(f"[Storage Engine] WebView2 user data folder configured at: {user_data_dir}")
except Exception as e:
    print(f"[Storage Engine] Failed to configure user data folder: {e}")

# Symmetrical Local Media Organizer Folder
DEFAULT_LIBRARY_DIR = os.path.join(os.path.expanduser("~"), "Videos", "MinimalMediaPlayer")
os.makedirs(DEFAULT_LIBRARY_DIR, exist_ok=True)

import re
import socket
import threading
import subprocess

def get_exe_dir():
    import sys
    import os
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__) if __file__ else ".")

def get_workflow_dir():
    """Returns the folder where user workflow folders live: raw/dub/output/test.
    If running from dist/ModernPlayer.exe during development, use the parent project folder
    so users do not accidentally create raw/dub in the wrong place.
    """
    base = get_exe_dir()
    try:
        if os.path.basename(base).lower() == 'dist':
            parent = os.path.dirname(base)
            if os.path.exists(os.path.join(parent, 'templates')) or os.path.exists(os.path.join(parent, 'app.py')):
                return parent
    except Exception:
        pass
    return base

def get_keys_file():
    """Prefer keys.json in the workflow/project root, not dist/.
    This prevents the EXE from creating/reading an empty dist/keys.json while the real keys.json
    lives next to app.py/build.py/raw/dub.
    """
    workflow = os.path.join(get_workflow_dir(), "keys.json")
    exe_local = os.path.join(get_exe_dir(), "keys.json")
    if os.path.exists(workflow):
        return workflow
    if os.path.exists(exe_local) and os.path.abspath(exe_local) != os.path.abspath(workflow):
        try:
            with open(exe_local, "r", encoding="utf-8") as f:
                import json
                data = json.load(f)
            if data.get("OPENAI_API_KEY") or data.get("TAVILY_API_KEY"):
                return exe_local
        except Exception:
            pass
    return workflow


def get_workflow_data_dir(*parts):
    """Project-local runtime data folder. Keeps root clean while still being portable."""
    path = os.path.join(get_workflow_dir(), "data", *parts)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path
import urllib.parse
import bottle
import webview
try:
    import nohomo_merger_core
except Exception as _merger_import_error:
    nohomo_merger_core = None

# Prefer a stable port so Watch Together / TV links and firewall rules do not change every restart.
# If 8765 is occupied, fall back to a random free port.
def find_free_port(preferred=8765):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('0.0.0.0', int(preferred)))
        port = s.getsockname()[1]
        s.close()
        return port
    except Exception:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

PORT = find_free_port(8765)

def get_asset_path(relative_path):
    """ Returns absolute path to resource, taking PyInstaller bundling into account """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__) if __file__ else ".")
    return os.path.join(base_path, relative_path)

import tempfile
import hashlib

def get_safe_temp_dir():
    candidates = [
        r"C:\Users\Public",
        tempfile.gettempdir(),
        os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
    ]
    for path in candidates:
        if not path:
            continue
        try:
            path.encode('ascii')
            test_file = os.path.join(path, ".test_write")
            with open(test_file, "w") as f:
                f.write("")
            os.remove(test_file)
            return path
        except Exception:
            continue
    return tempfile.gettempdir()

def get_output_mp4_path(filepath):
    h = hashlib.md5(filepath.encode('utf-8', errors='ignore')).hexdigest()
    safe_dir = get_safe_temp_dir()
    return os.path.join(safe_dir, f"remux_{h}.mp4")

def get_ffmpeg_path():
    # Check 1: Packed inside PyInstaller or in current directory
    local_ffmpeg = get_asset_path("ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    local_ffmpeg_dir = os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), "ffmpeg.exe")
    if os.path.exists(local_ffmpeg_dir):
        return local_ffmpeg_dir
        
    # Check 2: System PATH
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        proc.communicate()
        return "ffmpeg"
    except Exception:
        pass
        
    return None


# ═══════════════════════════════════════════════════════
#  🔊 ADVANCED PURE PYTHON SIGNATURE-BASED PTS PARSER
#  Scans raw binary PES stream structures to parse PTS.
#  100% compatible with TS, M2TS, TS-204, and IPTV dumps!
#  Does NOT need any external tools, works instantly (1ms).
# ═══════════════════════════════════════════════════════
def parse_pts_from_pes(chunk, idx):
    if idx + 14 > len(chunk):
        return None
    # PES start code prefix: 0x000001
    # Stream ID is at idx + 3
    stream_id = chunk[idx + 3]
    # Check if stream ID has optional PES header (all streams except some private streams)
    if stream_id not in (0xBC, 0xBF, 0xF0, 0xF1, 0xFF, 0xF2, 0xF8):
        # Optional PES header starts at idx + 6
        # Check if PTS/DTS flags (high 2 bits of idx + 7) indicate PTS is present (2 or 3)
        pts_dts_flag = (chunk[idx + 7] & 0xC0) >> 6
        if pts_dts_flag in (2, 3):
            # PTS data is at idx + 9
            pts_bytes = chunk[idx + 9 : idx + 14]
            if len(pts_bytes) == 5:
                # Validate PTS prefix marker bits (high 4 bits of pts_bytes[0] must be 0010 or 0011)
                # which is 0x20 or 0x30
                if (pts_bytes[0] & 0xF1) in (0x21, 0x31) and (pts_bytes[2] & 0x01) == 0x01 and (pts_bytes[4] & 0x01) == 0x01:
                    pts = ((pts_bytes[0] & 0x0E) << 29) | \
                          (pts_bytes[1] << 22) | \
                          ((pts_bytes[2] & 0xFE) << 14) | \
                          (pts_bytes[3] << 7) | \
                          ((pts_bytes[4] & 0xFE) >> 1)
                    return pts
    return None

def scan_chunk_for_pts_first(chunk):
    """ Finds the first valid PTS timestamp in a binary chunk """
    offset = 0
    while True:
        idx = chunk.find(b'\x00\x00\x01', offset)
        if idx == -1:
            break
        pts = parse_pts_from_pes(chunk, idx)
        if pts is not None:
            return pts
        offset = idx + 3
    return None

def scan_chunk_for_pts_last(chunk):
    """ Finds the last valid PTS timestamp in a binary chunk """
    offset = 0
    last_pts = None
    while True:
        idx = chunk.find(b'\x00\x00\x01', offset)
        if idx == -1:
            break
        pts = parse_pts_from_pes(chunk, idx)
        if pts is not None:
            last_pts = pts
        offset = idx + 3
    return last_pts

def parse_pcr_from_ts_packet(packet, packet_size=188):
    if len(packet) < packet_size:
        return None
    if packet_size == 192:
        ts_packet = packet[4:]
    elif packet_size == 204:
        ts_packet = packet[:188]
    else:
        ts_packet = packet
        
    if len(ts_packet) < 188 or ts_packet[0] != 0x47:
        return None
    adapt_control = (ts_packet[3] & 0x30) >> 4
    if adapt_control in (2, 3):
        adapt_len = ts_packet[4]
        if adapt_len > 0 and len(ts_packet) > 5:
            pcr_flag = (ts_packet[5] & 0x10) >> 4
            if pcr_flag == 1 and adapt_len >= 5 and len(ts_packet) >= 11:
                pcr_base = ((ts_packet[6] << 25) | 
                            (ts_packet[7] << 17) | 
                            (ts_packet[8] << 9) | 
                            (ts_packet[9] << 1) | 
                            (ts_packet[10] >> 7)) & 0x1FFFFFFFF
                return pcr_base
    return None

def find_pcr_first(filepath, packet_size=188, max_scan=5*1024*1024):
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(65536)
            if not chunk:
                return None
            start_pos = chunk.find(b'\x47')
            if start_pos == -1:
                return None
            
            if packet_size == 192:
                start_pos = max(0, start_pos - 4)
                
            f.seek(start_pos)
            offset = start_pos
            while offset < max_scan:
                packet = f.read(packet_size)
                if len(packet) < packet_size:
                    break
                pcr = parse_pcr_from_ts_packet(packet, packet_size)
                if pcr is not None:
                    return pcr
                offset += packet_size
    except Exception as e:
        print("Error finding first PCR:", e)
    return None

def find_pcr_last(filepath, packet_size=188, max_scan=5*1024*1024):
    try:
        size = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            start_seek = max(0, size - max_scan)
            f.seek(start_seek)
            chunk = f.read(65536)
            if not chunk:
                return None
            first_sync = chunk.find(b'\x47')
            if first_sync == -1:
                return None
            
            start_pos = start_seek + first_sync
            if packet_size == 192:
                start_pos = max(0, start_pos - 4)
                
            f.seek(start_pos)
            offset = start_pos
            last_pcr = None
            while offset < size:
                packet = f.read(packet_size)
                if len(packet) < packet_size:
                    break
                pcr = parse_pcr_from_ts_packet(packet, packet_size)
                if pcr is not None:
                    last_pcr = pcr
                offset += packet_size
            return last_pcr
    except Exception as e:
        print("Error finding last PCR:", e)
    return None

def detect_ts_packet_size(filepath):
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(10000)
            pos = chunk.find(b'\x47')
            if pos == -1:
                return 188
            for size in (188, 192, 204):
                if pos + size * 4 < len(chunk):
                    if (chunk[pos + size] == 0x47 and 
                        chunk[pos + size * 2] == 0x47 and 
                        chunk[pos + size * 3] == 0x47):
                        return size
    except Exception:
        pass
    return 188

def get_ts_duration_pure(filepath):
    """ Advanced binary parser to calculate TS file duration from PTS or PCR tags natively """
    if not os.path.exists(filepath):
        return 0
    try:
        size = os.path.getsize(filepath)
        packet_size = detect_ts_packet_size(filepath)
        print(f"[TS Parser] Detected TS packet size: {packet_size} bytes")
        
        first_pts = None
        last_pts = None
        
        with open(filepath, 'rb') as f:
            # Scan first 5MB for PTS
            first_chunk = f.read(min(size, 5 * 1024 * 1024))
            first_pts = scan_chunk_for_pts_first(first_chunk)
            
            # Scan last 5MB for PTS
            if size > 5 * 1024 * 1024:
                f.seek(-5 * 1024 * 1024, os.SEEK_END)
            else:
                f.seek(0)
            last_chunk = f.read()
            last_pts = scan_chunk_for_pts_last(last_chunk)
            
        if first_pts is not None and last_pts is not None:
            diff = last_pts - first_pts
            if diff < 0:
                diff += 2**33
            duration = diff / 90000.0
            if 0 < duration < 86400: # Limit to sane range (under 24 hours)
                print(f"[TS Parser] Pure PTS duration: {duration}s")
                return duration
                
        # If PTS duration fails, try PCR duration (ultra robust fallback)
        first_pcr = find_pcr_first(filepath, packet_size)
        last_pcr = find_pcr_last(filepath, packet_size)
        if first_pcr is not None and last_pcr is not None:
            diff = last_pcr - first_pcr
            if diff < 0:
                diff += 2**33
            duration = diff / 90000.0
            if 0 < duration < 86400:
                print(f"[TS Parser] Pure PCR duration: {duration}s")
                return duration
                
    except Exception as e:
        print("[PTS Parser] Pure binary parser failed:", e)
    return 0


def log_to_file(message):
    try:
        with open("player_log.txt", "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass

# Initialize Bottle app
app = bottle.Bottle()
API_INSTANCE = None
WATCH_ROOMS = {}
TV_ROOMS = {}
TV_STREAMS = {}
LIVE_STREAMS = {}


@app.hook('after_request')
def disable_cache():
    bottle.response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    bottle.response.headers['Pragma'] = 'no-cache'
    bottle.response.headers['Expires'] = '0'

@app.route('/')
def index():
    return bottle.static_file('index.html', root=get_asset_path('templates'))

@app.route('/dub-loading')
def dub_loading():
    target = bottle.request.query.get('target', 'https://rezka.fi/')
    title = bottle.request.query.get('title', '')
    season = bottle.request.query.get('season', '1')
    episode = bottle.request.query.get('episode', '0')
    safe_target = str(target).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    safe_title = str(title).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f"""
<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>DUB Browser Loading</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; width:100vw; height:100vh; overflow:hidden; background:#050508; color:#fff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif; display:flex; align-items:center; justify-content:center; }}
.bg {{ position:fixed; inset:-20%; background: radial-gradient(circle at 25% 25%, rgba(124,92,252,.22), transparent 30%), radial-gradient(circle at 75% 65%, rgba(6,182,212,.16), transparent 28%), #050508; filter: blur(10px); }}
.card {{ position:relative; width:min(560px, calc(100vw - 48px)); border:1px solid rgba(255,255,255,.08); background:rgba(12,12,18,.78); backdrop-filter: blur(18px); border-radius:18px; padding:26px; box-shadow:0 24px 70px rgba(0,0,0,.7); }}
.logo {{ width:54px; height:54px; border-radius:16px; background:#7c5cfc; display:flex; align-items:center; justify-content:center; font-weight:900; margin-bottom:18px; box-shadow:0 0 24px rgba(124,92,252,.35); }}
h1 {{ font-size:1.15rem; margin:0 0 8px; }}
p {{ margin:0 0 12px; color:rgba(255,255,255,.68); font-size:.82rem; line-height:1.5; }}
.target {{ margin-top:14px; padding:10px 12px; border-radius:10px; background:rgba(255,255,255,.04); color:rgba(255,255,255,.75); font-size:.72rem; word-break:break-all; }}
.progress {{ height:4px; border-radius:99px; overflow:hidden; background:rgba(255,255,255,.08); margin-top:18px; }}
.bar {{ height:100%; width:35%; background:linear-gradient(90deg,#7c5cfc,#06b6d4); border-radius:99px; animation: slide 1.2s ease-in-out infinite alternate; }}
@keyframes slide {{ from {{ transform:translateX(-80%); }} to {{ transform:translateX(260%); }} }}
.small {{ font-size:.68rem; color:rgba(255,255,255,.42); margin-top:12px; }}
</style>
</head>
<body>
<div class='bg'></div>
<div class='card'>
  <div class='logo'>:3</div>
  <h1>Preparing DUB Browser</h1>
  <p>Loading the source in a stability-first mode. If the source page is heavy, wait until it fully settles before clicking titles or playing video.</p>
  <p><b>Expected:</b> {safe_title or 'current title'} · S{season.zfill(2)}E{episode.zfill(2)}</p>
  <div class='target'>{safe_target}</div>
  <div class='progress'><div class='bar'></div></div>
  <div class='small'>No helper scripts are injected during navigation to prevent WebView freezes. Use Merger watcher in the main window after downloading.</div>
</div>
</body>
</html>
"""


@app.route('/static/<filepath:path>')
def serve_static(filepath):
    return bottle.static_file(filepath, root=get_asset_path('templates'))

@app.route('/media')
def serve_media():
    filepath = bottle.request.query.get('path')
    if not filepath:
        return bottle.HTTPError(400, "Missing path parameter")
    
    # Defensive unquoting and whitespace cleanup
    filepath = urllib.parse.unquote(filepath).strip('"' + "'")
    if not os.path.exists(filepath):
        # Symmetrical fallback for spaces encoded as pluses
        filepath_alt = filepath.replace('+', ' ')
        if os.path.exists(filepath_alt):
            filepath = filepath_alt
        else:
            return bottle.HTTPError(404, f"File not found: {filepath}")
        
    if filepath.lower().endswith('.ts'):
        bottle.response.set_header('Connection', 'close')  # Immediately close aborted connections for TS only to prevent socket exhaustion!
        
    dirname = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()
    mimetype = None
    if ext in ('.m4a', '.mp4a'):
        mimetype = 'audio/mp4'
    elif ext == '.aac':
        mimetype = 'audio/aac'
    elif ext == '.mkv':
        mimetype = 'video/x-matroska'
    elif ext == '.mp4':
        mimetype = 'video/mp4'
    return bottle.static_file(filename, root=dirname, mimetype=mimetype) if mimetype else bottle.static_file(filename, root=dirname)


# HTTP fallback API for cases where pywebview's JS bridge is late/unavailable.
# This keeps assistant/storage usable and prevents data-loss when window.pywebview.api is not exposed yet.
@app.post('/api/assistant_chat')
def api_assistant_chat_route():
    import json
    try:
        payload = bottle.request.json or {}
        msg = payload.get('message', '')
        ctx = payload.get('context', '{}')
        if API_INSTANCE:
            bottle.response.content_type = 'application/json; charset=utf-8'
            return API_INSTANCE.ai_assistant_chat(msg, ctx)
        return json.dumps({"status": "error", "answer": "Backend API instance is not ready yet.", "actions": []}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "answer": "Assistant HTTP fallback failed: " + str(e), "actions": []}, ensure_ascii=False)

@app.get('/api/load_all_databases')
def api_load_all_databases_route():
    if API_INSTANCE:
        bottle.response.content_type = 'application/json; charset=utf-8'
        return API_INSTANCE.load_all_databases()
    return '{"library":"{}","watching_progress":"{}","viewing_history":"{}","playlist":"{}","playlist_index":"{}"}'

@app.post('/api/save_db_data')
def api_save_db_data_route():
    import json
    try:
        payload = bottle.request.json or {}
        key = payload.get('key', '')
        data = payload.get('data', '{}')
        ok = API_INSTANCE.save_db_data(key, data) if API_INSTANCE else False
        return json.dumps({"status": "success" if ok else "error", "ok": ok}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

@app.get('/api/health')
def api_health_route():
    import json
    try:
        methods = []
        if API_INSTANCE:
            methods = [m for m in dir(API_INSTANCE) if not m.startswith('_') and callable(getattr(API_INSTANCE, m, None))]
        bottle.response.content_type = 'application/json; charset=utf-8'
        return json.dumps({
            "status": "success",
            "api_ready": API_INSTANCE is not None,
            "methods": methods,
            "port": PORT,
            "workflow_dir": get_workflow_dir(),
            "version": "2026.06.18-ready-gate"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

def get_lan_ip():
    ips = get_all_lan_ips()
    for ip in ips:
        if ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.'):
            return ip
    return ips[0] if ips else '127.0.0.1'


def get_all_lan_ips():
    """Return useful local IPv4 addresses, including VPN adapters like Radmin/Tailscale.
    Browser clients must use the IP that belongs to their network path.
    """
    ips = []
    def add(ip):
        if not ip or ip.startswith('127.') or ip == '0.0.0.0':
            return
        if ip not in ips:
            ips.append(ip)
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            add(info[4][0])
    except Exception:
        pass
    # Route-derived primary IP fallback.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    # Windows: socket hostname often misses VPN adapters. Parse ipconfig as fallback.
    if os.name == 'nt':
        try:
            out = subprocess.check_output(['ipconfig'], text=True, encoding='utf-8', errors='ignore')
            for m in re.finditer(r'IPv4[^:\n]*:\s*([0-9]+(?:\.[0-9]+){3})', out):
                add(m.group(1))
        except Exception:
            pass
    # Prefer VPN/private addresses likely useful for friends.
    def rank(ip):
        if ip.startswith('26.'): return 0      # Radmin VPN commonly uses 26.x.x.x
        if ip.startswith('100.'): return 1     # Tailscale CGNAT
        if ip.startswith('192.168.'): return 2
        if ip.startswith('10.'): return 3
        if ip.startswith('172.'): return 4
        return 9
    ips.sort(key=rank)
    return ips or ['127.0.0.1']


def make_room_code():
    import random, string
    for _ in range(20):
        code = ''.join(random.choice(string.digits) for _ in range(6))
        if code not in WATCH_ROOMS:
            return code
    return str(int(time.time()))[-6:]


@app.post('/api/watch/create')
def api_watch_create():
    import json, time
    payload = bottle.request.json or {}
    code = make_room_code()
    now = time.time()
    media_path = urllib.parse.unquote(str(payload.get('path') or '')).strip('\"' + "'")
    share = {'available': False}
    if media_path and os.path.exists(media_path):
        try:
            size = os.path.getsize(media_path)
        except Exception:
            size = 0
        share = {
            'available': True,
            'name': os.path.basename(media_path),
            'size': size,
            'size_mb': round(size / 1048576, 2),
            'download_url': f'/watch_download/{code}'
        }
    WATCH_ROOMS[code] = {
        'code': code,
        'created': now,
        'updated': now,
        'title': payload.get('title') or 'Watch Together',
        'duration': float(payload.get('duration') or 0),
        'fingerprint': payload.get('fingerprint') or '',
        'host': payload.get('host') or 'host',
        'share_path': media_path if share.get('available') else '',
        'share': share,
        'state': {
            'paused': True,
            'time': float(payload.get('time') or 0),
            'rate': float(payload.get('rate') or 1),
            'updatedAt': now
        },
        'clients': {}
    }
    ips = get_all_lan_ips()
    lan = ips[0] if ips else get_lan_ip()
    urls = [{'label': 'local', 'url': f'http://127.0.0.1:{PORT}/watch/{code}'}]
    for ip in ips:
        label = 'Radmin VPN' if ip.startswith('26.') else ('Tailscale' if ip.startswith('100.') else 'LAN')
        urls.append({'label': label, 'ip': ip, 'url': f'http://{ip}:{PORT}/watch/{code}'})
    bottle.response.content_type = 'application/json; charset=utf-8'
    return json.dumps({
        'status': 'success',
        'room': code,
        'local_url': f'http://127.0.0.1:{PORT}/watch/{code}',
        'lan_url': f'http://{lan}:{PORT}/watch/{code}',
        'urls': urls,
        'host_ip': lan,
        'all_ips': ips,
        'port': PORT
    }, ensure_ascii=False)


@app.post('/api/watch/update/<code>')
def api_watch_update(code):
    import json, time
    room = WATCH_ROOMS.get(str(code))
    if not room:
        return json.dumps({'status': 'missing', 'message': 'room not found'}, ensure_ascii=False)
    payload = bottle.request.json or {}
    now = time.time()
    room['updated'] = now
    room['title'] = payload.get('title') or room.get('title') or 'Watch Together'
    media_path = urllib.parse.unquote(str(payload.get('path') or '')).strip('\"' + "'")
    if media_path and os.path.exists(media_path) and media_path != room.get('share_path'):
        try:
            size = os.path.getsize(media_path)
        except Exception:
            size = 0
        room['share_path'] = media_path
        room['share'] = {'available': True, 'name': os.path.basename(media_path), 'size': size, 'size_mb': round(size / 1048576, 2), 'download_url': f'/watch_download/{code}'}
    if payload.get('duration') is not None:
        try: room['duration'] = float(payload.get('duration') or 0)
        except Exception: pass
    state = room.setdefault('state', {})
    if payload.get('paused') is not None:
        state['paused'] = bool(payload.get('paused'))
    if payload.get('time') is not None:
        try: state['time'] = float(payload.get('time') or 0)
        except Exception: pass
    if payload.get('rate') is not None:
        try: state['rate'] = float(payload.get('rate') or 1)
        except Exception: pass
    state['updatedAt'] = now
    bottle.response.content_type = 'application/json; charset=utf-8'
    return json.dumps({'status': 'success', 'room': room}, ensure_ascii=False)


@app.post('/api/watch/join/<code>')
def api_watch_join(code):
    import json, time
    room = WATCH_ROOMS.get(str(code))
    if not room:
        return json.dumps({'status': 'missing', 'message': 'room not found'}, ensure_ascii=False)
    payload = bottle.request.json or {}
    client_id = str(payload.get('client_id') or '')[:80] or ('client-' + str(int(time.time() * 1000)))
    room.setdefault('clients', {})[client_id] = {
        'id': client_id,
        'name': str(payload.get('name') or 'friend')[:80],
        'has_file': bool(payload.get('has_file')),
        'updated': time.time()
    }
    return json.dumps({'status': 'success', 'clients': len(room.get('clients', {}))}, ensure_ascii=False)


@app.get('/api/watch/state/<code>')
def api_watch_state(code):
    import json, time
    room = WATCH_ROOMS.get(str(code))
    if not room:
        return json.dumps({'status': 'missing', 'message': 'room not found'}, ensure_ascii=False)
    # Expire rooms after 12h idle.
    if time.time() - float(room.get('updated') or room.get('created') or 0) > 43200:
        WATCH_ROOMS.pop(str(code), None)
        return json.dumps({'status': 'missing', 'message': 'room expired'}, ensure_ascii=False)
    now = time.time()
    try:
        clients = room.setdefault('clients', {})
        for cid, c in list(clients.items()):
            if now - float(c.get('updated') or 0) > 20:
                clients.pop(cid, None)
    except Exception:
        pass
    safe_room = dict(room)
    safe_room.pop('share_path', None)
    bottle.response.content_type = 'application/json; charset=utf-8'
    return json.dumps({'status': 'success', 'room': safe_room, 'serverTime': now}, ensure_ascii=False)


@app.get('/watch_download/<code>')
def watch_download_file(code):
    room = WATCH_ROOMS.get(str(code))
    if not room:
        return bottle.HTTPError(404, 'room not found')
    path = room.get('share_path') or ''
    if not path or not os.path.exists(path):
        return bottle.HTTPError(404, 'shared file not found')
    return bottle.static_file(os.path.basename(path), root=os.path.dirname(path), download=os.path.basename(path))


@app.get('/watch/<code>')
def watch_room_page(code):
    safe_code = re.sub(r'[^0-9A-Za-z_-]', '', str(code))[:32]
    return f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Watch Together {safe_code}</title>
<style>
html,body{{margin:0;height:100%;background:#050508;color:#fff;font-family:Inter,Segoe UI,Arial,sans-serif;overflow:hidden}}
.bg{{position:fixed;inset:0;background:radial-gradient(circle at 50% 10%,rgba(124,92,252,.18),transparent 38%),#050508}}
.top{{position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:5;display:flex;gap:10px;align-items:center;background:rgba(10,10,16,.72);border:1px solid rgba(255,255,255,.1);border-radius:18px;padding:10px 14px;backdrop-filter:blur(14px)}}
.badge{{font-size:12px;color:#b8aaff;font-weight:900;letter-spacing:.08em;text-transform:uppercase}}
#status{{font-size:12px;color:rgba(255,255,255,.58)}}
.picker{{position:fixed;inset:0;display:grid;place-items:center;z-index:3}}
.card{{width:min(520px,calc(100vw - 40px));background:rgba(12,12,18,.86);border:1px solid rgba(255,255,255,.1);border-radius:22px;padding:24px;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.55)}}
.logo{{font-size:42px;margin-bottom:8px}} h1{{margin:0 0 8px;font-size:26px}} p{{color:rgba(255,255,255,.58);line-height:1.55;font-size:14px}} input{{margin-top:14px}}
video{{width:100vw;height:100vh;object-fit:contain;background:#000;display:none}}
</style></head><body><div class='bg'></div>
<div class='top'><span class='badge'>Room {safe_code}</span><span id='status'>Select the same local file. Host controls play/pause/seek.</span></div>
<div class='picker' id='picker'><div class='card'><div class='logo'>:3</div><h1>Watch Together</h1><p>Choose the same movie/episode file on this computer. After that, playback will follow the host.</p><input id='file' type='file' accept='video/*,.mkv,.mp4,.webm,.ts,.mov,.avi'></div></div>
<video id='v' playsinline></video>
<script>
const room='{safe_code}', v=document.getElementById('v'), picker=document.getElementById('picker'), statusEl=document.getElementById('status');
let ready=false, lastSeek=0, applying=false, lastHostTarget=0;
const clientId = localStorage.getItem('mmp_watch_client_id') || Math.random().toString(36).slice(2);
localStorage.setItem('mmp_watch_client_id', clientId);
async function heartbeat(){{try{{await fetch('/api/watch/join/'+room,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{client_id:clientId,name:'friend',has_file:ready}})}});}}catch(e){{}}}}
document.getElementById('file').onchange=e=>{{const f=e.target.files[0]; if(!f)return; v.src=URL.createObjectURL(f); v.style.display='block'; picker.style.display='none'; ready=true; statusEl.textContent='Connected. Waiting for host...'; heartbeat();}};
setInterval(heartbeat,5000); heartbeat();
function hostTime(state, serverTime){{let t=Number(state.time||0); if(!state.paused) t += Math.max(0, Number(serverTime||Date.now()/1000)-Number(state.updatedAt||serverTime||Date.now()/1000))*Number(state.rate||1); return t;}}
async function tick(){{try{{const r=await fetch('/api/watch/state/'+room,{{cache:'no-store'}}); if(!r.ok) throw new Error('HTTP '+r.status); const data=await r.json(); if(data.status!=='success'){{statusEl.textContent=data.message||'Room missing'; return;}} const st=data.room.state||{{}}; const clients=Object.keys(data.room.clients||{{}}).length; const target=hostTime(st,data.serverTime); lastHostTarget=target; statusEl.textContent=(data.room.title||'Watch Together')+' • host '+(st.paused?'paused':'playing')+' @ '+Math.floor(target)+'s • clients '+clients; if(!ready)return; applying=true; const drift=Math.abs((v.currentTime||0)-target); v.playbackRate=Number(st.rate||1); if(drift>0.75 && Date.now()-lastSeek>900){{v.currentTime=target; lastSeek=Date.now();}} if(st.paused && !v.paused) v.pause(); if(!st.paused && v.paused) v.play().catch(()=>{{}}); if(!st.paused && drift>0.15 && drift<=0.75){{v.playbackRate=(v.currentTime<target?1.035:.965)*Number(st.rate||1);}} applying=false;}}catch(e){{statusEl.textContent='Sync error: '+e.message+' · check host room/firewall'; applying=false;}}}}
v.addEventListener('seeking',()=>{{ if(!applying && ready && Math.abs((v.currentTime||0)-lastHostTarget)>1){{ try{{v.currentTime=lastHostTarget;}}catch(e){{}} }} }});
setInterval(tick,500); tick();
</script></body></html>
"""

# API exposed to the JavaScript layer

@app.post('/api/live_stream/create')
def api_live_stream_create():
    """Live desktop/player stream for TV: screen capture -> H264/AAC HLS.
    This is NOT file streaming. It captures what is shown on the host PC.
    Audio is included only if a Windows loopback device is configured (Stereo Mix / VB-CABLE).
    """
    import json, time, threading, shutil
    payload = bottle.request.json or {}
    title = str(payload.get('title') or 'ModernPlayer Live Stream')
    audio_device = str(payload.get('audio_device') or '').strip()
    if not audio_device:
        try:
            keys = API_INSTANCE._load_keys_dict() if API_INSTANCE else {}
            audio_device = str(keys.get('LIVE_STREAM_AUDIO_DEVICE') or os.environ.get('LIVE_STREAM_AUDIO_DEVICE') or '').strip()
        except Exception:
            audio_device = os.environ.get('LIVE_STREAM_AUDIO_DEVICE', '').strip()
    fps = int(payload.get('fps') or 30)
    fps = max(15, min(60, fps))
    bitrate = str(payload.get('bitrate') or '12000k')
    ffmpeg = get_ffmpeg_path() or 'ffmpeg'
    code = make_room_code()
    safe_root = os.path.join(get_safe_temp_dir(), 'modernplayer_live_streams')
    out_dir = os.path.join(safe_root, code)
    try:
        if os.path.exists(out_dir): shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass
    index_path = os.path.join(out_dir, 'index.m3u8')
    LIVE_STREAMS[code] = {
        'code': code, 'title': title, 'dir': out_dir, 'status': 'starting', 'progress': 0,
        'message': 'Starting live stream...', 'created': time.time(), 'audio_device': audio_device or '',
        'has_audio': bool(audio_device)
    }

    def worker():
        try:
            # Low-delay-ish HLS. Quality is high; latency depends on TV browser buffering.
            cmd = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-nostdin']
            if os.name == 'nt':
                cmd += ['-f', 'gdigrab', '-framerate', str(fps), '-i', 'desktop']
                if audio_device:
                    cmd += ['-f', 'dshow', '-i', f'audio={audio_device}']
            else:
                # Linux fallback: X11 display, video only by default.
                cmd += ['-f', 'x11grab', '-framerate', str(fps), '-i', os.environ.get('DISPLAY', ':0.0')]
            cmd += ['-map', '0:v:0']
            if audio_device and os.name == 'nt':
                cmd += ['-map', '1:a:0']
            else:
                cmd += ['-an']
            cmd += [
                '-vf', 'scale=w=min(1920\\,iw):h=-2',
                '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'zerolatency',
                '-crf', '18', '-maxrate', bitrate, '-bufsize', '24000k',
                '-pix_fmt', 'yuv420p', '-g', str(fps * 2), '-keyint_min', str(fps * 2),
            ]
            if audio_device and os.name == 'nt':
                cmd += ['-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-ar', '48000']
            cmd += [
                '-f', 'hls', '-hls_time', '1', '-hls_list_size', '8',
                '-hls_flags', 'delete_segments+independent_segments+program_date_time',
                '-hls_delete_threshold', '4', index_path
            ]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            LIVE_STREAMS[code].update({'status': 'running', 'message': 'Live stream running. Open link on TV.'})
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
            LIVE_STREAMS[code]['pid'] = proc.pid
            _, err = proc.communicate()
            rc = proc.returncode
            if rc == 0:
                LIVE_STREAMS[code].update({'status': 'stopped', 'message': 'Live stream stopped'})
            else:
                LIVE_STREAMS[code].update({'status': 'error', 'message': (err or f'ffmpeg exited {rc}')[-1200:]})
        except Exception as e:
            LIVE_STREAMS[code].update({'status': 'error', 'message': str(e)})
    threading.Thread(target=worker, daemon=True).start()
    ips = get_all_lan_ips()
    urls = []
    for ip in ips:
        label = 'Radmin VPN' if ip.startswith('26.') else ('Tailscale' if ip.startswith('100.') else 'LAN')
        urls.append({'label': label, 'ip': ip, 'url': f'http://{ip}:{PORT}/live/{code}', 'status_url': f'http://{ip}:{PORT}/api/live_stream/status/{code}'})
    return json.dumps({'status': 'success', 'code': code, 'urls': urls, 'lan_url': urls[0]['url'] if urls else f'http://127.0.0.1:{PORT}/live/{code}', 'local_url': f'http://127.0.0.1:{PORT}/live/{code}', 'audio_device': audio_device, 'has_audio': bool(audio_device)}, ensure_ascii=False)


@app.get('/api/live_stream/status/<code>')
def api_live_stream_status(code):
    import json
    st = LIVE_STREAMS.get(str(code))
    if not st:
        return json.dumps({'status': 'missing', 'message': 'live stream not found'}, ensure_ascii=False)
    safe = {k: v for k, v in st.items() if k not in ('dir', 'pid')}
    safe['playlist_ready'] = os.path.exists(os.path.join(st.get('dir',''), 'index.m3u8'))
    return json.dumps({'status': 'success', 'stream': safe}, ensure_ascii=False)


@app.post('/api/live_stream/stop/<code>')
def api_live_stream_stop(code):
    import json, signal
    st = LIVE_STREAMS.get(str(code))
    if not st:
        return json.dumps({'status': 'missing'}, ensure_ascii=False)
    pid = st.get('pid')
    try:
        if pid:
            if os.name == 'nt':
                subprocess.Popen(['taskkill', '/PID', str(pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(int(pid), signal.SIGTERM)
        st.update({'status': 'stopped', 'message': 'Live stream stopped'})
    except Exception as e:
        st.update({'status': 'error', 'message': str(e)})
    return json.dumps({'status': 'success'}, ensure_ascii=False)


@app.get('/live_hls/<code>/<filename:path>')
def live_hls_file(code, filename):
    st = LIVE_STREAMS.get(str(code))
    if not st:
        return bottle.HTTPError(404, 'live stream not found')
    ext = os.path.splitext(filename)[1].lower()
    mt = 'application/vnd.apple.mpegurl' if ext == '.m3u8' else ('video/mp2t' if ext == '.ts' else None)
    return bottle.static_file(filename, root=st.get('dir') or '', mimetype=mt) if mt else bottle.static_file(filename, root=st.get('dir') or '')


@app.get('/live/<code>')
def live_stream_page(code):
    safe = re.sub(r'[^0-9A-Za-z_-]', '', str(code))[:32]
    return f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ModernPlayer Live {safe}</title>
<style>html,body{{margin:0;height:100%;background:#000;color:#fff;font-family:Inter,Segoe UI,Arial,sans-serif;overflow:hidden}}video{{width:100vw;height:100vh;background:#000;object-fit:contain}}.status{{position:fixed;left:50%;top:18px;transform:translateX(-50%);z-index:5;background:rgba(8,8,14,.72);border:1px solid rgba(255,255,255,.12);border-radius:999px;padding:9px 14px;font-size:13px;backdrop-filter:blur(14px)}}.overlay{{position:fixed;inset:0;display:grid;place-items:center;background:radial-gradient(circle at 50% 35%,rgba(124,92,252,.22),transparent 35%),rgba(0,0,0,.72);z-index:4}}.card{{width:min(560px,calc(100vw - 40px));background:rgba(12,12,18,.9);border:1px solid rgba(255,255,255,.12);border-radius:24px;padding:28px;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.6)}}.logo{{font-size:48px}}button{{height:46px;border:0;border-radius:16px;background:#7c5cfc;color:#fff;font-weight:900;padding:0 22px}}</style></head>
<body><div class='status' id='status'>Preparing live stream…</div><video id='v' controls autoplay playsinline></video><div class='overlay' id='overlay'><div class='card'><div class='logo'>:3</div><h1>Live Stream</h1><p>This is the host PC screen stream. Press Start once.</p><button id='start'>Start watching</button></div></div><script>
const code='{safe}', v=document.getElementById('v'), statusEl=document.getElementById('status'), overlay=document.getElementById('overlay');
const src='/live_hls/'+code+'/index.m3u8'; v.src=src;
document.getElementById('start').onclick=()=>{{overlay.style.display='none'; v.play().catch(()=>{{}});}};
async function poll(){{try{{const r=await fetch('/api/live_stream/status/'+code,{{cache:'no-store'}});const j=await r.json();if(j.status==='success'){{const s=j.stream;statusEl.textContent=(s.message||s.status)+(s.has_audio?' • audio':' • no audio device'); if(s.playlist_ready && !v.src.endsWith('index.m3u8')) v.src=src;}}else statusEl.textContent=j.message||'stream missing';}}catch(e){{statusEl.textContent='status error: '+e.message;}}}}
setInterval(poll,1000); poll();
</script></body></html>
"""

@app.post('/api/tv_stream/create')
def api_tv_stream_create():
    """Create browser/TV compatible HLS stream from a local file.
    This solves codec issues (MKV/HEVC/EAC3) for TV browsers, but the TV still must reach this PC
    via LAN, Radmin-compatible route, public tunnel, or future cloud relay.
    """
    import json, time, threading, uuid, shutil
    payload = bottle.request.json or {}
    path = urllib.parse.unquote(str(payload.get('path') or '')).strip('"' + "'")
    title = str(payload.get('title') or os.path.basename(path) or 'TV Stream')
    if not path or not os.path.exists(path):
        return json.dumps({'status': 'error', 'message': 'media file not found'}, ensure_ascii=False)
    ffmpeg = get_ffmpeg_path() or 'ffmpeg'
    code = make_room_code()
    safe_root = os.path.join(get_safe_temp_dir(), 'modernplayer_tv_streams')
    out_dir = os.path.join(safe_root, code)
    try:
        if os.path.exists(out_dir): shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass
    index_path = os.path.join(out_dir, 'index.m3u8')
    TV_STREAMS[code] = {'code': code, 'title': title, 'path': path, 'dir': out_dir, 'status': 'starting', 'progress': 0, 'message': 'Starting TV stream...', 'created': time.time()}

    def worker():
        try:
            dur = None
            try:
                cfg = nohomo_merger_core.load_config(get_workflow_dir()) if nohomo_merger_core else {'ffprobe_path': 'ffprobe'}
                dur = nohomo_merger_core.get_duration(path, cfg) if nohomo_merger_core else None
            except Exception:
                pass
            # HLS event playlist: TV can start while FFmpeg is still transcoding.
            cmd = [
                ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-nostdin',
                '-i', path,
                '-map', '0:v:0', '-map', '0:a:0?',
                '-vf', 'scale=w=min(1920\\,iw):h=-2',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                '-maxrate', '5500k', '-bufsize', '11000k',
                '-c:a', 'aac', '-b:a', '160k', '-ac', '2',
                '-sn', '-dn',
                '-f', 'hls', '-hls_time', '2', '-hls_list_size', '0',
                '-hls_flags', 'independent_segments',
                '-progress', 'pipe:1', '-nostats',
                index_path
            ]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
            TV_STREAMS[code].update({'status': 'running', 'message': 'Transcoding TV stream... open link on TV'})
            if proc.stdout:
                for line in proc.stdout:
                    line = line.strip()
                    if line.startswith('out_time_ms=') and dur:
                        try:
                            out_s = float(line.split('=', 1)[1]) / 1000000.0
                            pct = max(0, min(99, int(out_s * 100 / dur)))
                            TV_STREAMS[code].update({'progress': pct, 'message': f'Transcoding TV stream... {pct}%'})
                        except Exception:
                            pass
                    elif line == 'progress=end':
                        TV_STREAMS[code].update({'progress': 100})
            rc = proc.wait()
            if rc == 0 and os.path.exists(index_path):
                TV_STREAMS[code].update({'status': 'ready', 'progress': 100, 'message': 'TV stream ready'})
            else:
                TV_STREAMS[code].update({'status': 'error', 'message': f'ffmpeg failed with code {rc}'})
        except Exception as e:
            TV_STREAMS[code].update({'status': 'error', 'message': str(e)})
    threading.Thread(target=worker, daemon=True).start()
    ips = get_all_lan_ips()
    urls = []
    for ip in ips:
        label = 'Radmin VPN' if ip.startswith('26.') else ('Tailscale' if ip.startswith('100.') else 'LAN')
        urls.append({'label': label, 'ip': ip, 'url': f'http://{ip}:{PORT}/tv_stream/{code}', 'status_url': f'http://{ip}:{PORT}/api/tv_stream/status/{code}'})
    return json.dumps({'status': 'success', 'code': code, 'pin': code, 'urls': urls, 'lan_url': urls[0]['url'] if urls else f'http://127.0.0.1:{PORT}/tv_stream/{code}', 'local_url': f'http://127.0.0.1:{PORT}/tv_stream/{code}'}, ensure_ascii=False)


@app.get('/api/tv_stream/status/<code>')
def api_tv_stream_status(code):
    import json
    st = TV_STREAMS.get(str(code))
    if not st:
        return json.dumps({'status': 'missing', 'message': 'stream not found'}, ensure_ascii=False)
    safe = {k: v for k, v in st.items() if k not in ('path', 'dir')}
    safe['playlist_ready'] = os.path.exists(os.path.join(st.get('dir',''), 'index.m3u8'))
    return json.dumps({'status': 'success', 'stream': safe}, ensure_ascii=False)


@app.get('/hls/<code>/<filename:path>')
def hls_file(code, filename):
    st = TV_STREAMS.get(str(code))
    if not st:
        return bottle.HTTPError(404, 'stream not found')
    ext = os.path.splitext(filename)[1].lower()
    mt = 'application/vnd.apple.mpegurl' if ext == '.m3u8' else ('video/mp2t' if ext == '.ts' else None)
    return bottle.static_file(filename, root=st.get('dir') or '', mimetype=mt) if mt else bottle.static_file(filename, root=st.get('dir') or '')


@app.get('/tv_stream/<code>')
def tv_stream_page(code):
    safe = re.sub(r'[^0-9A-Za-z_-]', '', str(code))[:32]
    return f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ModernPlayer TV Stream {safe}</title>
<style>html,body{{margin:0;height:100%;background:#000;color:#fff;font-family:Inter,Segoe UI,Arial,sans-serif;overflow:hidden}}video{{width:100vw;height:100vh;background:#000;object-fit:contain}}.status{{position:fixed;left:50%;top:18px;transform:translateX(-50%);z-index:5;background:rgba(8,8,14,.72);border:1px solid rgba(255,255,255,.12);border-radius:999px;padding:9px 14px;font-size:13px;backdrop-filter:blur(14px)}}.overlay{{position:fixed;inset:0;display:grid;place-items:center;background:radial-gradient(circle at 50% 35%,rgba(124,92,252,.22),transparent 35%),rgba(0,0,0,.72);z-index:4}}.card{{width:min(560px,calc(100vw - 40px));background:rgba(12,12,18,.9);border:1px solid rgba(255,255,255,.12);border-radius:24px;padding:28px;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.6)}}.logo{{font-size:48px}}button{{height:46px;border:0;border-radius:16px;background:#7c5cfc;color:#fff;font-weight:900;padding:0 22px}}</style></head>
<body><div class='status' id='status'>Preparing TV stream…</div><video id='v' controls playsinline></video><div class='overlay' id='overlay'><div class='card'><div class='logo'>:3</div><h1>TV Stream</h1><p>This mode transcodes video to H264 AAC for TV browser compatibility. Press Start once.</p><button id='start'>Start watching</button></div></div><script>
const code='{safe}', v=document.getElementById('v'), statusEl=document.getElementById('status'), overlay=document.getElementById('overlay');
const src='/hls/'+code+'/index.m3u8'; v.src=src;
document.getElementById('start').onclick=()=>{{overlay.style.display='none'; v.play().catch(()=>{{}});}};
async function poll(){{try{{const r=await fetch('/api/tv_stream/status/'+code,{{cache:'no-store'}});const j=await r.json();if(j.status==='success'){{const s=j.stream;statusEl.textContent=(s.message||s.status)+' • '+(s.progress||0)+'%'; if(s.playlist_ready && !v.src.endsWith('index.m3u8')) v.src=src;}}else statusEl.textContent=j.message||'stream missing';}}catch(e){{statusEl.textContent='status error: '+e.message;}}}}
setInterval(poll,1000); poll();
</script></body></html>
"""

@app.get('/tv')
def tv_join_page():
    return """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ModernPlayer TV</title>
<style>html,body{margin:0;height:100%;background:#050508;color:#fff;font-family:Inter,Segoe UI,Arial,sans-serif;display:grid;place-items:center}.card{width:min(520px,calc(100vw - 40px));padding:30px;border-radius:24px;background:rgba(16,16,24,.86);border:1px solid rgba(255,255,255,.12);text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.55)}.logo{font-size:54px}h1{margin:8px 0 10px}.pin{display:flex;gap:10px;margin-top:18px}input{flex:1;height:46px;border-radius:14px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);color:#fff;font-size:22px;text-align:center;letter-spacing:.18em}button{height:46px;border:0;border-radius:14px;background:#7c5cfc;color:#fff;font-weight:900;padding:0 18px}</style></head>
<body><div class='card'><div class='logo'>:3</div><h1>ModernPlayer TV</h1><p>Enter the PIN shown on your computer.</p><div class='pin'><input id='pin' maxlength='8' autofocus><button onclick='go()'>Join</button></div></div><script>function go(){const p=document.getElementById('pin').value.trim(); if(p) location.href='/tv/'+encodeURIComponent(p)}; document.getElementById('pin').addEventListener('keydown',e=>{if(e.key==='Enter')go()});</script></body></html>
"""


@app.post('/api/tv/create')
def api_tv_create():
    import json, time
    payload = bottle.request.json or {}
    path = urllib.parse.unquote(str(payload.get('path') or '')).strip('"' + "'")
    if not path or not os.path.exists(path):
        return json.dumps({'status': 'error', 'message': 'current media file not found'}, ensure_ascii=False)
    code = make_room_code()
    now = time.time()
    TV_ROOMS[code] = {
        'code': code,
        'created': now,
        'updated': now,
        'title': payload.get('title') or os.path.basename(path),
        'path': path,
        'duration': float(payload.get('duration') or 0),
        'state': {
            'paused': True,
            'time': float(payload.get('time') or 0),
            'rate': float(payload.get('rate') or 1),
            'updatedAt': now
        }
    }
    ips = get_all_lan_ips()
    lan = ips[0] if ips else get_lan_ip()
    urls = []
    for ip in ips:
        label = 'Radmin VPN' if ip.startswith('26.') else ('Tailscale' if ip.startswith('100.') else 'LAN')
        urls.append({'label': label, 'ip': ip, 'url': f'http://{ip}:{PORT}/tv/{code}', 'join_url': f'http://{ip}:{PORT}/tv'})
    bottle.response.content_type = 'application/json; charset=utf-8'
    return json.dumps({
        'status': 'success',
        'pin': code,
        'local_url': f'http://127.0.0.1:{PORT}/tv/{code}',
        'lan_url': f'http://{lan}:{PORT}/tv/{code}',
        'join_url': f'http://{lan}:{PORT}/tv',
        'urls': urls,
        'host_ip': lan,
        'all_ips': ips,
        'port': PORT
    }, ensure_ascii=False)


@app.post('/api/tv/update/<code>')
def api_tv_update(code):
    import json, time
    room = TV_ROOMS.get(str(code))
    if not room:
        return json.dumps({'status': 'missing', 'message': 'TV room not found'}, ensure_ascii=False)
    payload = bottle.request.json or {}
    now = time.time()
    room['updated'] = now
    if payload.get('title'):
        room['title'] = payload.get('title')
    if payload.get('duration') is not None:
        try: room['duration'] = float(payload.get('duration') or 0)
        except Exception: pass
    if payload.get('path'):
        path = urllib.parse.unquote(str(payload.get('path'))).strip('"' + "'")
        if os.path.exists(path): room['path'] = path
    st = room.setdefault('state', {})
    if payload.get('paused') is not None: st['paused'] = bool(payload.get('paused'))
    if payload.get('time') is not None:
        try: st['time'] = float(payload.get('time') or 0)
        except Exception: pass
    if payload.get('rate') is not None:
        try: st['rate'] = float(payload.get('rate') or 1)
        except Exception: pass
    st['updatedAt'] = now
    return json.dumps({'status': 'success'}, ensure_ascii=False)


@app.get('/api/tv/state/<code>')
def api_tv_state(code):
    import json, time
    room = TV_ROOMS.get(str(code))
    if not room:
        return json.dumps({'status': 'missing', 'message': 'TV room not found'}, ensure_ascii=False)
    bottle.response.content_type = 'application/json; charset=utf-8'
    safe = {k:v for k,v in room.items() if k != 'path'}
    safe['has_media'] = os.path.exists(room.get('path',''))
    return json.dumps({'status': 'success', 'room': safe, 'serverTime': time.time()}, ensure_ascii=False)


@app.get('/tv_media/<code>')
def tv_media(code):
    room = TV_ROOMS.get(str(code))
    if not room:
        return bottle.HTTPError(404, 'TV room not found')
    path = room.get('path') or ''
    if not os.path.exists(path):
        return bottle.HTTPError(404, 'Media file not found')
    ext = os.path.splitext(path)[1].lower()
    mimetype = None
    if ext == '.mp4': mimetype = 'video/mp4'
    elif ext == '.webm': mimetype = 'video/webm'
    elif ext == '.mkv': mimetype = 'video/x-matroska'
    elif ext == '.ts': mimetype = 'video/mp2t'
    return bottle.static_file(os.path.basename(path), root=os.path.dirname(path), mimetype=mimetype) if mimetype else bottle.static_file(os.path.basename(path), root=os.path.dirname(path))


@app.get('/tv/<code>')
def tv_room_page(code):
    safe_code = re.sub(r'[^0-9A-Za-z_-]', '', str(code))[:32]
    return f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ModernPlayer TV {safe_code}</title>
<style>
html,body{{margin:0;height:100%;background:#000;color:#fff;font-family:Inter,Segoe UI,Arial,sans-serif;overflow:hidden}}
video{{width:100vw;height:100vh;background:#000;object-fit:contain}}
.overlay{{position:fixed;inset:0;display:grid;place-items:center;background:radial-gradient(circle at 50% 40%,rgba(124,92,252,.18),transparent 35%),rgba(0,0,0,.72);z-index:3}}
.card{{width:min(560px,calc(100vw - 40px));background:rgba(12,12,18,.88);border:1px solid rgba(255,255,255,.12);border-radius:24px;padding:28px;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.6)}}
.logo{{font-size:48px}} h1{{margin:8px 0 8px}} p{{color:rgba(255,255,255,.62);line-height:1.5}} button{{height:46px;border:0;border-radius:16px;background:#7c5cfc;color:#fff;font-weight:900;padding:0 20px;font-size:15px}}
.status{{position:fixed;left:18px;top:16px;z-index:4;background:rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.1);padding:8px 12px;border-radius:999px;font-size:12px;color:rgba(255,255,255,.75);backdrop-filter:blur(10px)}}
</style></head><body>
<div class='status' id='status'>Room {safe_code} · waiting for host…</div>
<video id='v' playsinline controls src='/tv_media/{safe_code}'></video>
<div class='overlay' id='overlay'><div class='card'><div class='logo'>:3</div><h1>TV connected</h1><p>Press Start once on the TV remote. After that, the computer controls play / pause / seek.</p><button id='start'>Start watching</button></div></div>
<script>
const code='{safe_code}', v=document.getElementById('v'), overlay=document.getElementById('overlay'), statusEl=document.getElementById('status');
let unlocked=false,lastSeek=0,applying=false;
document.getElementById('start').onclick=async()=>{{unlocked=true; overlay.style.display='none'; try{{await v.play();}}catch(e){{}}}};
function hostTime(st,serverTime){{let t=Number(st.time||0); if(!st.paused)t+=Math.max(0,Number(serverTime)-Number(st.updatedAt||serverTime))*Number(st.rate||1); return t;}}
async function tick(){{try{{const r=await fetch('/api/tv/state/'+code,{{cache:'no-store'}});const data=await r.json();if(data.status!=='success'){{statusEl.textContent=data.message||'room missing';return;}}const room=data.room,st=room.state||{{}};const target=hostTime(st,data.serverTime);statusEl.textContent=(room.title||'ModernPlayer TV')+' · '+(st.paused?'paused':'playing')+' · '+Math.floor(target)+'s'; if(!unlocked)return; applying=true; const drift=Math.abs((v.currentTime||0)-target); v.playbackRate=Number(st.rate||1); if(drift>0.9 && Date.now()-lastSeek>1000){{v.currentTime=target;lastSeek=Date.now();}} if(st.paused && !v.paused)v.pause(); if(!st.paused && v.paused)v.play().catch(()=>{{}}); if(!st.paused && drift>0.18 && drift<=0.9){{v.playbackRate=(v.currentTime<target?1.03:.97)*Number(st.rate||1);}} applying=false;}}catch(e){{statusEl.textContent='sync error: '+e.message;applying=false;}}}}
setInterval(tick,500); tick();
</script></body></html>
"""


class PlayerAPI:
    def __init__(self):
        self.window = None
        self._ai_franchise_cache = {}
        self._ai_franchise_request_times = []
        self._media_tasks = {}

    def get_app_version(self):
        return "ModernPlayer-AgentBuild-10.2-ai-assistant"

    def _extract_prepare_query(self, text):
        """Local parser for assistant requests like 'prepare kill blue 7th episode'."""
        import re
        lower = (text or "").lower()
        aliases = {
            "kill blue": "Kill Blue",
            "kill ao": "Kill Blue",
            "убивая юность": "Kill Blue",
            "bleach": "Bleach",
            "блич": "Bleach",
            "fate": "Fate",
            "фейт": "Fate",
            "prison school": "Prison School",
            "школа тюрьма": "Prison School"
        }
        title = ""
        for k, v in aliases.items():
            if k in lower:
                title = v
                break
        ep = None
        patterns = [
            r's\s*0*(\d{1,2})\s*e\s*0*(\d{1,3})',
            r'(\d{1,3})\s*[- ]?\s*(?:st|nd|rd|th)?\s*(?:episode|ep)',
            r'(?:episode|ep)\s*0*(\d{1,3})',
            r'(?:сер(?:ия|ию|ии)?|эпизод)\s*0*(\d{1,3})',
            r'0*(\d{1,3})\s*(?:сер(?:ия|ию|ии)?|эпизод)'
        ]
        season = 1
        for pat in patterns:
            m = re.search(pat, lower)
            if m:
                if len(m.groups()) == 2:
                    season = int(m.group(1)); ep = int(m.group(2))
                else:
                    ep = int(m.group(1))
                break
        if title and ep:
            return title, season, ep, f"{title} S{season:02d}E{ep:02d}"
        return title, season, ep, title

    def _best_raw_candidate_for_query(self, query):
        """Runs existing Nyaa expert search and returns the best result object."""
        import json
        try:
            raw = self.search_nyaa_torrents(query, fast=True)
            data = json.loads(raw or "{}")
            results = data.get("results") or []
            if not results:
                return None, data
            # Prefer real video singles/batches with seeders; existing backend already sorts by score.
            best = results[0]
            return best, data
        except Exception as e:
            return None, {"status": "error", "message": str(e)}

    def torrent_add_raw(self, torrent_link="", magnet_link="", title=""):
        """Adds a RAW torrent to the internal libtorrent engine if available; otherwise stores the .torrent.
        Returns a clear status so the UI can tell the user what happened.
        """
        import json, urllib.request, time
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir()) if nohomo_merger_core else {"_base_dir": get_workflow_dir(), "raw_folder": "./raw"}
            raw_dir = nohomo_merger_core.resolve_path(cfg.get('raw_folder') or './raw', cfg) if nohomo_merger_core else os.path.join(get_workflow_dir(), 'raw')
            os.makedirs(raw_dir, exist_ok=True)
            torrent_dir = os.path.join(get_workflow_dir(), 'raw_torrents')
            os.makedirs(torrent_dir, exist_ok=True)

            # Try libtorrent first for a real internal torrent engine.
            try:
                import libtorrent as lt
                if not hasattr(self, '_lt_session'):
                    self._lt_session = lt.session()
                    try:
                        self._lt_session.listen_on(6881, 6891)
                    except Exception:
                        pass
                    # Make internal downloads behave like a real torrent client, not a passive handle.
                    # Without DHT/LSD/UPnP some public torrents sit forever at 0 peers / 0 KB/s.
                    try:
                        self._lt_session.start_dht()
                    except Exception:
                        pass
                    try:
                        self._lt_session.start_lsd()
                    except Exception:
                        pass
                    try:
                        self._lt_session.start_upnp()
                    except Exception:
                        pass
                    try:
                        self._lt_session.start_natpmp()
                    except Exception:
                        pass
                    try:
                        settings = {
                            'enable_dht': True,
                            'enable_lsd': True,
                            'enable_upnp': True,
                            'enable_natpmp': True,
                            'announce_to_all_trackers': True,
                            'announce_to_all_tiers': True,
                            'connections_limit': 200,
                            'active_downloads': 4,
                            'active_limit': 20,
                        }
                        if hasattr(self._lt_session, 'apply_settings'):
                            self._lt_session.apply_settings(settings)
                    except Exception:
                        pass
                params = {'save_path': raw_dir, 'storage_mode': lt.storage_mode_t.storage_mode_sparse}
                if magnet_link:
                    handle = lt.add_magnet_uri(self._lt_session, magnet_link, params)
                elif torrent_link:
                    req = urllib.request.Request(torrent_link, headers={'User-Agent': 'Mozilla/5.0'})
                    torrent_bytes = urllib.request.urlopen(req, timeout=20).read()
                    ti = lt.torrent_info(lt.bdecode(torrent_bytes))
                    params['ti'] = ti
                    handle = self._lt_session.add_torrent(params)
                else:
                    return json.dumps({"status": "error", "message": "No torrent or magnet link provided"}, ensure_ascii=False)
                self._lt_handles = getattr(self, '_lt_handles', [])
                self._lt_handles.append(handle)
                return json.dumps({"status": "started", "engine": "libtorrent", "save_path": raw_dir, "name": title or str(handle.name()), "download_id": str(len(self._lt_handles) - 1)}, ensure_ascii=False)
            except Exception as lt_error:
                # Fallback 1: qBittorrent Web API bridge if user configured it in keys.json.
                # This is the most reliable Windows option because python-libtorrent has no normal pip wheels.
                try:
                    qbit_url = os.environ.get('QBIT_URL', '')
                    qbit_user = os.environ.get('QBIT_USERNAME', '')
                    qbit_pass = os.environ.get('QBIT_PASSWORD', '')
                    keys_file = get_keys_file()
                    if os.path.exists(keys_file):
                        try:
                            with open(keys_file, 'r', encoding='utf-8') as f:
                                keys = json.load(f)
                            qbit_url = qbit_url or keys.get('QBIT_URL', '')
                            qbit_user = qbit_user or keys.get('QBIT_USERNAME', '')
                            qbit_pass = qbit_pass or keys.get('QBIT_PASSWORD', '')
                        except Exception:
                            pass
                    if qbit_url and qbit_user and qbit_pass:
                        import urllib.parse
                        import http.cookiejar
                        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                        qbit_url = qbit_url.rstrip('/')
                        login_data = urllib.parse.urlencode({'username': qbit_user, 'password': qbit_pass}).encode('utf-8')
                        login_req = urllib.request.Request(qbit_url + '/api/v2/auth/login', data=login_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                        login_resp = opener.open(login_req, timeout=10).read().decode('utf-8', errors='replace')
                        if login_resp.strip().lower() != 'ok.':
                            raise Exception('qBittorrent login failed')
                        torrent_url = magnet_link or torrent_link
                        if not torrent_url:
                            raise Exception('No magnet/torrent URL for qBittorrent')
                        add_data = urllib.parse.urlencode({
                            'urls': torrent_url,
                            'savepath': raw_dir,
                            'category': 'raw',
                            'paused': 'false'
                        }).encode('utf-8')
                        add_req = urllib.request.Request(qbit_url + '/api/v2/torrents/add', data=add_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                        add_resp = opener.open(add_req, timeout=15).read().decode('utf-8', errors='replace')
                        return json.dumps({"status": "started", "engine": "qbittorrent_webapi", "save_path": raw_dir, "name": title or torrent_url, "response": add_resp}, ensure_ascii=False)
                except Exception as qbit_error:
                    log_to_file(f"qBittorrent fallback failed: {qbit_error}")

                # Fallback 2: save .torrent into raw_torrents. User/external torrent client can pick it up.
                if torrent_link:
                    safe = re.sub(r'[^a-zA-Z0-9._ -]+', '_', title or ('raw_' + str(int(time.time())))).strip()[:160] or 'raw_download'
                    path = os.path.join(torrent_dir, safe + '.torrent')
                    req = urllib.request.Request(torrent_link, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=20) as response:
                        with open(path, 'wb') as f:
                            f.write(response.read())
                    return json.dumps({"status": "saved_torrent", "engine": "fallback", "path": path, "save_path": raw_dir, "message": "python-libtorrent is unavailable on this Windows/Python. Configure qBittorrent WebUI in keys.json for automatic raw/ downloading. Torrent file was saved."}, ensure_ascii=False)
                return json.dumps({"status": "error", "message": "Internal torrent engine unavailable: " + str(lt_error)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


    def torrent_status(self):
        """Returns progress for internal libtorrent RAW downloads."""
        import json
        items = []
        try:
            handles = getattr(self, '_lt_handles', []) or []
            for idx, h in enumerate(handles):
                try:
                    st = h.status()
                    state = str(st.state)
                    progress = round(float(getattr(st, 'progress', 0.0)) * 100, 2)
                    total = int(getattr(st, 'total_wanted', 0) or 0)
                    done = int(getattr(st, 'total_wanted_done', 0) or 0)
                    trackers = []
                    try:
                        trackers = [str(t.get('url') or '') for t in h.trackers()] if hasattr(h, 'trackers') else []
                    except Exception:
                        trackers = []
                    items.append({
                        "id": str(idx),
                        "name": h.name() if hasattr(h, 'name') else '',
                        "progress": progress,
                        "downloaded_mb": round(done / 1048576, 2),
                        "total_mb": round(total / 1048576, 2),
                        "download_rate_kb": round(float(getattr(st, 'download_rate', 0)) / 1024, 1),
                        "upload_rate_kb": round(float(getattr(st, 'upload_rate', 0)) / 1024, 1),
                        "num_peers": int(getattr(st, 'num_peers', 0)),
                        "num_seeds": int(getattr(st, 'num_seeds', 0)) if hasattr(st, 'num_seeds') else 0,
                        "state": state,
                        "paused": bool(getattr(st, 'paused', False)),
                        "error": str(getattr(st, 'errc', '') or ''),
                        "trackers": trackers[:8],
                        "finished": bool(progress >= 99.9 or getattr(st, 'is_seeding', False))
                    })
                except Exception as e:
                    items.append({"id": str(idx), "status": "error", "message": str(e)})
            return json.dumps({"status": "success", "engine": "libtorrent", "downloads": items}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e), "downloads": items}, ensure_ascii=False)


    def watch_share_download_start(self, url, filename=""):
        """Download a Watch Together shared file from host into user's Downloads/ModernPlayerShared.
        Used by friend APP-MODE. Assumes the user confirmed the download in UI.
        """
        import json, threading, uuid, urllib.request, urllib.parse
        try:
            url = str(url or '').strip()
            if not (url.startswith('http://') or url.startswith('https://')):
                return json.dumps({"status": "error", "message": "invalid download url"}, ensure_ascii=False)
            safe_name = os.path.basename(urllib.parse.unquote(filename or '')) or 'watch_together_media.mkv'
            safe_name = re.sub(r'[\\/*?:"<>|]+', '_', safe_name).strip() or 'watch_together_media.mkv'
            out_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'ModernPlayerShared')
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, safe_name)
            task_id = str(uuid.uuid4())
            self._media_tasks[task_id] = {"status": "running", "mode": "watch_share_download", "progress": 0, "path": out_path, "name": safe_name, "message": "Downloading shared file... 0%"}

            def worker():
                tmp = out_path + '.part'
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'ModernPlayer/WatchTogether'})
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        total = int(resp.headers.get('Content-Length') or 0)
                        done = 0
                        with open(tmp, 'wb') as f:
                            while True:
                                chunk = resp.read(1024 * 512)
                                if not chunk:
                                    break
                                f.write(chunk)
                                done += len(chunk)
                                if total:
                                    pct = max(0, min(99, int(done * 100 / total)))
                                    self._media_tasks[task_id].update({"progress": pct, "message": f"Downloading shared file... {pct}% ({round(done/1048576,1)}/{round(total/1048576,1)} MB)"})
                    os.replace(tmp, out_path)
                    self._media_tasks[task_id].update({"status": "ready", "progress": 100, "path": out_path, "name": safe_name, "message": "Shared file downloaded"})
                except Exception as e:
                    self._media_tasks[task_id].update({"status": "error", "progress": 0, "message": str(e)})
                    try:
                        if os.path.exists(tmp): os.remove(tmp)
                    except Exception:
                        pass
            threading.Thread(target=worker, daemon=True).start()
            return json.dumps({"status": "processing", "task_id": task_id, "path": out_path, "name": safe_name}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


    def chromecast_list_devices(self, timeout=6):
        """Discover Chromecast / Google Cast devices on the LAN."""
        import json
        try:
            try:
                import pychromecast
            except Exception as e:
                return json.dumps({
                    "status": "missing_dependency",
                    "message": "pychromecast is not installed. Run: python -m pip install pychromecast zeroconf, then rebuild ModernPlayer.",
                    "error": str(e)
                }, ensure_ascii=False)
            chromecasts, browser = pychromecast.get_chromecasts(timeout=int(timeout or 6))
            devices = []
            for cc in chromecasts:
                try:
                    info = cc.cast_info
                    devices.append({
                        "name": getattr(info, 'friendly_name', '') or getattr(cc, 'name', '') or 'Chromecast',
                        "uuid": str(getattr(info, 'uuid', '') or ''),
                        "model": getattr(info, 'model_name', '') or '',
                        "host": getattr(info, 'host', '') or '',
                        "port": getattr(info, 'port', '') or ''
                    })
                except Exception:
                    try:
                        devices.append({"name": cc.name, "uuid": str(cc.uuid), "model": getattr(cc, 'model_name', ''), "host": getattr(cc, 'host', ''), "port": getattr(cc, 'port', '')})
                    except Exception:
                        pass
            try:
                pychromecast.discovery.stop_discovery(browser)
            except Exception:
                pass
            return json.dumps({"status": "success", "devices": devices}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def chromecast_play_url(self, device_id="", url="", title="ModernPlayer Live Stream", content_type="application/vnd.apple.mpegurl"):
        """Cast an accessible media URL to a Chromecast device."""
        import json, time
        try:
            try:
                import pychromecast
            except Exception as e:
                return json.dumps({"status": "missing_dependency", "message": "pychromecast is not installed. Run: python -m pip install pychromecast zeroconf, then rebuild ModernPlayer.", "error": str(e)}, ensure_ascii=False)
            device_id = str(device_id or '').strip()
            url = str(url or '').strip()
            if not url:
                return json.dumps({"status": "error", "message": "empty cast URL"}, ensure_ascii=False)
            chromecasts, browser = pychromecast.get_chromecasts(timeout=8)
            target = None
            for cc in chromecasts:
                info = getattr(cc, 'cast_info', None)
                uuid = str(getattr(info, 'uuid', '') or getattr(cc, 'uuid', '') or '')
                name = str(getattr(info, 'friendly_name', '') or getattr(cc, 'name', '') or '')
                if device_id and (device_id == uuid or device_id.lower() == name.lower()):
                    target = cc
                    break
            if not target and chromecasts:
                target = chromecasts[0]
            if not target:
                try: pychromecast.discovery.stop_discovery(browser)
                except Exception: pass
                return json.dumps({"status": "not_found", "message": "No Chromecast device found"}, ensure_ascii=False)
            target.wait(timeout=10)
            mc = target.media_controller
            mc.play_media(url, content_type or 'application/vnd.apple.mpegurl', title=title or 'ModernPlayer Live Stream')
            try:
                mc.block_until_active(timeout=10)
            except Exception:
                pass
            try:
                pychromecast.discovery.stop_discovery(browser)
            except Exception:
                pass
            return json.dumps({"status": "success", "device": getattr(target, 'name', str(device_id)), "url": url}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def _load_keys_dict(self):
        import json
        data = {}
        keys_file = get_keys_file()
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
            except Exception as e:
                log_to_file(f"Failed to read keys/config json: {e}")
        return data

    def _get_dub_provider_config(self):
        """External DUB provider config.
        Expected keys.json fields:
          DUB_PROVIDER_COMMAND: "python rezka_dub.py"
          PREFERRED_DUB_ORDER: ["Дубляж", "JAM", "AniLibria"]
        Optional template mode:
          DUB_PROVIDER_COMMAND: "python rezka_dub.py {action} --title {title} --season {season} --episode {episode} --voice {voice} --output {output}"
        """
        keys = self._load_keys_dict()
        cmd = os.environ.get("DUB_PROVIDER_COMMAND", "") or keys.get("DUB_PROVIDER_COMMAND", "")
        prefs = keys.get("PREFERRED_DUB_ORDER", None)
        if prefs is None:
            prefs = os.environ.get("PREFERRED_DUB_ORDER", "")
        if isinstance(prefs, str):
            prefs = [x.strip() for x in prefs.split(',') if x.strip()]
        if not isinstance(prefs, list) or not prefs:
            prefs = ["Дубляж", "JAM", "AniLibria", "AniDub", "AniMaunt", "StudioBand", "Субтитры"]
        return {"command": str(cmd or "").strip(), "preferred": prefs}

    def _run_dub_provider(self, action, title, season=1, episode=0, voice="", output_dir=""):
        import json, shlex, subprocess
        cfg = self._get_dub_provider_config()
        command = cfg.get("command", "")
        if not command:
            return {"status": "not_configured", "message": "DUB_PROVIDER_COMMAND is not configured in keys.json"}
        if not output_dir:
            if nohomo_merger_core:
                mcfg = nohomo_merger_core.load_config(get_workflow_dir())
                output_dir = nohomo_merger_core.resolve_path(mcfg.get('dub_folder') or './dub', mcfg)
            else:
                output_dir = os.path.join(get_workflow_dir(), 'dub')
        os.makedirs(output_dir, exist_ok=True)

        # Two modes: template command or base command + standard subcommand args.
        if "{action}" in command or "{title}" in command or "{episode}" in command:
            formatted = command.format(
                action=action,
                title=title,
                season=int(season or 1),
                episode=int(episode or 0),
                voice=voice or "",
                output=output_dir
            )
            args = shlex.split(formatted, posix=(os.name != 'nt'))
        else:
            args = shlex.split(command, posix=(os.name != 'nt'))
            args += [action, "--title", str(title)]
            if action == "download":
                args += ["--season", str(int(season or 1)), "--episode", str(int(episode or 0)), "--output", str(output_dir)]
                if voice:
                    args += ["--voice", str(voice)]

        log_to_file("Running external DUB provider: " + " ".join(args))
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', timeout=3600, startupinfo=startupinfo)
        stdout = (proc.stdout or '').strip()
        stderr = (proc.stderr or '').strip()
        # Provider should print JSON. Accept last JSON-looking object from stdout.
        parsed = None
        for candidate in reversed([x.strip() for x in stdout.splitlines() if x.strip()]):
            if candidate.startswith('{') and candidate.endswith('}'):
                try:
                    parsed = json.loads(candidate)
                    break
                except Exception:
                    pass
        if parsed is None:
            parsed = {"status": "success" if proc.returncode == 0 else "error", "stdout": stdout[-4000:], "stderr": stderr[-4000:]}
        parsed.setdefault("returncode", proc.returncode)
        if proc.returncode != 0 and parsed.get("status") == "success":
            parsed["status"] = "error"
        if stderr and "stderr" not in parsed:
            parsed["stderr"] = stderr[-4000:]
        return parsed

    def dub_provider_list_voices(self, title):
        import json
        try:
            res = self._run_dub_provider("list-voices", title)
            return json.dumps(res, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def _choose_preferred_dub_voice(self, voices):
        cfg = self._get_dub_provider_config()
        prefs = [str(x).lower() for x in cfg.get("preferred", [])]
        if not isinstance(voices, list) or not voices:
            return ""
        def voice_name(v):
            if isinstance(v, dict):
                return str(v.get('name') or v.get('title') or v.get('voice') or '')
            return str(v)
        for pref in prefs:
            for v in voices:
                name = voice_name(v)
                if pref and pref in name.lower():
                    return name
        return voice_name(voices[0])

    def dub_provider_download_episode(self, title, season=1, episode=1, voice=""):
        """Starts external DUB provider download in a background thread.
        The provider is a user-owned black box; the player only receives files in dub/.
        """
        import json, threading
        try:
            title = str(title or '').strip()
            season = int(season or 1)
            episode = int(episode or 1)
            if not title:
                return json.dumps({"status": "error", "message": "Missing title"}, ensure_ascii=False)
            if not voice:
                try:
                    voices_res = self._run_dub_provider("list-voices", title)
                    voice = self._choose_preferred_dub_voice(voices_res.get('voices') or voices_res.get('data') or [])
                except Exception as e:
                    log_to_file(f"Voice auto-selection failed: {e}")
                    voice = ""
            def worker():
                try:
                    res = self._run_dub_provider("download", title, season, episode, voice)
                    log_to_file(f"External DUB provider download result: {res}")
                except Exception as e:
                    log_to_file(f"External DUB provider worker failed: {e}")
            threading.Thread(target=worker, daemon=True).start()
            return json.dumps({"status": "started", "title": title, "season": season, "episode": episode, "voice": voice}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)



    def _get_flaresolverr_config(self):
        keys = self._load_keys_dict()
        return {
            "path": os.environ.get("FLARESOLVERR_PATH") or keys.get("FLARESOLVERR_PATH") or "",
            "url": (os.environ.get("FLARESOLVERR_URL") or keys.get("FLARESOLVERR_URL") or "http://127.0.0.1:8191").rstrip('/'),
            "autostart": bool(keys.get("FLARESOLVERR_AUTOSTART", False)) or os.environ.get("FLARESOLVERR_AUTOSTART", "").lower() in ("1", "true", "yes")
        }

    def _http_alive(self, url, timeout=2.5):
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.status < 500
        except Exception:
            return False

    def ensure_flaresolverr(self):
        """Starts FlareSolverr if configured and not running.
        Returns a JSON-serializable status dict. This prevents Prowlarr indexers from failing with localhost:8191 refused.
        """
        import subprocess, time, json
        cfg = self._get_flaresolverr_config()
        url = cfg.get("url") or "http://127.0.0.1:8191"
        if self._http_alive(url):
            return {"status": "running", "url": url}
        if not cfg.get("autostart"):
            return {"status": "stopped", "url": url, "message": "FlareSolverr is not running and autostart is disabled"}
        exe = cfg.get("path") or ""
        if not exe or not os.path.exists(exe):
            return {"status": "missing", "url": url, "path": exe, "message": "FLARESOLVERR_PATH is missing or invalid"}
        try:
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            subprocess.Popen([exe], cwd=os.path.dirname(exe), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo, creationflags=creationflags)
            for _ in range(20):
                time.sleep(0.5)
                if self._http_alive(url):
                    log_to_file(f"FlareSolverr autostart OK: {url}")
                    return {"status": "started", "url": url, "path": exe}
            return {"status": "timeout", "url": url, "path": exe, "message": "FlareSolverr did not become ready in time"}
        except Exception as e:
            return {"status": "error", "url": url, "path": exe, "message": str(e)}

    def _get_movie_raw_provider_config(self):
        keys = self._load_keys_dict()
        return {
            "provider": (os.environ.get("MOVIE_RAW_PROVIDER") or keys.get("MOVIE_RAW_PROVIDER") or "prowlarr").lower(),
            "prowlarr_url": (os.environ.get("PROWLARR_URL") or keys.get("PROWLARR_URL") or "").rstrip('/'),
            "prowlarr_api_key": os.environ.get("PROWLARR_API_KEY") or keys.get("PROWLARR_API_KEY") or ""
        }

    def _normalize_movie_query(self, user_message):
        import re
        original = str(user_message or "")
        # Canonicalize known titles before removing helper words.
        known = [
            (r'\bzodiac\b', 'Zodiac 2007'),
            (r'\beyes\s+wide\s+shut\b', 'Eyes Wide Shut 1999'),
        ]
        for pattern, canonical in known:
            if re.search(pattern, original, re.IGNORECASE):
                return canonical
        q = original
        q = re.sub(r'\b(can\s+you|could\s+you|would\s+you|please|pls|can|you|me|i\s+want\s+to|i\s+need\s+to)\b', ' ', q, flags=re.IGNORECASE)
        q = re.sub(r'\b(get|give|find|download|best|raw|quality|movie|film|in|for|the)\b', ' ', q, flags=re.IGNORECASE)
        q = re.sub(r'\b(by|director|directed by|from)\b.*$', ' ', q, flags=re.IGNORECASE)
        q = re.sub(r'\s+', ' ', q).strip(' ,.-')
        return q or original.strip()


    def movie_raw_search(self, query):
        """Searches movie/show RAW via configured provider. Currently supports Prowlarr local API.
        Uses query expansion because movie indexers often name releases as `Title.Year.Quality...`
        and a single human query can be too narrow.
        """
        import json, urllib.request, urllib.parse, re, time
        cfg = self._get_movie_raw_provider_config()
        flaresolverr_status = self.ensure_flaresolverr()
        provider = cfg.get('provider') or 'prowlarr'
        if provider != 'prowlarr':
            return json.dumps({"status": "error", "message": f"Unsupported movie RAW provider: {provider}"}, ensure_ascii=False)
        if not cfg.get('prowlarr_url') or not cfg.get('prowlarr_api_key'):
            return json.dumps({
                "status": "not_configured",
                "flaresolverr": flaresolverr_status,
                "message": "Movie/show RAW needs Prowlarr. Add PROWLARR_URL and PROWLARR_API_KEY to keys.json.",
                "example": {"PROWLARR_URL": "http://127.0.0.1:9696", "PROWLARR_API_KEY": "your_api_key"}
            }, ensure_ascii=False)

        def clean_query(q):
            q = str(q or '').strip()
            q = re.sub(r'\s+', ' ', q)
            return q

        def get_enabled_indexer_ids():
            try:
                url = cfg['prowlarr_url'] + '/api/v1/indexer'
                req = urllib.request.Request(url, headers={'X-Api-Key': cfg['prowlarr_api_key'], 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read().decode('utf-8', errors='replace'))
                ids = []
                for item in data if isinstance(data, list) else []:
                    if item.get('enable', True) and item.get('id') is not None:
                        ids.append(str(item.get('id')))
                return ids
            except Exception as e:
                log_to_file(f'Prowlarr indexer list failed: {e}')
                return []

        def query_variants(q):
            q = clean_query(q)
            variants = []
            def add(x):
                x = clean_query(x)
                if x and x.lower() not in [v.lower() for v in variants]:
                    variants.append(x)
            # Known canonical titles / imdb IDs. Keep this short; long query fan-out causes UI waits.
            if re.search(r'\bzodiac\b', q, re.IGNORECASE):
                for x in ['Zodiac 2007', 'Zodiac 2007 1080p', 'Zodiac 2007 BluRay', 'Zodiac 2007 2160p', 'tt0443706']:
                    add(x)
                return variants
            if re.search(r'\beyes\s+wide\s+shut\b', q, re.IGNORECASE):
                for x in ['Eyes Wide Shut 1999', 'Eyes Wide Shut 1999 1080p', 'Eyes Wide Shut 1999 BluRay', 'Eyes Wide Shut 1999 2160p', 'tt0120663']:
                    add(x)
                return variants
            # Common ambiguous movie titles: Prowlarr/indexers often need the article/year/IMDb id.
            if re.search(r'\bdictator\b', q, re.IGNORECASE):
                for x in ['The Dictator 2012', 'The Dictator 2012 1080p', 'The Dictator 2012 BluRay', 'The Dictator 2012 2160p', 'tt1645170']:
                    add(x)
                return variants
            add(q)
            m = re.search(r'(.+?)\s+((?:19|20)\d{2})\b', q)
            if m:
                title = m.group(1).strip(); year = m.group(2)
                add(f'{title} {year} 1080p')
                add(f'{title} {year} BluRay')
                add(f'{title} {year} 2160p')
            else:
                add(f'{q} 1080p')
                add(f'{q} BluRay')
                add(f'{q} 2160p')
            return variants[:5]


        def parse_results(data, used_query):
            results = []
            for item in data if isinstance(data, list) else []:
                title = item.get('title') or item.get('releaseTitle') or ''
                if not title:
                    continue
                seeders = item.get('seeders') or item.get('seedersCount') or 0
                size = item.get('size') or 0
                try: size_gb = float(size) / (1024 ** 3)
                except Exception: size_gb = 0
                low = title.lower()
                try:
                    seed_score = min(int(seeders or 0), 80)
                except Exception:
                    seed_score = 0

                # Quality-first scoring: a highly seeded 720p YIFY should never outrank a real 1080p/2160p BluRay/REMUX.
                score = seed_score
                quality_rank = 0
                if '2160' in low or '4k' in low or 'uhd' in low:
                    score += 1200; quality_rank = max(quality_rank, 4)
                elif '1080' in low:
                    score += 800; quality_rank = max(quality_rank, 3)
                elif '720' in low:
                    score += 160; quality_rank = max(quality_rank, 1)
                else:
                    score += 40

                if 'remux' in low:
                    score += 450
                if 'bluray' in low or 'blu-ray' in low:
                    score += 260
                if 'bdrip' in low or 'brrip' in low:
                    score += 160
                if 'web-dl' in low:
                    score += 150
                elif 'webrip' in low:
                    score += 90
                if 'x265' in low or 'hevc' in low or 'h.265' in low:
                    score += 60
                if 'x264' in low or 'h.264' in low:
                    score += 25

                # Penalize tiny encodes and low-quality release groups when better sources exist.
                if 'yify' in low or 'yts' in low:
                    score -= 220
                if quality_rank <= 1 and size_gb and size_gb < 1.2:
                    score -= 180
                if any(x in low for x in [' cam', 'ts ', 'telesync', 'hdcam', 'camrip']):
                    score -= 1500
                # Avoid obviously unrelated title noise if query is specific.
                if 'zodiac' in used_query.lower() and 'zodiac' not in low and 'tt0443706' not in low:
                    score -= 800
                if 'eyes wide shut' in used_query.lower() and 'eyes' not in low and 'tt0120663' not in low:
                    score -= 800
                results.append({
                    "title": title,
                    "indexer": item.get('indexer') or item.get('indexerName') or '',
                    "seeders": seeders,
                    "size": size,
                    "size_gb": round(size_gb, 2),
                    "downloadUrl": item.get('downloadUrl') or item.get('download_url') or '',
                    "magnetUrl": item.get('magnetUrl') or item.get('magnet_url') or '',
                    "infoUrl": item.get('infoUrl') or item.get('guid') or '',
                    "score": score,
                    "matched_query": used_query
                })
            return results

        try:
            all_results = []
            attempts = []
            movie_categories = [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060, 2070]

            enabled_indexer_ids = get_enabled_indexer_ids()

            def prowlarr_request(q, mode='movies', request_timeout=14):
                # Prowlarr manual UI often searches enabled indexers with movie categories.
                # We try multiple API shapes because different Prowlarr builds/Cardigann indexers behave differently.
                pairs = [('query', q), ('limit', '100')]
                if mode != 'no_indexer' and enabled_indexer_ids:
                    pairs.append(('indexerIds', ','.join(enabled_indexer_ids)))
                elif mode == 'minus_one':
                    pairs.append(('indexerIds', '-1'))

                if mode in ('movie_type', 'movie_type_no_indexer'):
                    pairs.append(('type', 'movie'))
                    pairs += [('categories', str(c)) for c in movie_categories]
                elif mode in ('movies', 'no_indexer', 'minus_one'):
                    pairs.append(('type', 'search'))
                    pairs += [('categories', str(c)) for c in movie_categories]
                elif mode == 'all':
                    pairs.append(('type', 'search'))
                elif mode == 'movie_no_cat':
                    pairs.append(('type', 'movie'))
                else:
                    pairs.append(('type', 'search'))

                params = urllib.parse.urlencode(pairs, doseq=True)
                url = cfg['prowlarr_url'] + '/api/v1/search?' + params
                req = urllib.request.Request(url, headers={'X-Api-Key': cfg['prowlarr_api_key'], 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=request_timeout) as response:
                    return json.loads(response.read().decode('utf-8', errors='replace')), url


            api_errors = []
            deadline = time.time() + 42
            # Keep fan-out small, but give slow Cloudflare/FlareSolverr indexers enough time.
            variants_for_search = query_variants(query)[:4]
            for q in variants_for_search:
                if time.time() > deadline:
                    api_errors.append('Search stopped by 42s deadline')
                    break
                modes = ('movie_type', 'all')
                for mode in modes:
                    if time.time() > deadline:
                        api_errors.append('Search stopped by 42s deadline')
                        break
                    remaining = max(4, int(deadline - time.time()))
                    timeout_s = min(16, remaining)
                    attempts.append(f'{q} [{mode}]')
                    try:
                        data, used_url = prowlarr_request(q, mode, request_timeout=timeout_s)
                        parsed = parse_results(data, q)
                        all_results.extend(parsed)
                        if parsed:
                            log_to_file(f'Prowlarr returned {len(parsed)} result(s) for {q} [{mode}]')
                        if len(all_results) >= 8 and any(r.get('score', 0) >= 700 for r in all_results):
                            break
                    except Exception as request_error:
                        err_text = str(request_error)
                        # Timeout is common on the first FlareSolverr-protected indexer hit; keep trying better canonical variants.
                        api_errors.append(f'{q} [{mode}]: {err_text}')
                        log_to_file(f'Prowlarr search attempt failed: {q} [{mode}] {err_text}')
                        continue
                if len(all_results) >= 8 and any(r.get('score', 0) >= 700 for r in all_results):
                    break
            # Deduplicate by title/indexer/size.
            seen = set(); dedup = []
            for r in all_results:
                key = (r.get('title','').lower(), r.get('indexer','').lower(), r.get('size',0))
                if key in seen: continue
                seen.add(key); dedup.append(r)
            dedup.sort(key=lambda x: x.get('score', 0), reverse=True)
            return json.dumps({"status": "success", "query": query, "flaresolverr": flaresolverr_status, "attempts": attempts, "errors": api_errors[-8:] if 'api_errors' in locals() else [], "results": dedup[:40]}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "query": query, "flaresolverr": flaresolverr_status if 'flaresolverr_status' in locals() else {}, "message": str(e)}, ensure_ascii=False)


    def _best_movie_raw_candidate(self, query):
        import json
        try:
            data = json.loads(self.movie_raw_search(query) or '{}')
            results = data.get('results') or []
            return (results[0] if results else None), data
        except Exception as e:
            return None, {"status": "error", "message": str(e)}

    def ai_assistant_chat(self, user_message, context_json="{}"):
        """Compact in-app :3 assistant. It explains the app and returns safe UI actions.
        It can suggest downloader/merger workflows, but does not automate protected-site bypasses.
        """
        import json
        import urllib.request
        user_message = str(user_message or "").strip()
        if not user_message:
            return json.dumps({"status": "success", "answer": "Ask me what you want to do: find RAW, prepare DUB, merge episodes, or fix playback.", "actions": []}, ensure_ascii=False)
        try:
            context = json.loads(context_json or "{}")
            if not isinstance(context, dict):
                context = {}
        except Exception:
            context = {}

        openai_key = os.environ.get("OPENAI_API_KEY", "")
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        keys_file = get_keys_file()
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    keys = json.load(f)
                    openai_key = openai_key or keys.get("OPENAI_API_KEY", "")
                    tavily_key = tavily_key or keys.get("TAVILY_API_KEY", "")
            except Exception:
                pass

        # Local command fallback works without API keys and also seeds useful deterministic actions.
        lower = user_message.lower()
        local_actions = []
        known_titles = {
            "kill blue": "Kill Blue",
            "kill ao": "Kill Ao",
            "убивая юность": "Kill Blue",
            "bleach": "Bleach",
            "блич": "Bleach",
            "fate": "Fate",
            "фейт": "Fate",
            "prison school": "Prison School",
            "школа тюрьма": "Prison School"
        }
        detected_title = ""
        for k, v in known_titles.items():
            if k in lower:
                detected_title = v
                break
        ep_match = re.search(r'(?:episode|ep|сер(?:ия|ии|ию)?|s\d{1,2}e)\s*0*(\d{1,3})|\b(\d{1,3})\s*[- ]?\s*(?:st|nd|rd|th)?\s*(?:episode|ep|сер(?:ия|ии|ию)?)', lower)
        detected_ep = ""
        detected_season = 1
        season_match = re.search(r'(?:season|s|сезон)\s*0*(\d{1,2})', lower)
        if season_match:
            try:
                detected_season = int(season_match.group(1))
            except Exception:
                detected_season = 1
        if ep_match:
            detected_ep = ep_match.group(1) or ep_match.group(2) or ""
        downloader_query = detected_title
        if detected_title and detected_ep:
            downloader_query = f"{detected_title} S{detected_season:02d}E{int(detected_ep):02d}"
        elif not detected_title and any(x in lower for x in ["raw", "nyaa", "download", "скач", "торрент"]):
            # Use the raw message as a search query if no known title was detected.
            downloader_query = user_message.strip()

        # Movie/show RAW requests should not be sent blindly to Nyaa.
        # Use a movie/show provider (Prowlarr) instead and present multiple practical candidates.
        raw_download_intent = any(x in lower for x in [
            "raw", "best raw", "download raw", "скачай raw", "лучший raw", "best quality download",
            "get best", "best quality", "download", "скачай", "качай"
        ])
        identification_intent = (
            any(x in lower for x in [
                "what is this", "what's this", "how is this", "name of", "identify",
                "как называется", "что за фильм", "название фильма", "найди название", "определи фильм"
            ])
            # Phrases like "film called Eyes Wide Shut" are not identification if user also asks for RAW/download.
            or ("called" in lower and not raw_download_intent)
        )
        movie_raw_request = (
            not identification_intent
            and not detected_title
            and raw_download_intent
            and any(x in lower for x in ["movie", "film", "фильм", "raw", "quality"])
        )
        if movie_raw_request:
            clean_movie_query = self._normalize_movie_query(user_message)
            try:
                pdata = json.loads(self.movie_raw_search(clean_movie_query) or '{}')
            except Exception as e:
                pdata = {"status": "error", "message": str(e), "results": []}
            results = pdata.get('results') or []

            def unique_by_title(items):
                seen = set(); out = []
                for r in items:
                    key = (r.get('title','').lower(), r.get('indexer','').lower(), round(float(r.get('size_gb') or 0), 2))
                    if key in seen: continue
                    seen.add(key); out.append(r)
                return out

            def pick_best(items, max_size=None, min_size=None, require_1080=False):
                pool = []
                for r in items:
                    size = float(r.get('size_gb') or 0)
                    title_l = (r.get('title') or '').lower()
                    if max_size is not None and size > max_size: continue
                    if min_size is not None and size < min_size: continue
                    if require_1080 and not any(x in title_l for x in ['1080', '2160', '4k', 'uhd']): continue
                    pool.append(r)
                return sorted(pool, key=lambda x: x.get('score', 0), reverse=True)[0] if pool else None

            if results:
                results = unique_by_title(results)

                def title_l(r):
                    return (r.get('title') or '').lower()

                def size_of(r):
                    try:
                        return float(r.get('size_gb') or 0)
                    except Exception:
                        return 0.0

                def seeders_of(r):
                    try:
                        return int(r.get('seeders') or 0)
                    except Exception:
                        return 0

                def has_2160(r):
                    t = title_l(r)
                    return '2160' in t or '4k' in t or 'uhd' in t

                def has_1080(r):
                    return '1080' in title_l(r)

                def is_remux(r):
                    return 'remux' in title_l(r)

                def is_bluray(r):
                    t = title_l(r)
                    return 'bluray' in t or 'blu-ray' in t or 'bdrip' in t or 'brrip' in t

                def is_web(r):
                    t = title_l(r)
                    return 'web-dl' in t or 'webrip' in t

                def is_tiny_group(r):
                    t = title_l(r)
                    return 'yify' in t or 'yts' in t

                def unique_add(candidates, label, reason, item):
                    if not item:
                        return
                    key = (item.get('title', '').lower(), round(size_of(item), 2))
                    if any((c['item'].get('title', '').lower(), round(size_of(c['item']), 2)) == key for c in candidates):
                        return
                    candidates.append({'label': label, 'reason': reason, 'item': item})

                def best_by(pool, fn):
                    pool = [r for r in pool if r]
                    if not pool:
                        return None
                    return sorted(pool, key=fn, reverse=True)[0]

                # Category-specific scoring. This is intentionally not one universal score:
                # users need practical choices, not only a 90GB archive remux.
                def balance_score(r):
                    size = size_of(r)
                    score = seeders_of(r) * 1.2
                    if has_1080(r): score += 120
                    if has_2160(r): score += 80  # 4K can be good, but balance favors sane size.
                    if is_bluray(r): score += 80
                    if is_web(r): score += 45
                    if 'x265' in title_l(r) or 'hevc' in title_l(r): score += 35
                    # Sweet spot for normal viewing.
                    if 4 <= size <= 16: score += 110
                    elif 2 <= size < 4: score += 55
                    elif 16 < size <= 25: score += 25
                    elif size > 35: score -= 120
                    if is_remux(r): score -= 80
                    if is_tiny_group(r): score -= 90
                    return score

                def best_1080_score(r):
                    size = size_of(r)
                    score = seeders_of(r)
                    if has_1080(r): score += 200
                    else: score -= 300
                    if is_bluray(r): score += 120
                    if is_remux(r): score += 60
                    if 'criterion' in title_l(r): score += 80
                    if 'x265' in title_l(r) or 'hevc' in title_l(r): score += 45
                    if 6 <= size <= 25: score += 85
                    elif size > 35: score -= 80
                    if is_tiny_group(r): score -= 160
                    return score

                def practical_4k_score(r):
                    size = size_of(r)
                    score = seeders_of(r)
                    if has_2160(r): score += 240
                    else: score -= 400
                    if is_bluray(r): score += 90
                    if 'hdr' in title_l(r) or 'dv' in title_l(r): score += 70
                    if 'x265' in title_l(r) or 'hevc' in title_l(r): score += 50
                    # Practical 4K: not tiny, not absurd.
                    if 18 <= size <= 45: score += 130
                    elif 45 < size <= 60: score += 60
                    elif size > 65: score -= 150
                    if is_remux(r) and size > 65: score -= 80
                    return score

                def archive_score(r):
                    size = size_of(r)
                    score = seeders_of(r)
                    if has_2160(r): score += 260
                    if is_remux(r): score += 220
                    if is_bluray(r): score += 120
                    if 'truehd' in title_l(r) or 'dts-hd' in title_l(r) or 'atmos' in title_l(r): score += 90
                    if 'hdr' in title_l(r) or 'dv' in title_l(r): score += 70
                    if size >= 35: score += 40
                    return score

                def compact_score(r):
                    size = size_of(r)
                    score = seeders_of(r) * 1.5
                    if has_1080(r): score += 120
                    if is_bluray(r) or is_web(r): score += 70
                    if 'x265' in title_l(r) or 'hevc' in title_l(r): score += 50
                    if 1.5 <= size <= 5: score += 120
                    elif 5 < size <= 8: score += 65
                    elif size > 10: score -= 250
                    if is_tiny_group(r): score -= 35  # still allow if user wants compact.
                    return score

                candidates = []
                unique_add(
                    candidates,
                    'Best Balance',
                    'best normal viewing choice: strong quality without insane size',
                    best_by([r for r in results if 2 <= size_of(r) <= 25 and (has_1080(r) or has_2160(r))], balance_score)
                )
                unique_add(
                    candidates,
                    'Best 1080p Quality',
                    'best 1080p encode/source quality',
                    best_by([r for r in results if has_1080(r)], best_1080_score)
                )
                unique_add(
                    candidates,
                    'Best 4K Practical',
                    'best 2160p/4K option with reasonable size',
                    best_by([r for r in results if has_2160(r) and size_of(r) <= 60], practical_4k_score)
                )
                unique_add(
                    candidates,
                    'Archive Max Quality',
                    'maximum archive quality, storage-heavy',
                    best_by(results, archive_score)
                )
                unique_add(
                    candidates,
                    'Compact',
                    'smallest acceptable file for quick viewing',
                    best_by([r for r in results if size_of(r) <= 8], compact_score)
                )

                # Fill up to 5 with strong unique alternatives if one category is missing.
                for r in sorted(results, key=lambda x: x.get('score', 0), reverse=True):
                    if len(candidates) >= 5:
                        break
                    unique_add(candidates, 'Alternative', 'strong fallback candidate', r)

                lines = [
                    f"Movie RAW candidates for: {clean_movie_query}",
                    "Type a number to download. Example: 2",
                    ""
                ]
                choices = []
                for idx, c in enumerate(candidates[:5], start=1):
                    r = c['item']
                    title = r.get('title') or 'Unknown release'
                    size = r.get('size_gb')
                    seeders = r.get('seeders')
                    reason = c['reason']
                    lines.append(f"{idx}) {c['label']} — {size} GiB")
                    lines.append(f"   {title}")
                    lines.append(f"   {reason}. Seeds: {seeders}.")
                    if size and float(size) >= 50:
                        lines.append("   Warning: huge file; choose a practical option unless you want archival quality.")
                    lines.append("")
                    choices.append({
                        "title": title,
                        "label": c['label'],
                        "size_gb": size,
                        "reason": reason,
                        "action": {
                            "type": "torrent_add_raw",
                            "label": f"Download {idx}",
                            "torrent_link": r.get('downloadUrl', ''),
                            "magnet_link": r.get('magnetUrl', ''),
                            "title": title
                        }
                    })
                lines.append("Choose by number: 1 = balanced, 3 = practical 4K, 4 = archive max quality.")
                return json.dumps({"status": "success", "answer": "\n".join(lines).strip(), "actions": [], "choices": choices}, ensure_ascii=False)

            if pdata.get('status') == 'not_configured':
                answer = (
                    f"I recognized this as a movie/show request: {clean_movie_query}.\n"
                    "Nyaa is not the right provider for regular movies. Configure Prowlarr for movie/show RAW search.\n\n"
                    "Prowlarr is a self-hosted indexer aggregator, not a public cloud API. Add PROWLARR_URL and PROWLARR_API_KEY to keys.json."
                )
                return json.dumps({"status": "success", "answer": answer, "actions": [{"type": "open_merger", "label": "Open Merger"}, {"type": "import_raw_downloads", "label": "Import RAW Downloads"}]}, ensure_ascii=False)
            attempts_txt = ', '.join((pdata.get('attempts') or [])[:10])
            errors_txt = '\n'.join((pdata.get('errors') or [])[:5])
            fl_txt = pdata.get('flaresolverr') or {}
            answer = (
                f"Movie provider did not return RAW results for {clean_movie_query}.\n\n"
                f"FlareSolverr: {fl_txt.get('status', 'unknown')} {fl_txt.get('message', '')}\n"
                f"Attempts: {attempts_txt or 'none'}\n"
                + (f"Errors:\n{errors_txt}\n" if errors_txt else "")
                + "If Prowlarr UI finds this movie but the app does not, check that at least one enabled indexer is saved and that Prowlarr API key in keys.json matches the running Prowlarr instance."
            )
            return json.dumps({"status": "success", "answer": answer, "actions": [{"type": "open_merger", "label": "Open Merger"}]}, ensure_ascii=False)



        if any(x in lower for x in ["merger", "merge", "склей", "скле", "даб", "dub"]):
            local_actions.append({"type": "open_merger", "label": "Open Merger"})
        if any(x in lower for x in ["raw", "nyaa", "торрент", "download", "скач", "prepare", "найди", "find"]):
            if downloader_query:
                local_actions.append({"type": "search_downloader", "label": f"Search RAW: {downloader_query}", "query": downloader_query})
            else:
                local_actions.append({"type": "open_downloader", "label": "Open Downloader"})

        wants_dub = any(x in lower for x in ["dub", "даб", "дуб", "дубляж", "озвуч", "voice", "voiceover"])
        if wants_dub and detected_title and detected_ep:
            answer = (
                f"I prepared the stable DUB Browser workflow for {detected_title} S{detected_season:02d}E{int(detected_ep):02d}.\n"
                "The source will open inside the player. Sign in once if needed, choose the voice on the page, start the site download, and I will catch the finished file from Downloads/dub/."
            )
            return json.dumps({"status": "success", "answer": answer, "actions": [
                {"type": "open_dub_source", "label": "Open built-in DUB Browser", "title": detected_title, "season": detected_season, "episode": int(detected_ep)},
                {"type": "open_merger", "label": "Open Merger"}
            ]}, ensure_ascii=False)


        # If user asks for a concrete episode/RAW, resolve it NOW on the backend.
        # Do not let GPT turn this into a useless "search" button.
        wants_prepare = any(x in lower for x in [
            "prepare", "find", "give me", "show me", "best raw", "raw", "best quality", "quality",
            "найди", "подготов", "скачай", "download", "кач", "лучш", "серия", "эпизод"
        ])
        if detected_title and detected_ep and downloader_query and wants_prepare:
            log_to_file(f"AI assistant deterministic prepare request: query={downloader_query}")
            best, search_data = self._best_raw_candidate_for_query(downloader_query)
            if best:
                answer = (
                    f"I found a concrete RAW candidate for {detected_title} S{detected_season:02d}E{int(detected_ep):02d}:\n\n"
                    f"{best.get('title')}\n"
                    f"Size: {best.get('size')} | Seeders: {best.get('seeders')} | Source: {best.get('source')} | Group: {best.get('group')} | Score: {best.get('score')}\n\n"
                    "Recommendation: download this RAW into raw/ and then get the matching DUB. Should I add it to the internal torrent queue?"
                )
                return json.dumps({"status": "success", "answer": answer, "actions": [
                    {"type": "torrent_add_raw", "label": "Download RAW to raw/", "torrent_link": best.get('torrent_link', ''), "magnet_link": best.get('magnet_link', ''), "title": best.get('title', '')},
                    {"type": "open_merger", "label": "Open Merger"}
                ]}, ensure_ascii=False)
            else:
                answer = f"I searched for {downloader_query}, but did not find a usable RAW candidate. Try a broader query like '{detected_title}'."
                return json.dumps({"status": "success", "answer": answer, "actions": [{"type": "search_downloader", "label": f"Search RAW: {detected_title}", "query": detected_title}]}, ensure_ascii=False)

        if any(x in lower for x in ["rezka", "резка", "озвуч", "dub"]):
            local_actions.append({"type": "open_merger", "label": "Open Merger"})
            local_actions.append({"type": "import_dub_downloads", "label": "Import DUB Downloads"})
        if any(x in lower for x in ["scan", "match", "проверь", "пары"]):
            local_actions.append({"type": "merger_scan", "label": "Scan RAW/DUB"})
        if any(x in lower for x in ["merge all", "собери", "склей все"]):
            local_actions.append({"type": "merger_merge_all", "label": "Merge All"})
        if not openai_key:
            if downloader_query:
                answer = (
                    f"I will prepare a RAW search for: {downloader_query}.\n"
                    "Use the action button below to open Downloader and run the Nyaa search.\n"
                    "After RAW is downloaded/imported to raw/, download your chosen DUB, import/watch dub/, then run Merger → Auto Sync + Merge All.\n\n"
                    "Full GPT reasoning is disabled because no OPENAI_API_KEY was detected."
                )
            else:
                answer = (
                    "I can help with the workflow. Current safest pipeline:\n"
                    "1. Put or import best RAW into raw/.\n"
                    "2. Open DUB Source, download your chosen dub, then import/watch dub/.\n"
                    "3. Use Merger → Auto Sync + Merge All.\n"
                    "4. Use Add Outputs to Library and confirm the target title.\n\n"
                    "Add OPENAI_API_KEY and TAVILY_API_KEY to keys.json for full reasoning and recommendations."
                )
            return json.dumps({"status": "success", "answer": answer, "actions": local_actions[:4]}, ensure_ascii=False)

        web_context = ""
        if tavily_key and any(x in lower for x in ["recommend", "похож", "атмосфер", "best", "лучш", "quality", "source", "called", "identify", "what film", "what movie", "как называется", "что за фильм"]):
            try:
                req_data = json.dumps({
                    "api_key": tavily_key,
                    "query": user_message + " anime movie show recommendations best source watch order",
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": 5
                }).encode("utf-8")
                req = urllib.request.Request("https://api.tavily.com/search", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=10) as response:
                    tr = json.loads(response.read().decode("utf-8", errors="replace"))
                    chunks = []
                    if tr.get("answer"):
                        chunks.append("Answer: " + tr.get("answer"))
                    for r in tr.get("results", [])[:5]:
                        chunks.append(f"Title: {r.get('title','')}\nContent: {r.get('content','')}")
                    web_context = "\n\n".join(chunks)[:6000]
            except Exception as e:
                web_context = "Tavily unavailable: " + str(e)

        system_prompt = (
            "You are :3, the built-in assistant for Minimal Media Player Pro. "
            "You know the app features: Catalog, Library, Watching Guard, Downloader/Nyaa RAW search, Merger RAW/DUB pipeline, DUB Source browser workflow, Demucs voice-only overlay, output-to-library linking. "
            "Be concise, practical, and proactive. Never instruct bypassing protected websites or hidden APIs. "
            "Return ONLY JSON with keys: answer (string), actions (array). "
            "Allowed action types: open_downloader, search_downloader, torrent_add_raw, open_merger, open_dub_source, import_raw_downloads, import_dub_downloads, merger_scan, merger_merge_all, add_outputs_to_library. "
            "For search_downloader include a query field, e.g. {type:'search_downloader', label:'Search RAW: Kill Blue S01E07', query:'Kill Blue S01E07'}. "
            "When the user asks to prepare/download an episode range, clearly state what RAW query or episode range you are preparing before giving actions. "
            "Each action object must have type and label."
        )
        user_prompt = json.dumps({
            "user_message": user_message,
            "app_context": context,
            "web_context": web_context
        }, ensure_ascii=False, indent=2)
        try:
            payload = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.25,
                "response_format": {"type": "json_object"}
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {openai_key}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=18) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
                raw = data["choices"][0]["message"]["content"].strip()
                parsed = json.loads(raw)
                return json.dumps({"status": "success", "answer": parsed.get("answer", "Done."), "actions": parsed.get("actions", [])[:6]}, ensure_ascii=False)
        except Exception as e:
            answer = "AI request failed, but I can still route you through the local workflow. Open Merger for RAW/DUB automation or Downloader for Nyaa RAW search. Error: " + str(e)
            return json.dumps({"status": "success", "answer": answer, "actions": local_actions[:4]}, ensure_ascii=False)

    def process_file(self, filepath, filename):
        """ Remuxes TS to MP4 on-the-fly using FFmpeg copy stream (0.5 seconds, 100% quality) """
        log_to_file(f"=== process_file called for: {filepath} ===")
        if not filepath:
            return {"path": "", "name": filename, "is_remuxed": False}
            
        # Resolve any % character URL encodings
        if not os.path.exists(filepath):
            unquoted = urllib.parse.unquote(filepath)
            if os.path.exists(unquoted):
                filepath = unquoted
            else:
                return {"path": filepath, "name": filename, "is_remuxed": False}
                
        # We only process .ts files
        if not filepath.lower().endswith('.ts'):
            return {"path": filepath, "name": filename, "is_remuxed": False}
            
        # Check if FFmpeg is available
        ffmpeg_bin = get_ffmpeg_path()
        if not ffmpeg_bin:
            log_to_file("FFmpeg is not available, skipping remux.")
            return {"path": filepath, "name": filename, "is_remuxed": False}
            
        # Get target output path
        target_mp4 = get_output_mp4_path(filepath)
        log_to_file(f"Target MP4 path: {target_mp4}")
        
        # If the MP4 file already exists and is not empty, use it directly!
        if os.path.exists(target_mp4) and os.path.getsize(target_mp4) > 1024 * 1024:
            log_to_file("Remuxed MP4 already exists, returning cached file.")
            return {"path": target_mp4, "name": os.path.basename(target_mp4), "is_remuxed": True}
            
        # Run FFmpeg remuxing (copy streams, no quality loss, extremely fast!)
        log_to_file("Running fast stream copy remux from TS to MP4...")
        try:
            cmd = [ffmpeg_bin, "-y", "-i", filepath, "-c", "copy", "-map_metadata", "0", target_mp4]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
            stdout, stderr = proc.communicate(timeout=15)
            
            if os.path.exists(target_mp4) and os.path.getsize(target_mp4) > 1024:
                log_to_file("Successfully remuxed TS to MP4!")
                return {"path": target_mp4, "name": os.path.basename(target_mp4), "is_remuxed": True}
            else:
                log_to_file(f"Remux failed, output file is empty or missing. FFmpeg output: {stderr.decode('utf-8', errors='ignore')}")
        except Exception as e:
            log_to_file(f"Remux exception: {e}")
            
        return {"path": filepath, "name": filename, "is_remuxed": False}

    def _media_proxy_path(self, filepath):
        """Full compatible MKV copy path: video copied, primary/default audio transcoded to AAC."""
        h = hashlib.md5(str(filepath).encode('utf-8', errors='ignore')).hexdigest()
        safe_dir = get_safe_temp_dir()
        return os.path.join(safe_dir, f"audio_proxy_{h}.mkv")

    def _media_video_proxy_path(self, filepath):
        """Full browser-compatible MP4: video H.264 + audio AAC."""
        h = hashlib.md5(str(filepath).encode('utf-8', errors='ignore')).hexdigest()
        safe_dir = get_safe_temp_dir()
        return os.path.join(safe_dir, f"video_compat_{h}.mp4")

    def _is_valid_media_proxy(self, proxy_path):
        try:
            if not proxy_path or not os.path.exists(proxy_path) or os.path.getsize(proxy_path) <= 1024 * 1024:
                return False
            if nohomo_merger_core:
                cfg = nohomo_merger_core.load_config(get_workflow_dir())
                info = nohomo_merger_core.ffprobe_json(proxy_path, cfg)
                has_video = any(st.get('codec_type') == 'video' for st in info.get('streams', []))
                has_audio = any(st.get('codec_type') == 'audio' for st in info.get('streams', []))
                return bool(has_video and has_audio)
            return True
        except Exception as e:
            log_to_file(f"Full compatible proxy validation failed for {proxy_path}: {e}")
            return False

    def _media_sidecar_name(self, filepath):
        h = hashlib.md5(str(filepath).encode('utf-8', errors='ignore')).hexdigest()
        return f"audio_sidecar_{h}.m4a"

    def _can_write_in_dir(self, folder):
        try:
            if not folder or not os.path.isdir(folder):
                return False
            test = os.path.join(folder, f".mmp_write_test_{os.getpid()}.tmp")
            with open(test, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test)
            return True
        except Exception:
            try:
                if 'test' in locals() and os.path.exists(test):
                    os.remove(test)
            except Exception:
                pass
            return False

    def _media_sidecar_candidates(self, filepath):
        name = self._media_sidecar_name(filepath)
        src_dir = os.path.dirname(os.path.abspath(filepath))
        safe_dir = get_safe_temp_dir()
        out = []
        if src_dir:
            out.append(os.path.join(src_dir, name))
        out.append(os.path.join(safe_dir, name))
        # Deduplicate while preserving order.
        seen = set()
        uniq = []
        for x in out:
            ax = os.path.abspath(x)
            if ax not in seen:
                seen.add(ax)
                uniq.append(x)
        return uniq

    def _media_sidecar_path(self, filepath):
        """Small AAC audio-only sidecar path for unsupported browser audio.

        Prefer the movie folder so a flash drive keeps its reusable audio fix next to the MKV.
        If that folder is not writable, fall back to local safe temp (usually system SSD).
        """
        candidates = self._media_sidecar_candidates(filepath)
        src_dir = os.path.dirname(os.path.abspath(filepath))
        if src_dir and self._can_write_in_dir(src_dir):
            return candidates[0]
        return candidates[-1]

    def _is_valid_audio_sidecar(self, sidecar_path):
        """Quick sanity check so a half-written/corrupt .m4a is never treated as cached-ready."""
        try:
            if not sidecar_path or not os.path.exists(sidecar_path) or os.path.getsize(sidecar_path) <= 128 * 1024:
                return False
            if nohomo_merger_core:
                cfg = nohomo_merger_core.load_config(get_workflow_dir())
                info = nohomo_merger_core.ffprobe_json(sidecar_path, cfg)
                for st in info.get('streams', []):
                    if st.get('codec_type') == 'audio' and str(st.get('codec_name', '')).lower() in {'aac', 'mp4a'}:
                        return True
                return False
            return True
        except Exception as e:
            log_to_file(f"Audio sidecar validation failed for {sidecar_path}: {e}")
            return False

    def _existing_media_sidecar_path(self, filepath):
        try:
            for candidate in self._media_sidecar_candidates(filepath):
                if os.path.exists(candidate) and os.path.getsize(candidate) > 128 * 1024:
                    if self._is_valid_audio_sidecar(candidate):
                        return candidate
                    # Corrupt/unfinished sidecar: remove it so the app can rebuild cleanly.
                    try:
                        os.remove(candidate)
                    except Exception:
                        pass
        except Exception:
            pass
        return ""

    def _same_windows_drive(self, a, b):
        try:
            da = os.path.splitdrive(os.path.abspath(a))[0].lower()
            db = os.path.splitdrive(os.path.abspath(b))[0].lower()
            return bool(da and db and da == db)
        except Exception:
            return False

    def _should_stage_media_on_local_ssd(self, filepath, local_dir):
        """Return (enabled, reason). Staging helps when source is on a slow/removable drive.
        It temporarily copies the original MKV to local SSD, transcodes audio from there,
        then deletes the staged copy. It needs free local space roughly equal to the source.
        """
        try:
            filepath = os.path.abspath(filepath)
            local_dir = os.path.abspath(local_dir)
            size = os.path.getsize(filepath)
            if size < 2 * 1024 * 1024 * 1024:
                return False, "source is small"
            if os.name == 'nt' and self._same_windows_drive(filepath, local_dir):
                return False, "source is already on local temp drive"
            import shutil
            free = shutil.disk_usage(local_dir).free
            # Keep a safety cushion: source size + 2 GiB.
            if free < size + 2 * 1024 * 1024 * 1024:
                return False, "not enough local SSD free space for temporary staging"
            return True, "source appears to be on another drive and local SSD has enough space"
        except Exception as e:
            return False, str(e)

    def analyze_media_compat(self, filepath):
        """Returns codec info and whether a small AAC sidecar is recommended for WebView playback."""
        import json
        try:
            if not filepath:
                return json.dumps({"status": "error", "message": "empty filepath"}, ensure_ascii=False)
            filepath = urllib.parse.unquote(str(filepath)).strip('"' + "'")
            if not os.path.exists(filepath):
                return json.dumps({"status": "error", "message": "file not found", "path": filepath}, ensure_ascii=False)
            cfg = nohomo_merger_core.load_config(get_workflow_dir()) if nohomo_merger_core else {"ffprobe_path": "ffprobe"}
            info = nohomo_merger_core.ffprobe_json(filepath, cfg) if nohomo_merger_core else {}
            audio = []
            video = []
            for st in info.get('streams', []):
                if st.get('codec_type') == 'audio':
                    audio.append({
                        "index": st.get('index'),
                        "codec": st.get('codec_name', ''),
                        "channels": st.get('channels'),
                        "language": st.get('tags', {}).get('language', 'und'),
                        "title": st.get('tags', {}).get('title', ''),
                        "default": int(st.get('disposition', {}).get('default', 0) or 0)
                    })
                elif st.get('codec_type') == 'video':
                    video.append({
                        "index": st.get('index'),
                        "codec": st.get('codec_name', ''),
                        "width": st.get('width'),
                        "height": st.get('height')
                    })
            unsupported_audio = {'dts', 'dca', 'truehd', 'mlp', 'flac', 'alac', 'opus', 'vorbis'}
            maybe_unsupported = {'ac3', 'eac3'}
            # WebView2/HTML5 can be unreliable with HEVC/AV1 in MKV depending on Windows codecs/extensions.
            # If this is true, audio sidecar/full-audio-copy will not help: user needs H.264/AAC MP4 transcode.
            video_codecs = {v.get('codec', '').lower() for v in video if v.get('codec')}
            risky_video = {'hevc', 'h265', 'av1', 'vp9'}
            needs_video_transcode = bool(video_codecs & risky_video)
            # Browser playback uses the default/first audio track, not every audio stream in the MKV.
            # Merged outputs often contain Russian AAC first + original DTS second; the second track must NOT trigger sidecar.
            playback_audio = None
            for a in audio:
                if a.get('default'):
                    playback_audio = a
                    break
            if not playback_audio and audio:
                playback_audio = audio[0]
            playback_codec = (playback_audio or {}).get('codec', '').lower()
            needs_proxy = bool(playback_codec in unsupported_audio or playback_codec in maybe_unsupported)
            all_codecs = {a.get('codec', '').lower() for a in audio if a.get('codec')}
            has_non_primary_unsupported = bool((all_codecs & (unsupported_audio | maybe_unsupported)) and not needs_proxy)
            return json.dumps({
                "status": "success",
                "path": filepath,
                "audio": audio,
                "video": video,
                "playback_audio": playback_audio,
                "needs_audio_proxy": needs_proxy,
                "needs_audio_sidecar": needs_proxy,
                "has_non_primary_unsupported_audio": has_non_primary_unsupported,
                "needs_video_transcode": needs_video_transcode,
                "video_codecs": list(video_codecs),
                "recommended_mode": "video_transcode" if needs_video_transcode else ("audio_sidecar" if needs_proxy else "direct"),
                "reason": "Primary/default audio is unsupported" if needs_proxy else ("Video codec/container may be unsupported by WebView" if needs_video_transcode else "Primary/default playback audio appears browser-compatible")
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def safe_delete_replaced_media(self, old_path, new_path=""):
        """Delete old media after a compatible copy replaced it, but only for app-managed/generated paths.
        This avoids deleting arbitrary user originals from random folders.
        """
        import json
        try:
            old_path = urllib.parse.unquote(str(old_path or '')).strip('"' + "'")
            new_path = urllib.parse.unquote(str(new_path or '')).strip('"' + "'")
            if not old_path or not os.path.exists(old_path):
                return json.dumps({"status": "skipped", "reason": "old file missing"}, ensure_ascii=False)
            if new_path and os.path.abspath(old_path) == os.path.abspath(new_path):
                return json.dumps({"status": "skipped", "reason": "same file"}, ensure_ascii=False)
            ap = os.path.abspath(old_path)
            safe_roots = [
                os.path.abspath(DEFAULT_LIBRARY_DIR),
                os.path.abspath(os.path.join(get_workflow_dir(), 'output')),
                os.path.abspath(get_safe_temp_dir()),
            ]
            base = os.path.basename(ap).lower()
            generated = base.startswith('audio_proxy_') or base.startswith('audio_sidecar_') or base.startswith('remux_')
            inside_safe = any(ap.startswith(root + os.sep) or ap == root for root in safe_roots if root)
            if not (generated or inside_safe):
                return json.dumps({"status": "skipped", "reason": "old file is not app-managed; not deleting user original", "path": ap}, ensure_ascii=False)
            os.remove(ap)
            return json.dumps({"status": "success", "deleted": ap}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def check_playback_fixes(self, filepath):
        """Return compatibility analysis and cached fixes without starting FFmpeg.
        Frontend uses this to avoid asking the user if a full compatible copy/sidecar already exists.
        """
        import json
        try:
            filepath = urllib.parse.unquote(str(filepath or '')).strip('"' + "'")
            if not filepath or not os.path.exists(filepath):
                return json.dumps({"status": "error", "message": "file not found", "path": filepath}, ensure_ascii=False)
            analysis = json.loads(self.analyze_media_compat(filepath))
            full_path = self._media_proxy_path(filepath)
            video_path = self._media_video_proxy_path(filepath)
            sidecar_path = self._existing_media_sidecar_path(filepath) or self._media_sidecar_path(filepath)
            full_ready = self._is_valid_media_proxy(full_path)
            video_ready = self._is_valid_media_proxy(video_path)
            sidecar_ready = self._is_valid_audio_sidecar(sidecar_path)
            try:
                size = os.path.getsize(filepath)
            except Exception:
                size = 0
            return json.dumps({
                "status": "success",
                "path": filepath,
                "size": size,
                "size_gb": round(size / (1024 ** 3), 2) if size else 0,
                "analysis": analysis,
                "needs_fix": bool(analysis.get('needs_audio_sidecar') or analysis.get('needs_video_transcode')),
                "video_proxy": {"ready": video_ready, "path": video_path if video_ready else ""},
                "full_proxy": {"ready": full_ready, "path": full_path if full_ready else ""},
                "sidecar": {"ready": sidecar_ready, "path": sidecar_path if sidecar_ready else ""}
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def prepare_media_for_playback(self, filepath, mode="sidecar"):
        """Prepare browser-compatible playback for files with DTS/TrueHD/FLAC/etc.

        Critical design rule: never duplicate the video for large movies.
        Instead of creating a 43-90 GB MKV proxy, create only a small AAC/M4A sidecar
        and let the frontend play original video muted + synced sidecar audio.
        """
        import json, threading, time, uuid
        try:
            filepath = urllib.parse.unquote(str(filepath or '')).strip('"' + "'")
            if not filepath or not os.path.exists(filepath):
                return json.dumps({"status": "error", "message": "file not found", "path": filepath}, ensure_ascii=False)

            analysis = json.loads(self.analyze_media_compat(filepath))
            if analysis.get('status') != 'success':
                return json.dumps(analysis, ensure_ascii=False)
            playback_audio_index = None
            try:
                playback_audio_index = analysis.get('playback_audio', {}).get('index')
            except Exception:
                playback_audio_index = None
            selected_audio_map = f"0:{int(playback_audio_index)}" if playback_audio_index is not None else '0:a:0'
            if not analysis.get('needs_audio_sidecar'):
                return json.dumps({
                    "status": "ready",
                    "mode": "direct",
                    "path": filepath,
                    "video_path": filepath,
                    "proxy": False,
                    "sidecar": False,
                    "analysis": analysis
                }, ensure_ascii=False)

            mode = str(mode or 'sidecar').lower().strip()
            if mode in ('original', 'skip', 'none'):
                return json.dumps({"status": "ready", "mode": "original", "path": filepath, "video_path": filepath, "sidecar": False, "analysis": analysis}, ensure_ascii=False)

            if mode in ('video', 'video_transcode', 'browser', 'mp4'):
                video_path = self._media_video_proxy_path(filepath)
                if self._is_valid_media_proxy(video_path):
                    return json.dumps({"status": "ready", "mode": "video_proxy", "path": video_path, "video_path": video_path, "proxy": True, "cached": True, "analysis": analysis}, ensure_ascii=False)
                task_id = str(uuid.uuid4())
                self._media_tasks[task_id] = {"status": "running", "mode": "video_proxy", "progress": 0, "path": video_path, "source": filepath, "message": "Creating H.264/AAC browser-compatible MP4... 0%"}
                def video_worker():
                    tmp = video_path + '.tmp.mp4'
                    try:
                        ffmpeg_bin = get_ffmpeg_path() or 'ffmpeg'
                        cfg = nohomo_merger_core.load_config(get_workflow_dir()) if nohomo_merger_core else {"ffprobe_path": "ffprobe"}
                        dur = nohomo_merger_core.get_duration(filepath, cfg) if nohomo_merger_core else None
                        cmd = [
                            ffmpeg_bin, '-y', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-i', filepath,
                            '-map', '0:v:0', '-map', selected_audio_map,
                            '-vf', 'scale=w=min(1920\\,iw):h=-2',
                            '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-b:a', '192k', '-ac', '2',
                            '-movflags', '+faststart', '-map_metadata', '-1',
                            '-progress', 'pipe:1', '-nostats', tmp
                        ]
                        startupinfo = None
                        if os.name == 'nt':
                            startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
                        if proc.stdout:
                            for line in proc.stdout:
                                line = line.strip()
                                if line.startswith('out_time_ms=') and dur:
                                    try:
                                        out_s = float(line.split('=', 1)[1]) / 1000000.0
                                        pct = max(0, min(99, int((out_s / dur) * 100)))
                                        self._media_tasks[task_id].update({"progress": pct, "message": f"Creating H.264/AAC browser-compatible MP4... {pct}%"})
                                    except Exception: pass
                        code = proc.wait()
                        if code == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1024 * 1024:
                            os.replace(tmp, video_path)
                            self._media_tasks[task_id].update({"status": "ready", "progress": 100, "path": video_path, "message": "Browser-compatible MP4 ready"})
                        else:
                            self._media_tasks[task_id].update({"status": "error", "progress": 0, "message": f"ffmpeg video transcode failed with code {code}"})
                    except Exception as e:
                        self._media_tasks[task_id].update({"status": "error", "message": str(e), "progress": 0})
                    finally:
                        try:
                            if os.path.exists(tmp): os.remove(tmp)
                        except Exception: pass
                threading.Thread(target=video_worker, daemon=True).start()
                return json.dumps({"status": "processing", "task_id": task_id, "mode": "video_proxy", "analysis": analysis}, ensure_ascii=False)

            if mode in ('full', 'full_proxy', 'copy'):
                proxy_path = self._media_proxy_path(filepath)
                if self._is_valid_media_proxy(proxy_path):
                    return json.dumps({"status": "ready", "mode": "full_proxy", "path": proxy_path, "video_path": proxy_path, "proxy": True, "cached": True, "analysis": analysis}, ensure_ascii=False)
                task_id = str(uuid.uuid4())
                self._media_tasks[task_id] = {"status": "running", "mode": "full_proxy", "progress": 0, "path": proxy_path, "source": filepath, "message": "Creating full AAC-compatible copy... 0%"}
                def full_worker():
                    tmp = proxy_path + '.tmp.mkv'
                    try:
                        ffmpeg_bin = get_ffmpeg_path() or 'ffmpeg'
                        cfg = nohomo_merger_core.load_config(get_workflow_dir()) if nohomo_merger_core else {"ffprobe_path": "ffprobe"}
                        dur = nohomo_merger_core.get_duration(filepath, cfg) if nohomo_merger_core else None
                        cmd = [ffmpeg_bin, '-y', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', filepath, '-map', '0:v:0', '-map', '0:a:0', '-map', '0:s?', '-dn', '-c:v', 'copy', '-c:s', 'copy', '-c:a', 'aac', '-b:a', '384k', '-ac', '2', '-map_metadata', '0', '-progress', 'pipe:1', '-nostats', tmp]
                        startupinfo = None
                        if os.name == 'nt':
                            startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
                        if proc.stdout:
                            for line in proc.stdout:
                                line = line.strip()
                                if line.startswith('out_time_ms=') and dur:
                                    try:
                                        out_s = float(line.split('=', 1)[1]) / 1000000.0
                                        pct = max(0, min(99, int((out_s / dur) * 100)))
                                        self._media_tasks[task_id].update({"progress": pct, "message": f"Creating full AAC-compatible copy... {pct}%"})
                                    except Exception: pass
                        code = proc.wait()
                        if code == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1024 * 1024:
                            os.replace(tmp, proxy_path)
                            self._media_tasks[task_id].update({"status": "ready", "progress": 100, "path": proxy_path, "message": "Full AAC-compatible copy ready"})
                        else:
                            self._media_tasks[task_id].update({"status": "error", "progress": 0, "message": f"ffmpeg failed with code {code}"})
                    except Exception as e:
                        self._media_tasks[task_id].update({"status": "error", "message": str(e), "progress": 0})
                    finally:
                        try:
                            if os.path.exists(tmp): os.remove(tmp)
                        except Exception: pass
                threading.Thread(target=full_worker, daemon=True).start()
                return json.dumps({"status": "processing", "task_id": task_id, "mode": "full_proxy", "analysis": analysis}, ensure_ascii=False)

            sidecar_path = self._existing_media_sidecar_path(filepath) or self._media_sidecar_path(filepath)
            if os.path.exists(sidecar_path) and os.path.getsize(sidecar_path) > 128 * 1024:
                return json.dumps({
                    "status": "ready",
                    "mode": "audio_sidecar",
                    "video_path": filepath,
                    "path": filepath,
                    "sidecar_path": sidecar_path,
                    "sidecar": True,
                    "cached": True,
                    "analysis": analysis
                }, ensure_ascii=False)

            # Reuse an already-running task for the same file instead of spawning duplicate FFmpeg jobs.
            for existing_id, existing in list(getattr(self, '_media_tasks', {}).items()):
                try:
                    if existing.get('source') == filepath and existing.get('mode') == 'audio_sidecar' and existing.get('status') == 'running':
                        return json.dumps({"status": "processing", "task_id": existing_id, "mode": "audio_sidecar", "analysis": analysis}, ensure_ascii=False)
                except Exception:
                    pass

            task_id = str(uuid.uuid4())
            self._media_tasks[task_id] = {
                "status": "running",
                "mode": "audio_sidecar",
                "progress": 0,
                "path": filepath,
                "video_path": filepath,
                "sidecar_path": sidecar_path,
                "source": filepath,
                "message": "Creating AAC audio sidecar... 0%"
            }

            def worker():
                import shutil
                safe_dir = get_safe_temp_dir()
                h = hashlib.md5(str(filepath).encode('utf-8', errors='ignore')).hexdigest()
                local_tmp_sidecar = os.path.join(safe_dir, f"audio_sidecar_{h}.{task_id}.tmp.m4a")
                staged_source = None
                staged_part = None
                try:
                    ffmpeg_bin = get_ffmpeg_path() or 'ffmpeg'
                    cfg = nohomo_merger_core.load_config(get_workflow_dir()) if nohomo_merger_core else {"ffprobe_path": "ffprobe"}
                    dur = nohomo_merger_core.get_duration(filepath, cfg) if nohomo_merger_core else None
                    source_for_ffmpeg = filepath
                    if os.path.exists(local_tmp_sidecar):
                        try: os.remove(local_tmp_sidecar)
                        except Exception: pass

                    # Optional SSD staging: if the movie is on a flash/external drive, copy it once to local SSD,
                    # transcode audio from the local copy, then delete the 40-90 GB temporary source.
                    # This costs temporary SSD space, but avoids slow/throttled flash-drive reads during decoding.
                    do_stage, stage_reason = self._should_stage_media_on_local_ssd(filepath, safe_dir)
                    if do_stage:
                        ext = os.path.splitext(filepath)[1] or '.mkv'
                        staged_source = os.path.join(safe_dir, f"audio_stage_{h}{ext}")
                        staged_part = staged_source + ".part"
                        size = os.path.getsize(filepath)
                        copied = 0
                        self._media_tasks[task_id].update({
                            "progress": 0,
                            "message": "Copying movie to local SSD first... 0%"
                        })
                        try:
                            if os.path.exists(staged_source) and os.path.getsize(staged_source) == size:
                                source_for_ffmpeg = staged_source
                                self._media_tasks[task_id].update({"progress": 20, "message": "Local SSD staged copy found. Creating AAC audio..."})
                            else:
                                if os.path.exists(staged_part):
                                    try: os.remove(staged_part)
                                    except Exception: pass
                                with open(filepath, 'rb') as src, open(staged_part, 'wb') as dst:
                                    while True:
                                        chunk = src.read(16 * 1024 * 1024)
                                        if not chunk:
                                            break
                                        dst.write(chunk)
                                        copied += len(chunk)
                                        if size:
                                            pct = max(0, min(20, int((copied / size) * 20)))
                                            self._media_tasks[task_id].update({
                                                "progress": pct,
                                                "message": f"Copying movie to local SSD first... {int((copied / size) * 100)}%"
                                            })
                                os.replace(staged_part, staged_source)
                                source_for_ffmpeg = staged_source
                                self._media_tasks[task_id].update({"progress": 20, "message": "Local SSD copy ready. Creating AAC audio..."})
                        except Exception as copy_error:
                            # Fall back instead of failing playback fix entirely.
                            source_for_ffmpeg = filepath
                            self._media_tasks[task_id].update({
                                "progress": 0,
                                "message": f"SSD staging failed, converting directly from source... ({copy_error})"
                            })
                    else:
                        self._media_tasks[task_id].update({
                            "progress": 0,
                            "message": f"Creating AAC audio sidecar directly... ({stage_reason})"
                        })

                    # Audio-only conversion: tiny output, no video copy, safe for 64 GB flash drives.
                    # Output is written to local SSD first, then moved/copied to final sidecar path.
                    cmd = [
                        ffmpeg_bin, '-y', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-i', source_for_ffmpeg,
                        '-map', selected_audio_map,
                        '-vn', '-sn', '-dn',
                        '-c:a', 'aac', '-b:a', '384k', '-ac', '2',
                        '-map_metadata', '-1',
                        '-movflags', '+faststart',
                        '-progress', 'pipe:1', '-nostats',
                        local_tmp_sidecar
                    ]
                    startupinfo = None
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
                    if proc.stdout:
                        for line in proc.stdout:
                            line = line.strip()
                            if line.startswith('out_time_ms=') and dur:
                                try:
                                    out_s = float(line.split('=', 1)[1]) / 1000000.0
                                    # If staging happened, reserve 0-20% for copy and 20-99% for transcoding.
                                    base = 20 if source_for_ffmpeg == staged_source else 0
                                    span = 79 if source_for_ffmpeg == staged_source else 99
                                    pct = max(base, min(99, base + int((out_s / dur) * span)))
                                    self._media_tasks[task_id].update({
                                        "progress": pct,
                                        "message": f"Creating AAC audio sidecar... {pct}%"
                                    })
                                except Exception:
                                    pass
                            elif line == 'progress=end':
                                self._media_tasks[task_id].update({"progress": 99})
                    code = proc.wait()
                    if code == 0 and self._is_valid_audio_sidecar(local_tmp_sidecar):
                        os.makedirs(os.path.dirname(sidecar_path), exist_ok=True)
                        final_tmp = sidecar_path + ".tmp"
                        try:
                            if os.path.abspath(os.path.dirname(local_tmp_sidecar)) == os.path.abspath(os.path.dirname(sidecar_path)):
                                os.replace(local_tmp_sidecar, sidecar_path)
                            else:
                                shutil.copy2(local_tmp_sidecar, final_tmp)
                                os.replace(final_tmp, sidecar_path)
                                try: os.remove(local_tmp_sidecar)
                                except Exception: pass
                        finally:
                            try:
                                if os.path.exists(final_tmp): os.remove(final_tmp)
                            except Exception:
                                pass
                        self._media_tasks[task_id].update({
                            "status": "ready",
                            "progress": 100,
                            "path": filepath,
                            "video_path": filepath,
                            "sidecar_path": sidecar_path,
                            "message": "AAC audio sidecar ready"
                        })
                    else:
                        self._media_tasks[task_id].update({
                            "status": "error",
                            "progress": 0,
                            "message": f"ffmpeg failed with code {code}. Try another release with AAC/EAC3 audio or install FFmpeg."
                        })
                except Exception as e:
                    self._media_tasks[task_id].update({"status": "error", "message": str(e), "progress": 0})
                finally:
                    for cleanup_path in [local_tmp_sidecar, staged_part, staged_source]:
                        try:
                            if cleanup_path and os.path.exists(cleanup_path):
                                os.remove(cleanup_path)
                        except Exception:
                            pass

            threading.Thread(target=worker, daemon=True).start()
            return json.dumps({"status": "processing", "task_id": task_id, "mode": "audio_sidecar", "analysis": analysis}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def media_task_status(self, task_id):
        import json
        task = self._media_tasks.get(str(task_id), None)
        if not task:
            return json.dumps({"status": "missing", "message": "task not found"}, ensure_ascii=False)
        return json.dumps(task, ensure_ascii=False)

    def select_link_folder(self, mal_id, anime_title):
        """ Opens multi-file dialog on a background thread to prevent deadlocks, copies/remuxes files safely """
        log_to_file(f"=== select_link_folder called for: {anime_title} ===")
        if not self.window:
            return
            
        def worker():
            try:
                file_types = (
                    'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                    'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                    'All Files (*.*)'
                )
                file_paths = self.window.create_file_dialog(
                    dialog_type=webview.OPEN_DIALOG,
                    allow_multiple=True,
                    file_types=file_types
                )
                if not file_paths:
                    try:
                        self.window.evaluate_js("if(window.hideTaskOverlay) window.hideTaskOverlay(0);")
                    except Exception:
                        pass
                    return
                    
                if isinstance(file_paths, (list, tuple)):
                    file_paths = list(file_paths)
                else:
                    file_paths = [file_paths]
                    
                anime_title_str = str(anime_title or "Unknown")
                import re
                clean_title = re.sub(r'[\\/*?:"<>|]', "", anime_title_str).strip()
                anime_dir = os.path.join(DEFAULT_LIBRARY_DIR, clean_title)
                os.makedirs(anime_dir, exist_ok=True)
                
                results = []
                for fp in file_paths:
                    original_name = os.path.basename(fp)
                    original_selected_path = fp
                    
                    ep_match = re.search(r'(?:ep|episode|s\d+e|series|серия|серии)?\s*(\d+)', original_name, re.IGNORECASE)
                    if ep_match:
                        ep_num = int(ep_match.group(1))
                    else:
                        ep_num = 1
                        
                    ext = os.path.splitext(original_name)[1].lower()
                    target_name = f"Episode_{ep_num}{ext}"
                    if ext == '.ts':
                        target_name = f"Episode_{ep_num}.mp4"
                        
                    target_path = os.path.join(anime_dir, target_name)
                    
                    try:
                        if ext == '.ts':
                            ffmpeg_bin = get_ffmpeg_path()
                            if ffmpeg_bin:
                                cmd = [ffmpeg_bin, "-y", "-i", fp, "-c", "copy", "-map_metadata", "0", target_path]
                                startupinfo = None
                                if os.name == 'nt':
                                    startupinfo = subprocess.STARTUPINFO()
                                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
                                proc.communicate(timeout=15)
                                if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
                                    results.append({
                                        'path': target_path,
                                        'name': target_name
                                    })
                                else:
                                    results.append({
                                        'path': original_selected_path,
                                        'name': original_name
                                    })
                            else:
                                results.append({
                                        'path': original_selected_path,
                                        'name': original_name
                                    })
                        else:
                            # Large movie/episode files must be linked by reference, not copied.
                            # Copying 40-90GB files makes the app look frozen and wastes disk space.
                            try:
                                file_size = os.path.getsize(fp)
                            except Exception:
                                file_size = 0
                            if file_size > 512 * 1024 * 1024:
                                results.append({
                                    'path': original_selected_path,
                                    'name': original_name,
                                    'linked_directly': True,
                                    'size': file_size
                                })
                            else:
                                import shutil
                                shutil.copy2(fp, target_path)
                                results.append({
                                    'path': target_path,
                                    'name': target_name,
                                    'linked_directly': False,
                                    'size': file_size
                                })
                    except Exception as e:
                        log_to_file(f"Folder copy/remux failed, fallback to original: {e}")
                        results.append({
                            'path': original_selected_path,
                            'name': original_name
                        })
                        
                import json
                js_code = f"completeMultipleEpisodesLinking({mal_id}, {json.dumps(results)});"
                self.window.evaluate_js(js_code)
            except Exception as e:
                log_to_file(f"Exception in select_link_folder worker: {e}")
                
        threading.Thread(target=worker, daemon=True).start()


    def select_link_file(self, mal_id, ep_num, anime_title):
        """ Opens file dialog on a background thread to prevent deadlocks, copies/remuxes file safely, and returns path """
        log_to_file(f"=== select_link_file called for: {anime_title}, ep: {ep_num} ===")
        if not self.window:
            return
            
        def worker():
            try:
                file_types = (
                    'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                    'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                    'All Files (*.*)'
                )
                file_paths = self.window.create_file_dialog(
                    dialog_type=webview.OPEN_DIALOG,
                    allow_multiple=False,
                    file_types=file_types
                )
                if not file_paths:
                    try:
                        self.window.evaluate_js("if(window.cancelEpisodeLinking) window.cancelEpisodeLinking(); else if(window.hideTaskOverlay) window.hideTaskOverlay(0);")
                    except Exception:
                        pass
                    return
                    
                fp = file_paths[0] if isinstance(file_paths, (list, tuple)) else file_paths
                original_selected_path = fp
                original_name = os.path.basename(fp)
                try:
                    self.window.evaluate_js("if(window.showTaskOverlay) window.showTaskOverlay('Linking selected media...', 'Preparing the selected file. Large files are linked directly.');")
                except Exception:
                    pass
                
                anime_title_str = str(anime_title or "Unknown")
                import re
                clean_title = re.sub(r'[\\/*?:"<>|]', "", anime_title_str).strip()
                anime_dir = os.path.join(DEFAULT_LIBRARY_DIR, clean_title)
                os.makedirs(anime_dir, exist_ok=True)
                
                ext = os.path.splitext(original_name)[1].lower()
                target_name = f"Episode_{ep_num}{ext}"
                if ext == '.ts':
                    target_name = f"Episode_{ep_num}.mp4"
                    
                target_path = os.path.join(anime_dir, target_name)
                
                is_remuxed = False
                is_direct_link = False
                try:
                    if ext == '.ts':
                        ffmpeg_bin = get_ffmpeg_path()
                        if ffmpeg_bin:
                            cmd = [ffmpeg_bin, "-y", "-i", fp, "-c", "copy", "-map_metadata", "0", target_path]
                            startupinfo = None
                            if os.name == 'nt':
                                startupinfo = subprocess.STARTUPINFO()
                                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
                            proc.communicate(timeout=15)
                            if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
                                fp = target_path
                                original_name = target_name
                                is_remuxed = True
                    else:
                        # For large files, link original path directly. Do not copy huge movies into the app library.
                        try:
                            file_size = os.path.getsize(fp)
                        except Exception:
                            file_size = 0
                        if file_size > 512 * 1024 * 1024:
                            fp = original_selected_path
                            original_name = os.path.basename(fp)
                            is_direct_link = True
                        else:
                            import shutil
                            shutil.copy2(fp, target_path)
                            fp = target_path
                            original_name = target_name
                            is_direct_link = False
                except Exception as e:
                    log_to_file(f"Copying/remuxing failed, fallback to original path: {e}")
                    fp = original_selected_path
                    original_name = os.path.basename(fp)
                    
                import json
                processed_file = {"path": fp, "name": original_name, "is_remuxed": is_remuxed, "linked_directly": is_direct_link}
                js_code = f"completeEpisodeLinking({mal_id}, {ep_num}, {json.dumps(processed_file)});"
                self.window.evaluate_js(js_code)
            except Exception as e:
                log_to_file(f"Exception in select_link_file worker: {e}")
                
        threading.Thread(target=worker, daemon=True).start()

    def select_files(self):
        """ Opens a fully native OS file selection dialog via a non-blocking thread to prevent deadlocks """
        log_to_file("=== select_files called ===")
        if not self.window:
            return []
            
        def worker():
            try:
                log_to_file("Worker thread started for select_files.")
                file_types = (
                    'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                    'Audio Files (*.mp3;*.wav;*.ogg;*.m4a;*.aac;*.flac)',
                    'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                    'All Files (*.*)'
                )
                
                file_paths = self.window.create_file_dialog(
                    dialog_type=webview.OPEN_DIALOG,
                    allow_multiple=True,
                    file_types=file_types
                )
                log_to_file(f"create_file_dialog returned: {file_paths}")
                
                if not file_paths:
                    return
                    
                if isinstance(file_paths, (list, tuple)):
                    file_paths = list(file_paths)
                else:
                    file_paths = [file_paths]
                    
                results = []
                for fp in file_paths:
                    name = os.path.basename(fp)
                    results.append({
                        'path': fp,
                        'name': name
                    })
                log_to_file(f"Selected files results: {results}")
                
                import json
                js_code = f"addFilesToPlaylist({json.dumps(results)});"
                self.window.evaluate_js(js_code)
            except Exception as e:
                log_to_file(f"Exception in select_files worker: {e}")
                
        threading.Thread(target=worker, daemon=True).start()
        return []

    def toggle_native_fullscreen(self):
        """ Toggles the OS-level borderless window fullscreen """
        if self.window:
            self.window.toggle_fullscreen()

    def merger_open_folder(self, folder_key="raw_folder"):
        """Opens RAW/DUB/OUTPUT workflow folder in the OS file manager."""
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            allowed = {"raw_folder", "dub_folder", "output_folder", "test_folder"}
            key = folder_key if folder_key in allowed else "raw_folder"
            path = nohomo_merger_core.resolve_path(cfg.get(key) or "./raw", cfg)
            os.makedirs(path, exist_ok=True)
            if os.name == 'nt':
                os.startfile(path)
            else:
                subprocess.Popen(['xdg-open', path] if sys.platform.startswith('linux') else ['open', path])
            return json.dumps({"status": "success", "path": path}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def merger_get_config(self):
        """Loads nohomo merger config for the integrated RAW/DUB workflow."""
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            return json.dumps({"status": "success", "config": cfg}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def merger_scan(self):
        """Scans RAW and DUB folders, remuxes TS DUB files, and returns matched episode pairs."""
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            data = nohomo_merger_core.scan_project(cfg)
            folders = {
                "raw": nohomo_merger_core.resolve_path(cfg.get('raw_folder') or './raw', cfg),
                "dub": nohomo_merger_core.resolve_path(cfg.get('dub_folder') or './dub', cfg),
                "output": nohomo_merger_core.resolve_path(cfg.get('output_folder') or './output', cfg)
            }
            return json.dumps({"status": "success", "folders": folders, **data}, ensure_ascii=False)
        except Exception as e:
            log_to_file(f"merger_scan failed: {e}")
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def merger_autosync(self, episode_num=0, dub_track=None):
        """Runs music/SFX autosync for a matched episode and returns the recommended offset."""
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            scan = nohomo_merger_core.scan_project(cfg)
            pairs = scan.get('matched', [])
            if episode_num:
                pairs = [p for p in pairs if p['raw'].get('episode') == int(episode_num)]
            if not pairs:
                return json.dumps({"status": "empty", "message": "No matched RAW/DUB episode pair found"}, ensure_ascii=False)
            pair = pairs[0]
            track = int(dub_track if dub_track is not None else cfg.get('dub_audio_track', 0))
            res = nohomo_merger_core.autosync(pair['raw']['path'], pair['dub']['path'], cfg, track)
            return json.dumps({"status": "success", "pair": pair, "autosync": res}, ensure_ascii=False)
        except Exception as e:
            log_to_file(f"merger_autosync failed: {e}")
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def merger_run(self, episode_num=0, offset=0.0, dub_track=None, title="", voice_mode="off", sync_mode="global"):
        """Runs final RAW video + DUB audio merge and optionally organizes output into the local library folder."""
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            scan = nohomo_merger_core.scan_project(cfg)
            pairs = scan.get('matched', [])
            if episode_num:
                pairs = [p for p in pairs if p['raw'].get('episode') == int(episode_num)]
            if not pairs:
                return json.dumps({"status": "empty", "message": "No matched RAW/DUB episode pair found"}, ensure_ascii=False)
            track = int(dub_track if dub_track is not None else cfg.get('dub_audio_track', 0))
            out_dir = nohomo_merger_core.resolve_path(cfg.get('output_folder') or './output', cfg)
            os.makedirs(out_dir, exist_ok=True)
            results = []
            for pair in pairs:
                raw = pair['raw']; dub = pair['dub']
                base = os.path.splitext(raw['name'])[0]
                output = os.path.join(out_dir, base + '_RusDub.mkv')
                merged = nohomo_merger_core.merge(raw['path'], dub['path'], output, cfg, float(offset), track, voice_mode=voice_mode, sync_mode=sync_mode)
                if merged.get('ok') and cfg.get('organize_after_merge', True):
                    org_title = title or base.split('S01E')[0].replace('.', ' ').strip() or 'Unknown'
                    organized = nohomo_merger_core.organize_output(
                        merged['output'], org_title, raw.get('season') or 1, raw.get('episode') or 1,
                        cfg.get('library_root') or DEFAULT_LIBRARY_DIR
                    )
                    merged['organized'] = organized
                results.append({"pair": pair, "result": merged})
            return json.dumps({"status": "success", "results": results}, ensure_ascii=False)
        except Exception as e:
            log_to_file(f"merger_run failed: {e}")
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def merger_import_downloads(self, target="dub_folder", move=True):
        """Moves recently downloaded episode-like media files from ~/Downloads into raw/ or dub/.
        Only files with detectable episode numbers are imported to avoid moving random videos.
        """
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            key = target if target in ("raw_folder", "dub_folder") else "dub_folder"
            dest = nohomo_merger_core.resolve_path(cfg.get(key) or ("./dub" if key == "dub_folder" else "./raw"), cfg)
            os.makedirs(dest, exist_ok=True)
            imported = []
            skipped = []
            if not os.path.exists(downloads):
                return json.dumps({"status": "error", "message": "Downloads folder not found"}, ensure_ascii=False)
            for name in os.listdir(downloads):
                src = os.path.join(downloads, name)
                if not os.path.isfile(src):
                    continue
                ext = os.path.splitext(name)[1].lower()
                if ext not in nohomo_merger_core.VIDEO_EXTS:
                    continue
                ep = nohomo_merger_core.extract_episode(name)
                # DUB workflow: browser/downloader often outputs MPEG-TS with Russian movie title and no S/E.
                # Import those to dub/ as movie/special candidates instead of forcing manual moves.
                is_movie_like_dub = (key == "dub_folder" and ext == ".ts")
                if ep is None and not is_movie_like_dub:
                    skipped.append({"name": name, "reason": "no episode number"})
                    continue
                if ep is None and is_movie_like_dub:
                    ep = 1
                target_path = os.path.join(dest, name)
                if os.path.exists(target_path):
                    base, ext2 = os.path.splitext(name)
                    target_path = os.path.join(dest, f"{base}_{int(os.path.getmtime(src))}{ext2}")
                if move:
                    import shutil
                    shutil.move(src, target_path)
                else:
                    import shutil
                    shutil.copy2(src, target_path)
                imported.append({"name": os.path.basename(target_path), "path": target_path, "episode": ep})
            return json.dumps({"status": "success", "target": key, "folder": dest, "imported": imported, "skipped": skipped}, ensure_ascii=False)
        except Exception as e:
            log_to_file(f"merger_import_downloads failed: {e}")
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def merger_list_outputs(self):
        """Lists merged output files for Library linking."""
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            out_dir = nohomo_merger_core.resolve_path(cfg.get('output_folder') or './output', cfg)
            files = nohomo_merger_core.find_videos(out_dir)
            return json.dumps({"status": "success", "folder": out_dir, "files": files}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def merger_autosync_merge_all(self, title="", voice_mode="off", sync_mode="auto"):
        """Sequentially autosyncs every matched RAW/DUB pair and builds all outputs.
        This is intentionally sequential to avoid Demucs/FFmpeg GPU/RAM contention.
        """
        import json
        if not nohomo_merger_core:
            return json.dumps({"status": "error", "message": "nohomo_merger_core is not available"}, ensure_ascii=False)
        try:
            cfg = nohomo_merger_core.load_config(get_workflow_dir())
            scan = nohomo_merger_core.scan_project(cfg)
            pairs = scan.get('matched', [])
            if not pairs:
                return json.dumps({"status": "empty", "message": "No matched RAW/DUB episode pairs found"}, ensure_ascii=False)
            track = int(cfg.get('dub_audio_track', 0))
            out_dir = nohomo_merger_core.resolve_path(cfg.get('output_folder') or './output', cfg)
            os.makedirs(out_dir, exist_ok=True)
            results = []
            for pair in pairs:
                raw = pair['raw']; dub = pair['dub']
                sync = nohomo_merger_core.autosync(raw['path'], dub['path'], cfg, track)
                offset = float(sync.get('offset') or 0.0) if isinstance(sync, dict) else 0.0
                base = os.path.splitext(raw['name'])[0]
                output = os.path.join(out_dir, base + '_RusDub.mkv')
                merged = nohomo_merger_core.merge(raw['path'], dub['path'], output, cfg, offset, track, voice_mode=voice_mode, sync_mode=sync_mode)
                if merged.get('ok') and cfg.get('organize_after_merge', True):
                    org_title = title or base.split('S01E')[0].replace('.', ' ').strip() or 'Unknown'
                    merged['organized'] = nohomo_merger_core.organize_output(
                        merged['output'], org_title, raw.get('season') or 1, raw.get('episode') or 1,
                        cfg.get('library_root') or DEFAULT_LIBRARY_DIR
                    )
                results.append({"pair": pair, "autosync": sync, "result": merged})
            return json.dumps({"status": "success", "results": results}, ensure_ascii=False)
        except Exception as e:
            log_to_file(f"merger_autosync_merge_all failed: {e}")
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

    def _find_chromium_executable(self):
        """Find Chrome/Edge/Brave for extension-capable DUB Browser mode."""
        import shutil
        candidates = []
        try:
            keys = self._load_keys_dict() if hasattr(self, '_load_keys_dict') else {}
            for k in ('CHROMIUM_PATH', 'CHROME_PATH', 'EDGE_PATH', 'BRAVE_PATH', 'DUB_CHROMIUM_PATH'):
                v = keys.get(k) or os.environ.get(k)
                if v:
                    candidates.append(str(v).strip('"'))
        except Exception:
            pass
        if os.name == 'nt':
            envs = [os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'), os.environ.get('LOCALAPPDATA')]
            rels = [
                r"Google\Chrome\Application\chrome.exe",
                r"Microsoft\Edge\Application\msedge.exe",
                r"BraveSoftware\Brave-Browser\Application\brave.exe",
                r"Chromium\Application\chrome.exe",
            ]
            for base in envs:
                if base:
                    for rel in rels:
                        candidates.append(os.path.join(base, rel))
        for name in ['chrome', 'google-chrome', 'msedge', 'microsoft-edge', 'brave', 'brave-browser', 'chromium', 'chromium-browser']:
            found = shutil.which(name)
            if found:
                candidates.append(found)
        for c in candidates:
            try:
                if c and os.path.exists(c):
                    return c
            except Exception:
                pass
        return ""

    def _write_text_if_changed(self, path, content):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            old = None
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    old = f.read()
            if old != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return True
        except Exception as e:
            log_to_file(f"Failed writing file {path}: {e}")
            return False

    def _ensure_dub_chromium_extensions(self):
        """Create built-in Chrome extensions for DUB Browser Bridge.

        This provides:
        - MMP Userscript Manager (Tampermonkey-lite, visible-page/browser-assisted)
        - MMP AdBlock Lite (small declarative blocker)

        Real uBlock Origin/Tampermonkey can additionally be loaded if the user places unpacked extension folders at:
          extensions/ublock_origin/
          extensions/tampermonkey/
        """
        import json
        base = os.path.join(get_workflow_dir(), 'data', 'dub_chromium_extensions')
        user_ext = os.path.join(base, 'mmp_userscripts')
        adblock_ext = os.path.join(base, 'mmp_adblock_lite')
        script_file = os.path.join(get_workflow_dir(), 'data', 'dub_userscript.user.js')
        if not os.path.exists(script_file):
            self._write_text_if_changed(script_file, """// Built-in DUB userscript. Paste your Tampermonkey JS here, then reopen DUB Browser.\n// This runs in the dedicated Chromium DUB Browser profile.\nconsole.log('[MMP DUB] built-in user script loaded:', location.href);\n""")
        try:
            with open(script_file, 'r', encoding='utf-8', errors='replace') as f:
                user_script = f.read()
        except Exception:
            user_script = "console.log('[MMP DUB] no user script');"

        manifest = {
            "manifest_version": 3,
            "name": "MMP DUB Userscripts",
            "version": "1.0.0",
            "description": "Built-in userscript manager for Minimal Media Player DUB Browser.",
            "permissions": ["storage", "scripting", "downloads", "notifications"],
            "host_permissions": ["<all_urls>"],
            "background": {"service_worker": "background.js"},
            "content_scripts": [{"matches": ["<all_urls>"], "js": ["content.js"], "run_at": "document_idle", "all_frames": False}],
            "web_accessible_resources": [{"resources": ["page_script.js"], "matches": ["<all_urls>"]}]
        }
        background = """
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg) return;
  if (msg.type === 'GM_XHR') {
    fetch(msg.url, { method: msg.method || 'GET', headers: msg.headers || {}, body: msg.body || undefined, credentials: 'include' })
      .then(async r => sendResponse({ ok:true, status:r.status, statusText:r.statusText, responseText: await r.text(), finalUrl:r.url }))
      .catch(e => sendResponse({ ok:false, error: String(e && e.stack || e) }));
    return true;
  }
  if (msg.type === 'GM_DOWNLOAD') {
    const d = msg.details || {};
    const url = d.url || d.href;
    if (!url) { sendResponse({ ok:false, error:'GM_download: url is missing' }); return; }
    const filename = d.name || d.filename || undefined;
    chrome.downloads.download({ url, filename, saveAs: !!d.saveAs, conflictAction: d.conflictAction || 'uniquify' }, (downloadId) => {
      const err = chrome.runtime.lastError;
      if (err) sendResponse({ ok:false, error: err.message });
      else sendResponse({ ok:true, downloadId });
    });
    return true;
  }
});
"""        # JSON-embed user script safely.
        page_script = f"""
(function() {{
  if (window.__MMP_CHROME_DUB_USERSCRIPT__) return;
  window.__MMP_CHROME_DUB_USERSCRIPT__ = true;
  const BUILTIN_USER_SCRIPT = {json.dumps(user_script)};
  function GM_addStyle(css) {{ const s=document.createElement('style'); s.textContent=css; (document.head||document.documentElement).appendChild(s); return s; }}
  function GM_getValue(k,d) {{ try {{ const v=localStorage.getItem('mmp_gm_'+k); return v===null?d:JSON.parse(v); }} catch(e) {{ return d; }} }}
  function GM_setValue(k,v) {{ try {{ localStorage.setItem('mmp_gm_'+k, JSON.stringify(v)); }} catch(e) {{}} }}
  function GM_deleteValue(k) {{ try {{ localStorage.removeItem('mmp_gm_'+k); }} catch(e) {{}} }}
  function GM_log(...a) {{ console.log('[MMP GM]', ...a); }}
  function GM_xmlhttpRequest(details) {{
    window.postMessage({{__mmp_gm_xhr:true, id: Math.random().toString(36).slice(2), details}}, '*');
  }}
  const GM_xmlHttpRequest = GM_xmlhttpRequest;
  const GM_info = {{ scriptHandler: 'MMP DUB Userscripts', version: '1.0.0', script: {{ name: 'MMP custom DUB userscript', version: '1.0.0', namespace: 'mmp-dub' }}, platform: {{ browserName: 'Chromium/WebView', arch: 'x64' }} }};
  const GM = {{ info: GM_info, getValue: GM_getValue, setValue: GM_setValue, deleteValue: GM_deleteValue, addStyle: GM_addStyle, xmlHttpRequest: GM_xmlhttpRequest, xmlhttpRequest: GM_xmlhttpRequest, log: GM_log }};
  window.addEventListener('message', (ev) => {{
    const m=ev.data; if(!m || !m.__mmp_gm_xhr_result) return;
    const cb=window.__mmp_gm_callbacks && window.__mmp_gm_callbacks[m.id];
    if(cb) {{ try {{ (m.ok ? cb.onload : cb.onerror)(m.response); }} catch(e) {{ console.error(e); }} delete window.__mmp_gm_callbacks[m.id]; }}
  }});
  // Override GM_xmlhttpRequest with callback bridge.
  GM_xmlhttpRequest = function(details) {{
    const id=Math.random().toString(36).slice(2);
    window.__mmp_gm_callbacks = window.__mmp_gm_callbacks || {{}};
    window.__mmp_gm_callbacks[id] = {{ onload: details.onload || function(){{}}, onerror: details.onerror || function(){{}} }};
    window.postMessage({{__mmp_gm_xhr:true, id, details}}, '*');
  }};
  try {{
    new Function('GM_getValue','GM_setValue','GM_deleteValue','GM_addStyle','GM_xmlhttpRequest','GM_xmlHttpRequest','GM_info','GM','GM_log','unsafeWindow', BUILTIN_USER_SCRIPT + '\n//# sourceURL=mmp-builtin-dub-userscript.user.js')(
      GM_getValue, GM_setValue, GM_deleteValue, GM_addStyle, GM_xmlhttpRequest, GM_xmlHttpRequest, GM_info, GM, GM_log, window
    );
  }} catch(e) {{ console.error('[MMP DUB Userscript] failed:', e); }}
}})();
"""
        content = """
(function(){
  if (window.__MMP_DUB_CONTENT__) return;
  window.__MMP_DUB_CONTENT__ = true;
  const page = document.createElement('script');
  page.src = chrome.runtime.getURL('page_script.js');
  page.onload = () => page.remove();
  (document.head || document.documentElement).appendChild(page);
  window.addEventListener('message', (ev) => {
    const m = ev.data;
    if (!m || !m.__mmp_gm_xhr || !m.details) return;
    chrome.runtime.sendMessage({ type:'GM_XHR', url:m.details.url, method:m.details.method, headers:m.details.headers, body:m.details.data || m.details.body }, (res) => {
      window.postMessage({ __mmp_gm_xhr_result:true, id:m.id, ok: !!(res && res.ok), response: res || { ok:false, error:'no response' } }, '*');
    });
  });
})();
"""
        # Prefer the maintained content script file. It provides persistent panel/storage/autofill across login navigation.
        try:
            content_path = get_asset_path(os.path.join('templates', 'dub_chromium_content.js'))
            if os.path.exists(content_path):
                with open(content_path, 'r', encoding='utf-8', errors='replace') as cf:
                    content = cf.read()
        except Exception as ce:
            log_to_file(f"Failed to load dub_chromium_content.js, using fallback content: {ce}")

        self._write_text_if_changed(os.path.join(user_ext, 'manifest.json'), json.dumps(manifest, ensure_ascii=False, indent=2))
        self._write_text_if_changed(os.path.join(user_ext, 'background.js'), background)
        self._write_text_if_changed(os.path.join(user_ext, 'content.js'), content)
        self._write_text_if_changed(os.path.join(user_ext, 'page_script.js'), page_script)

        ad_manifest = {
            "manifest_version": 3,
            "name": "MMP AdBlock Lite",
            "version": "1.0.0",
            "description": "Small built-in declarative ad blocker for DUB Browser.",
            "permissions": ["declarativeNetRequest"],
            "host_permissions": ["<all_urls>"],
            "declarative_net_request": {"rule_resources": [{"id": "ruleset_1", "enabled": True, "path": "rules.json"}]}
        }
        rules = []
        domains = [
            'doubleclick.net','googlesyndication.com','googleadservices.com','adservice.google.com','adnxs.com','adsystem.com',
            'popads.net','popcash.net','onclickads.net','propellerads.com','adsterra.com','exoclick.com','trafficjunky.net',
            'mgid.com','taboola.com','outbrain.com','yandex.ru/ads','mc.yandex.ru','facebook.net','hotjar.com'
        ]
        rid = 1
        for d in domains:
            rules.append({"id": rid, "priority": 1, "action": {"type": "block"}, "condition": {"urlFilter": d, "resourceTypes": ["script","image","xmlhttprequest","sub_frame","media","font","stylesheet","ping","other"]}})
            rid += 1
        self._write_text_if_changed(os.path.join(adblock_ext, 'manifest.json'), json.dumps(ad_manifest, ensure_ascii=False, indent=2))
        self._write_text_if_changed(os.path.join(adblock_ext, 'rules.json'), json.dumps(rules, ensure_ascii=False, indent=2))

        exts = [user_ext, adblock_ext]
        # Optional real extension folders if user supplies unpacked copies.
        for extra in [os.path.join(get_workflow_dir(), 'extensions', 'tampermonkey'), os.path.join(get_workflow_dir(), 'extensions', 'ublock_origin')]:
            if os.path.exists(os.path.join(extra, 'manifest.json')):
                exts.append(extra)
        return exts, script_file

    def open_chromium_dub_browser(self, url, title="", season=1, episode=0):
        """Launch a dedicated extension-capable Chromium app window for DUB browser-assisted workflow."""
        try:
            # Extension-capable mode: a dedicated Chrome/Edge app window with isolated profile, userscripts and adblock.
            keys = self._load_keys_dict() if hasattr(self, '_load_keys_dict') else {}
            mode = str(keys.get('DUB_BROWSER_MODE', 'chromium')).lower().strip()
            if mode in ('chromium', 'chrome', 'extension', 'tampermonkey'):
                if self.open_chromium_dub_browser(url, title, season, episode):
                    return True
                log_to_file('Chromium DUB Browser unavailable; falling back to WebView DUB Browser')

            safe_url = str(url or "https://rezka.fi/").strip() or "https://rezka.fi/"
            if not (safe_url.startswith('http://') or safe_url.startswith('https://')):
                safe_url = 'https://' + safe_url
            chrome = self._find_chromium_executable()
            if not chrome:
                log_to_file('Chromium DUB Browser requested but Chrome/Edge/Brave was not found')
                return False
            exts, script_file = self._ensure_dub_chromium_extensions()
            profile = os.path.join(get_workflow_dir(), 'data', 'dub_chromium_profile')
            os.makedirs(profile, exist_ok=True)
            ext_arg = ','.join(exts)
            cmd = [
                chrome,
                f'--user-data-dir={profile}',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-popup-blocking',
                '--autoplay-policy=no-user-gesture-required',
                f'--disable-extensions-except={ext_arg}',
                f'--load-extension={ext_arg}',
                f'--app={safe_url}'
            ]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            self.dub_context = {"title": title or "", "season": int(season or 1), "episode": int(episode or 0), "url": safe_url, "mode": "chromium", "userscript_file": script_file}
            log_to_file(f"Chromium DUB Browser launched: {safe_url}; userscript={script_file}; extensions={ext_arg}")
            return True
        except Exception as e:
            log_to_file(f"open_chromium_dub_browser failed: {e}")
            return False

    def _get_dub_userscript_bootstrap(self):
        try:
            path = get_asset_path(os.path.join('templates', 'dub_userscript_bootstrap.js'))
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            log_to_file(f"Failed to load DUB userscript bootstrap: {e}")
        return ""

    def _inject_dub_userscript_later(self, dub_window, reason=""):
        """Lightweight visible-page userscript injection for DUB Browser.
        This is Tampermonkey-lite UI/autofill/custom script support only, not a hidden extractor/downloader.
        """
        try:
            script = self._get_dub_userscript_bootstrap()
            if not script:
                return False
            wrapped = "(function(){\n" + script + "\n})();"
            dub_window.evaluate_js(wrapped)
            log_to_file(f"DUB userscript bootstrap injected ({reason})")
            return True
        except Exception as e:
            log_to_file(f"DUB userscript injection failed ({reason}): {e}")
            return False

    def open_internal_url(self, url, title="", season=1, episode=0):
        """Opens the in-app DUB Browser through a lightweight loading screen, then navigates safely.

        Stability strategy:
        - first show a local loading screen instantly;
        - use normal visible WebView cookies/profile so login can persist;
        - inject a small Tampermonkey-lite bootstrap after navigation, with retries;
        - no hidden extractor/downloader logic.
        """
        try:
            safe_url = str(url or "https://rezka.fi/").strip() or "https://rezka.fi/"
            if not (safe_url.startswith("http://") or safe_url.startswith("https://")):
                safe_url = "https://" + safe_url

            loader_url = (
                f"http://127.0.0.1:{PORT}/dub-loading?"
                + urllib.parse.urlencode({
                    "target": safe_url,
                    "title": title or "",
                    "season": str(int(season or 1)),
                    "episode": str(int(episode or 0))
                })
            )

            dub_window = webview.create_window(
                title="DUB Browser",
                url=loader_url,
                width=1180,
                height=760,
                min_size=(900, 560),
                background_color="#050508"
            )
            self.dub_window = dub_window
            self.dub_context = {"title": title or "", "season": int(season or 1), "episode": int(episode or 0), "url": safe_url}

            # WebView fallback: inject on every navigation/load event. Login pages often redirect and replace the document,
            # so a one-time injection disappears. This keeps the :3 userscript panel alive after sign-in.
            try:
                if hasattr(dub_window, 'events') and hasattr(dub_window.events, 'loaded'):
                    def _on_dub_loaded():
                        try:
                            # slight delay so late DOM/head exists
                            threading.Timer(0.8, lambda: self._inject_dub_userscript_later(dub_window, 'webview-loaded-event')).start()
                            threading.Timer(2.2, lambda: self._inject_dub_userscript_later(dub_window, 'webview-loaded-event-late')).start()
                        except Exception as ev_e:
                            log_to_file(f"DUB loaded-event injection scheduling failed: {ev_e}")
                    dub_window.events.loaded += _on_dub_loaded
                    log_to_file('DUB Browser loaded-event userscript hook attached')
            except Exception as hook_e:
                log_to_file(f"Failed to attach DUB loaded-event hook: {hook_e}")

            def delayed_navigation():
                import time
                time.sleep(0.7)
                try:
                    self._inject_dub_userscript_later(dub_window, 'loader-page')
                except Exception:
                    pass
                time.sleep(0.9)
                try:
                    dub_window.load_url(safe_url)
                    log_to_file(f"DUB Browser navigated to source after loading screen: {safe_url}")
                    # WebView fallback only: a few reinjections after login redirects/reloads.
                    # Keep this limited: evaluate_js on heavy ad pages can make WebView appear Not Responding.
                    for i in range(10):
                        time.sleep(3.0)
                        try:
                            self._inject_dub_userscript_later(dub_window, f'periodic-{i+1}')
                        except Exception as ie:
                            log_to_file(f"DUB Browser userscript retry failed: {ie}")
                except Exception as e:
                    log_to_file(f"DUB Browser delayed navigation failed: {e}")

            threading.Thread(target=delayed_navigation, daemon=True).start()
            log_to_file(f"DUB Browser loading screen opened: {safe_url}")
            return True
        except Exception as e:
            log_to_file(f"open_internal_url failed: {e}")
            return False


    def open_external_url(self, url):
        """Fallback: opens a URL in the user's default browser."""
        try:
            import webbrowser
            webbrowser.open(str(url or ""))
            return True
        except Exception as e:
            log_to_file(f"open_external_url failed: {e}")
            return False

    def get_file_duration(self, filepath):
        """ Retrieves the duration of a video file in seconds (Pure TS Parser + FFmpeg fallback + Est Fallback) """
        log_to_file(f"=== get_file_duration called for: {filepath} ===")
        if not filepath:
            log_to_file("Filepath is empty!")
            return 0
            
        # Safer path checking (resolves corruption with % characters in raw file paths)
        exists_raw = os.path.exists(filepath)
        log_to_file(f"Raw filepath exists: {exists_raw}")
        
        if not exists_raw:
            unquoted = urllib.parse.unquote(filepath)
            exists_unquoted = os.path.exists(unquoted)
            log_to_file(f"Unquoted filepath: {unquoted}")
            log_to_file(f"Unquoted filepath exists: {exists_unquoted}")
            if exists_unquoted:
                filepath = unquoted
            else:
                log_to_file("File not found anywhere on disk!")
                return 0
                
        # Priority 1: If it's a TS file, use our ultra-fast pure Python parser first!
        if filepath.lower().endswith('.ts'):
            log_to_file("File is TS, running pure TS parser...")
            try:
                pure_dur = get_ts_duration_pure(filepath)
                log_to_file(f"Pure TS parser returned: {pure_dur}")
                if pure_dur > 0:
                    return pure_dur
            except Exception as e:
                log_to_file(f"Pure TS parser failed: {e}")
                
        # Priority 2: General FFmpeg fallback
        log_to_file("Running FFmpeg fallback...")
        try:
            cmd = ["ffmpeg", "-i", filepath]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, startupinfo=startupinfo)
            _, errs = proc.communicate(timeout=2)
            if errs and isinstance(errs, str):
                dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", errs)
                if dur_match:
                    hours = int(dur_match.group(1))
                    minutes = int(dur_match.group(2))
                    seconds = float(dur_match.group(3))
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                    log_to_file(f"FFmpeg returned: {total_seconds}")
                    return total_seconds
            log_to_file("FFmpeg did not find duration match or output was empty.")
        except Exception as e:
            log_to_file(f"FFmpeg fallback failed: {e}")
            
        # Priority 3: Ultimate Fallback - estimate duration based on file size if other methods fail!
        log_to_file("Running file size estimation fallback...")
        try:
            size = os.path.getsize(filepath)
            est_dur = size / 200000.0  # ~1.6 Mbps average (typical for HDRezka downloads)
            if est_dur > 0:
                log_to_file(f"Estimated duration {est_dur}s based on size {size} bytes")
                return est_dur
        except Exception as e:
            log_to_file(f"Size estimation fallback failed: {e}")
            
        return 0

    def get_ai_franchise_search_plan(self, query, category, candidates_json="[]"):
        """
        GPT + Tavily franchise detector for search results.
        Decides whether a query should be collapsed into ONE franchise hub or shown as individual standalone results.
        This is the general auto-search solution; famous-franchise tables are only local fallbacks.
        """
        import json
        import urllib.request
        import time
        
        query = str(query or "").strip()
        category = str(category or "anime").strip().lower()
        log_to_file(f"=== get_ai_franchise_search_plan called for: {query} [{category}] ===")
        if not query:
            return json.dumps({"status": "error", "should_collapse": False, "reason": "empty query"}, ensure_ascii=False)
        
        try:
            candidates = json.loads(candidates_json) if candidates_json else []
            if not isinstance(candidates, list):
                candidates = []
        except Exception:
            candidates = []
        candidates = candidates[:20]
        
        # Keys
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        keys_file = get_keys_file()
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    keys = json.load(f)
                    openai_key = openai_key or keys.get("OPENAI_API_KEY", "")
                    tavily_key = tavily_key or keys.get("TAVILY_API_KEY", "")
            except Exception as e:
                log_to_file(f"Error reading keys.json in franchise search plan: {e}")
        
        if not openai_key or not tavily_key:
            return json.dumps({"status": "no_keys", "should_collapse": False}, ensure_ascii=False)
        
        now = time.time()
        self._ai_franchise_request_times = [t for t in self._ai_franchise_request_times if now - t < 60]
        if len(self._ai_franchise_request_times) >= 100:
            return json.dumps({"status": "rate_limited", "should_collapse": False}, ensure_ascii=False)
        self._ai_franchise_request_times.append(now)
        
        def post_json(url, payload, headers, timeout=12):
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        
        web_context = ""
        try:
            tavily_payload = {
                "api_key": tavily_key,
                "query": f"{query} franchise watch order main entry movies seasons chronology is it franchise or standalone",
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 6
            }
            t_res = post_json("https://api.tavily.com/search", tavily_payload, {"Content-Type": "application/json"}, timeout=10)
            chunks = []
            if t_res.get("answer"):
                chunks.append("Answer: " + str(t_res.get("answer")))
            for r in t_res.get("results", [])[:6]:
                chunks.append(f"Title: {r.get('title','')}\nURL: {r.get('url','')}\nContent: {r.get('content','')}")
            web_context = "\n\n".join(chunks)[:10000]
        except Exception as e:
            log_to_file(f"Tavily franchise search plan failed: {e}")
        
        system_prompt = (
            "You are a media search architect. Your job is to decide whether search results should be displayed "
            "as one unified franchise hub or as separate standalone titles. You must be conservative: collapse only "
            "when the query clearly targets a franchise/saga/series universe. Output ONLY JSON."
        )
        prompt_template = """
User query: "{query}"
Search category: "{category}"

Visible search candidates from the app:
{candidates_json}

Web evidence:
{web_context}

Decide if the UI should collapse these results into ONE franchise hub.

Rules:
1. If the query is a franchise/saga/universe with multiple seasons/movies/OVAs/spin-offs (Bleach, Fate, Spider-Man, Star Wars, Harry Potter, Breaking Bad universe), return should_collapse=true.
2. If the query is a single standalone title with no meaningful watch-order structure, return should_collapse=false.
3. Do NOT collapse unrelated titles that only share words.
4. Pick the best root candidate from the provided candidates: the main series / first film / franchise entry point.
5. For anime, root_title should usually be the original main TV title, not an OVA/movie unless the franchise starts with a movie.
6. For movies, root_title should be the first/main franchise film or a hub title if no single candidate is clearly the root.
7. Keep labels short for UI.

Return only JSON:
{
  "status": "success",
  "should_collapse": true,
  "confidence": 0.0,
  "media_kind": "anime/movie/show",
  "hub_title": "Clean Franchise Hub title",
  "canonical_title": "Canonical franchise name",
  "root_title": "Best root candidate title from candidates if possible",
  "reason": "short Russian reason for developer/user",
  "standalone": false
}
"""
        short_candidates = []
        for idx, c in enumerate(candidates[:20], start=1):
            short_candidates.append({
                "num": idx,
                "id": c.get("mal_id") or c.get("id"),
                "title": c.get("title") or c.get("name"),
                "type": c.get("type"),
                "episodes": c.get("episodes"),
                "year": c.get("year")
            })
        prompt = (prompt_template
            .replace("{query}", query)
            .replace("{category}", category)
            .replace("{candidates_json}", json.dumps(short_candidates, ensure_ascii=False, indent=2))
            .replace("{web_context}", web_context or "No web evidence."))
        
        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.05,
                "response_format": {"type": "json_object"}
            }
            res = post_json(
                "https://api.openai.com/v1/chat/completions",
                payload,
                {"Content-Type": "application/json", "Authorization": f"Bearer {openai_key}"},
                timeout=16
            )
            raw = res["choices"][0]["message"]["content"].strip()
            parsed = json.loads(raw)
            parsed.setdefault("status", "success")
            parsed["should_collapse"] = bool(parsed.get("should_collapse"))
            return json.dumps(parsed, ensure_ascii=False)
        except Exception as e:
            log_to_file(f"OpenAI franchise search plan failed: {e}")
            return json.dumps({"status": "error", "should_collapse": False, "message": str(e)}, ensure_ascii=False)


    def get_ai_franchise_info(self, title):
        """
        GPT + Tavily chronology compiler v2.
        Builds a validated watch-order/season structure for anime AND regular TV shows.
        It is intentionally strict: every returned part must belong to the requested franchise,
        preventing dry database mismatches like Breaking Bad -> random anime.
        """
        import json
        import urllib.request
        import time
        import hashlib
        
        title = str(title or "").strip()
        log_to_file(f"=== get_ai_franchise_info v2 called for: {title} ===")
        if not title:
            return json.dumps({"status": "error", "message": "empty title"})
        
        # 0. Safe local cache: prevents repeated double-click spam and keeps us under API limits.
        cache_key = title.lower()
        cached = self._ai_franchise_cache.get(cache_key)
        if cached and (time.time() - cached.get("ts", 0) < 24 * 3600):
            log_to_file("AI franchise cache hit")
            return json.dumps(cached["data"], ensure_ascii=False)
        
        # 1. Read API keys from environment or keys.json local file.
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        keys_file = get_keys_file()
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    keys = json.load(f)
                    openai_key = openai_key or keys.get("OPENAI_API_KEY", "")
                    tavily_key = tavily_key or keys.get("TAVILY_API_KEY", "")
            except Exception as e:
                log_to_file(f"Error reading keys.json: {e}")
        else:
            try:
                with open(keys_file, "w", encoding="utf-8") as f:
                    json.dump({"OPENAI_API_KEY": "", "TAVILY_API_KEY": "", "QBIT_URL": "", "QBIT_USERNAME": "", "QBIT_PASSWORD": "", "MOVIE_RAW_PROVIDER": "prowlarr", "PROWLARR_URL": "http://127.0.0.1:9696", "PROWLARR_API_KEY": "", "FLARESOLVERR_PATH": "", "FLARESOLVERR_URL": "http://127.0.0.1:8191", "FLARESOLVERR_AUTOSTART": False}, f, indent=4, ensure_ascii=False)
            except Exception:
                pass
        
        if not openai_key or not tavily_key:
            log_to_file("Missing API keys, returning status: no_keys")
            return json.dumps({"status": "no_keys"})
        
        # 2. Rate limit: max 100 Tavily/GPT chronology transactions per minute.
        now = time.time()
        self._ai_franchise_request_times = [t for t in self._ai_franchise_request_times if now - t < 60]
        if len(self._ai_franchise_request_times) >= 100:
            return json.dumps({"status": "rate_limited", "message": "Chronology API limit reached. Try again in a minute."}, ensure_ascii=False)
        self._ai_franchise_request_times.append(now)
        
        def post_json(url, payload, headers, timeout=12):
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        
        # 3. Tavily: retrieve independent web context. We ask broadly and force validation later.
        tavily_context = []
        try:
            tavily_payload = {
                "api_key": tavily_key,
                "query": f"{title} official watch order seasons episodes chronology franchise guide wiki imdb myanimelist",
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 8
            }
            tavily_res = post_json(
                "https://api.tavily.com/search",
                tavily_payload,
                {"Content-Type": "application/json"},
                timeout=10
            )
            if tavily_res.get("answer"):
                tavily_context.append("Answer: " + str(tavily_res.get("answer")))
            for r in tavily_res.get("results", [])[:8]:
                tavily_context.append(
                    f"Title: {r.get('title','')}\nURL: {r.get('url','')}\nContent: {r.get('content','')}"
                )
        except Exception as e:
            log_to_file(f"Tavily chronology lookup failed: {e}")
        
        web_context = "\n\n".join(tavily_context)[:12000]
        
        # 4. GPT strict compiler. No f-string template braces here except JSON sample is escaped by normal string concatenation.
        system_prompt = (
            "You are a senior media-franchise archivist and video-library engineer. "
            "You build clean watch-order structures for anime and regular TV shows. "
            "Your highest priority is identity validation: never attach an unrelated franchise just because a database search result has a similar word. "
            "Use web context first, then common knowledge. Output ONLY valid JSON."
        )
        user_prompt_template = """
Requested title: "{title}"

Web evidence from Tavily:
{web_context}

Task:
Build a clean, validated chronology / season structure for the requested title.

Hard rules:
1. Validate every entry against the requested franchise. If the requested title is a live-action show like Breaking Bad, do NOT return anime results. If the requested title is anime, do NOT return unrelated similarly named shows.
2. Number the watch order explicitly: 1, 2, 3, ... . Use relation labels like Prequel, Season 1, Season 2, Movie, OVA, Side story, Spin-off, Final season.
3. Keep the structure clean for UI tabs: no paragraph soup inside names. Each part name must be short and displayable.
4. Return a practical episode count for each part. For movies/specials use episodes=1. If unknown, use a safe estimate but mark confidence lower.
5. For complex franchises such as Fate, Bleach, Monogatari, JoJo, Attack on Titan, use the real viewing chronology, not a random database order.
6. If web evidence is weak, return the main title only instead of inventing unrelated entries.

Return ONLY this JSON object, no markdown:
{
  "status": "success",
  "confidence": 0.0,
  "media_kind": "anime_or_tv_or_movie",
  "synopsis": "Russian synopsis of the active title",
  "studios_str": "studio / network / distributor",
  "genres_str": "genres",
  "source": "Manga / Novel / Original / TV / Unknown",
  "score": 0,
  "airing_status": "Completed / Currently Airing / Unknown",
  "franchise": [
    {
      "id": 123,
      "order": 1,
      "name": "Short display name",
      "relation": "Season 1 / Prequel / Movie / OVA / Spin-off",
      "type": "TV / Movie / OVA / Special",
      "year": 2020,
      "episodes": 12,
      "confidence": 0.0
    }
  ]
}
"""
        user_prompt = user_prompt_template.replace("{title}", title).replace("{web_context}", web_context or "No reliable web evidence returned.")
        
        try:
            openai_payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.05,
                "response_format": {"type": "json_object"}
            }
            res_data = post_json(
                "https://api.openai.com/v1/chat/completions",
                openai_payload,
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}"
                },
                timeout=18
            )
            raw_text = res_data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(raw_text)
            
            if parsed.get("status") != "success" or not isinstance(parsed.get("franchise"), list):
                raise ValueError("AI returned invalid schema")
            
            # 5. Defensive post-validation and stable IDs for non-MAL / live-action parts.
            clean_franchise = []
            seen_names = set()
            for i, part in enumerate(parsed.get("franchise", [])[:40], start=1):
                name = str(part.get("name") or "").strip()
                if not name:
                    continue
                key = name.lower()
                if key in seen_names:
                    continue
                seen_names.add(key)
                raw_id = part.get("id")
                try:
                    stable_id = int(raw_id)
                except Exception:
                    stable_id = int(hashlib.md5((title + name).encode("utf-8", errors="ignore")).hexdigest()[:8], 16)
                episodes = part.get("episodes", 12)
                try:
                    episodes = int(episodes)
                except Exception:
                    episodes = 12
                episodes = max(1, min(500, episodes))
                clean_franchise.append({
                    "id": stable_id,
                    "order": int(part.get("order") or i),
                    "name": name,
                    "relation": str(part.get("relation") or f"Part {i}"),
                    "type": str(part.get("type") or "TV"),
                    "year": int(part.get("year") or 0),
                    "episodes": episodes,
                    "confidence": float(part.get("confidence") or parsed.get("confidence") or 0.6)
                })
            
            clean_franchise.sort(key=lambda x: (x.get("order", 999), x.get("year") or 9999, x.get("name", "")))
            parsed["franchise"] = clean_franchise
            parsed["status"] = "success"
            
            self._ai_franchise_cache[cache_key] = {"ts": time.time(), "data": parsed}
            log_to_file(f"Successfully generated validated chronology with {len(clean_franchise)} parts")
            return json.dumps(parsed, ensure_ascii=False)
        except Exception as e:
            log_to_file(f"OpenAI chronology completion failed: {e}")
            return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


    def save_db_data(self, key, data_json):
        """Permanently saves JSON data on disk using atomic replace + workflow backup.
        This prevents half-written DB files if the app is closed during a save.
        """
        log_to_file(f"=== save_db_data called for key: {key} ===")
        if not USER_DATA_DIR:
            return False
        try:
            clean_key = "".join([c for c in key if c.isalnum() or c in ("_", "-")])
            if not clean_key:
                return False

            def atomic_write(path, content):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp_path = path + ".tmp"
                bak_path = path + ".bak"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                    try:
                        f.flush()
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                try:
                    if os.path.exists(path):
                        try:
                            import shutil
                            shutil.copy2(path, bak_path)
                        except Exception:
                            pass
                    os.replace(tmp_path, path)
                finally:
                    try:
                        if os.path.exists(tmp_path): os.remove(tmp_path)
                    except Exception:
                        pass

            file_path = os.path.join(USER_DATA_DIR, f"db_{clean_key}.json")
            atomic_write(file_path, data_json)

            # Extra project-root backup for safer migrations between dev/exe/dist storage modes.
            try:
                backup_path = os.path.join(get_workflow_data_dir("db"), f"db_{clean_key}.json")
                if os.path.abspath(backup_path) != os.path.abspath(file_path):
                    atomic_write(backup_path, data_json)
            except Exception as be:
                log_to_file(f"Failed to save workflow backup database file: {be}")
            log_to_file(f"Successfully saved permanent database file: {file_path}")
            return True
        except Exception as e:
            log_to_file(f"Failed to save database file: {e}")
            return False

    def load_db_data(self, key):
        """ Permanently loads JSON data from the user's hard drive """
        log_to_file(f"=== load_db_data called for key: {key} ===")
        if not USER_DATA_DIR:
            return "{}"
        try:
            clean_key = "".join([c for c in key if c.isalnum() or c in ("_", "-")])
            file_path = os.path.join(USER_DATA_DIR, f"db_{clean_key}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                log_to_file(f"Successfully loaded permanent database file: {file_path}")
                return content
            else:
                log_to_file(f"Database file does not exist: {file_path}")
                return "{}"
        except Exception as e:
            log_to_file(f"Failed to load database file: {e}")
            return "{}"


    def load_all_databases(self):
        """ Symmetrically bundles and loads all 5 databases in a single, lightning-fast IPC transaction """
        log_to_file("=== load_all_databases called ===")
        import json
        result = {
            "library": "{}",
            "watching_progress": "{}",
            "viewing_history": "{}",
            "playlist": "{}",
            "playlist_index": "{}"
        }
        if not USER_DATA_DIR:
            return json.dumps(result)
            
        try:
            for key in result.keys():
                clean_key = "".join([c for c in key if c.isalnum() or c in ("_", "-")])
                candidates = [
                    os.path.join(USER_DATA_DIR, f"db_{clean_key}.json"),
                    os.path.join(USER_DATA_DIR, f"db_{clean_key}.json.bak"),
                    os.path.join(get_workflow_data_dir("db"), f"db_{clean_key}.json"),
                    os.path.join(get_workflow_data_dir("db"), f"db_{clean_key}.json.bak"),
                    # Legacy root backups are still read for migration/backward compatibility.
                    os.path.join(get_workflow_dir(), f"db_{clean_key}.json"),
                    os.path.join(get_workflow_dir(), f"db_{clean_key}.json.bak"),
                    os.path.join(get_exe_dir(), f"db_{clean_key}.json"),
                    os.path.join(get_exe_dir(), f"db_{clean_key}.json.bak"),
                ]
                for file_path in candidates:
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        # Prefer first non-empty meaningful database, but allow .bak/workflow backup if AppData is empty/corrupt.
                        if content and content.strip() not in ("", "{}", "[]"):
                            try:
                                json.loads(content)
                            except Exception:
                                log_to_file(f"Skipping corrupt database candidate: {file_path}")
                                continue
                            result[key] = content
                            break
            log_to_file("Successfully loaded all 5 databases permanently in a single transaction!")
        except Exception as e:
            log_to_file(f"Failed to load databases in transaction: {e}")
            
        return json.dumps(result)


    def start_magnet_link(self, magnet_link):
        """ Launches the magnet link in the user's default OS torrent client """
        log_to_file(f"=== start_magnet_link called for: {magnet_link[:60]}... ===")
        try:
            import os
            if os.name == 'nt':
                os.startfile(magnet_link)
            else:
                import subprocess
                import sys
                subprocess.run(['xdg-open', magnet_link] if sys.platform.startswith('linux') else ['open', magnet_link])
            return True
        except Exception as e:
            log_to_file(f"Failed to start magnet link: {e}")
            return False

    def download_torrent_to_watch(self, torrent_link, title):
        """ Downloads the .torrent file directly into C:\\Users\\Public\\MinimalMediaPlayer\\downloads\\ """
        log_to_file(f"=== download_torrent_to_watch called for: {title} ===")
        try:
            import urllib.request
            import re
            
            download_dir = os.path.join(DEFAULT_LIBRARY_DIR, "downloads")
            os.makedirs(download_dir, exist_ok=True)
            
            clean_filename = re.sub(r'[\\/*?:"<>|]', '_', title).strip()
            filepath = os.path.join(download_dir, clean_filename + ".torrent")
            
            req = urllib.request.Request(
                torrent_link, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                with open(filepath, 'wb') as f:
                    f.write(response.read())
            return filepath
        except Exception as e:
            log_to_file(f"Failed to download torrent: {e}")
            return ""

    def search_nyaa_torrents(self, query, fast=False):
        """
        Symmetrically runs the entire NoHomo Downloader v1.3+ AI/Expert pipeline with 100% crash-proof safety!
        1. Translates Russian queries to English/Japanese via Tavily + GPT or local dict.
        2. Queries Nyaa.si FULL HTML Database (no weekly limits) and parses results using regex.
        3. Runs Local Expert analysis calculating NOHOMO Score and tags, resolving FRENCH and Chinese-character bugs.
        4. Queries GPT-4o-mini with our uncompromising VCB-Studio priority and duplicate-free ongoing curator prompt!
        """
        import json
        import urllib.request
        import urllib.parse
        import re
        import os
        
        log_to_file(f"=== search_nyaa_torrents called for: {query} ===")
        
        try:
            openai_key = os.environ.get("OPENAI_API_KEY", "")
            tavily_key = os.environ.get("TAVILY_API_KEY", "")
            
            keys_file = get_keys_file()
            if os.path.exists(keys_file):
                try:
                    with open(keys_file, "r", encoding="utf-8") as f:
                        keys = json.load(f)
                        if not openai_key:
                            openai_key = keys.get("OPENAI_API_KEY", "")
                        if not tavily_key:
                            tavily_key = keys.get("TAVILY_API_KEY", "")
                except Exception as e:
                    log_to_file(f"Error reading keys.json in downloader: {e}")
                    
            # ═══════════════════════════════════════════════════════
            #  1. EXPAND / TRANSLATE QUERY WITH AI OR LOCAL DICT
            # ═══════════════════════════════════════════════════════
            processed_query = query
            has_cyrillic = bool(re.search('[а-яА-Я]', query))
            
            tavily_info = ""
            if has_cyrillic:
                if tavily_key:
                    try:
                        search_query = f"аниме {query} оригинальное японское и английское название romaji English title"
                        req_data = json.dumps({
                            "api_key": tavily_key,
                            "query": search_query,
                            "search_depth": "basic",
                            "include_answer": True
                        }).encode('utf-8')
                        
                        req = urllib.request.Request(
                            "https://api.tavily.com/search",
                            data=req_data,
                            headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=5) as response:
                            res = json.loads(response.read().decode('utf-8'))
                            tavily_info = res.get("answer", "")
                            if not tavily_info and res.get("results"):
                                tavily_info = " ".join([r.get("content", "") for r in res["results"][:2]])
                    except Exception as e:
                        log_to_file(f"Tavily translation search failed: {e}")
                        
                if openai_key:
                    try:
                        system_prompt = "Ты — умный ассистент, который переводит русские названия аниме/манги в точные английские и японские названия для поиска на англоязычном торрент-трекере Nyaa.si."
                        user_prompt = f"Переведи русское название аниме/манги '{query}' в его точное официальное английское название и японское название (ромадзи)."
                        if tavily_info:
                            user_prompt += f"\\nВот свежие данные из интернета (Tavily) для помощи:\\n{tavily_info}"
                        user_prompt += "\\nВыведи в ответ ТОЛЬКО точные ключевые слова для поиска (например: \"Kill Blue\" OR \"Kill Ao\"), без лишних слов, вступлений, точек в конце и кавычек."

                        req_data = json.dumps({
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "temperature": 0.1
                        }).encode('utf-8')
                        
                        req = urllib.request.Request(
                            "https://api.openai.com/v1/chat/completions",
                            data=req_data,
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {openai_key}"
                            }
                        )
                        with urllib.request.urlopen(req, timeout=10) as response:
                            res_json = json.loads(response.read().decode('utf-8'))
                            processed_query = res_json['choices'][0]['message']['content'].strip()
                            processed_query = processed_query.replace('"', '').replace("'", "")
                            log_to_file(f"GPT translation successfully resolved: '{query}' -> '{processed_query}'")
                    except Exception as e:
                        log_to_file(f"GPT translation failed: {e}")
                else:
                    # Local Dictionary Fallback
                    local_dict = {
                        "убивая юность": "Kill Blue",
                        "школа тюрьма": "Prison School",
                        "школа-тюрьма": "Prison School",
                        "клинок рассекающий демонов": "Demon Slayer Kimetsu no Yaiba",
                        "клинок рассекающий": "Demon Slayer Kimetsu no Yaiba",
                        "магическая битва": "Jujutsu Kaisen",
                        "человек бензопила": "Chainsaw Man",
                        "человек-бензопила": "Chainsaw Man",
                        "атака титанов": "Attack on Titan",
                        "ветролом": "Wind Breaker",
                        "синяя коробка": "Blue Box"
                    }
                    cleaned_q = query.lower().strip()
                    if cleaned_q in local_dict:
                        processed_query = local_dict[cleaned_q]
                        log_to_file(f"Local dict translation resolved: {processed_query}")

            # ═══════════════════════════════════════════════════════
            #  2. QUERY NYAA.SI FULL HTML DATABASE PARSER (v1.3)
            # ═══════════════════════════════════════════════════════
            def search_nyaa(q):  
                import urllib.request  
                import urllib.parse  
                import re  
              
                url = 'https://nyaa.si/?f=0&c=0_0&q=' + urllib.parse.quote(q)  
                req = urllib.request.Request(  
                    url,   
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}  
                )  
                  
                try:  
                    with urllib.request.urlopen(req, timeout=10) as response:  
                        html = response.read().decode('utf-8', errors='replace')  
                except Exception as e_nyaa:  
                    log_to_file(f"search_nyaa HTTP request failed: {e_nyaa}")
                    return []  
              
                rows = re.findall(r'<tr class="(?:default|success|danger|info)">(.+?)</tr>', html, re.DOTALL)  
                results = []  
                  
                for row in rows:  
                    try:  
                        title_match = re.search(r'href="/view/(\d+)"\s+title="([^"]+)"', row)  
                        if not title_match:  
                            title_match = re.search(r'title="([^"]+)"\s+href="/view/(\d+)"', row)  
                        if not title_match:  
                            continue  
                              
                        view_id = title_match.group(1) if title_match.group(1).isdigit() else title_match.group(2)  
                        title = title_match.group(2) if title_match.group(1).isdigit() else title_match.group(1)  
                          
                        # Декодирование HTML сущностей  
                        title = title.replace('&amp;amp;', '&').replace('&amp;quot;', '"').replace('&amp;lt;', '<').replace('&amp;gt;', '>')  
                          
                        magnet_match = re.search(r'href="(magnet:\?[^"]+)"', row)  
                        magnet_link = magnet_match.group(1) if magnet_match else ""  
                          
                        cat_match = re.search(r'href="/\?c=(\d_\d)"', row)  
                        cat_id = cat_match.group(1) if cat_match else "0_0"  
                          
                        torrent_link = f"https://nyaa.si/download/{view_id}.torrent"  
                          
                        tds = re.findall(r'<td class="text-center"[^>]*>(.+?)</td>', row, re.DOTALL)  
                        if len(tds) < 4:  
                            continue  
                              
                        size_val = re.sub(r'<[^>]+>', '', tds[1]).strip()  
                        seeders_clean = re.sub(r'<[^>]+>', '', tds[3]).strip()  
                        seeders_val = int(seeders_clean) if seeders_clean.isdigit() else 0  
                        leechers_clean = re.sub(r'<[^>]+>', '', tds[4]).strip()  
                        leechers_val = int(leechers_clean) if leechers_clean.isdigit() else 0  
              
                        results.append({  
                            'title': title,  
                            'torrent_link': torrent_link,  
                            'magnet_link': magnet_link,  
                            'seeders': seeders_val,  
                            'leechers': leechers_val,  
                            'size': size_val,  
                            'cat_id': cat_id  
                        })  
                    except:  
                        continue  
                          
                return results

            nyaa_results = search_nyaa(processed_query)

            if not nyaa_results:
                return json.dumps({"status": "empty", "query": processed_query, "results": []})

            # ═══════════════════════════════════════════════════════
            #  3. Железобетонный локальный экспертный анализ (полный фикс ложного BATCH)
            # ═══════════════════════════════════════════════════════
            def local_expert_analysis(items):  
                import re  
                analyzed = []  
                
                def parse_size_to_gb(size_str):
                    if not size_str:
                        return 0.0
                    try:
                        clean = size_str.lower().strip()
                        match = re.search(r'([0-9.]+)\s*([a-z]+)', clean)
                        if not match:
                            return 0.0
                        val = float(match.group(1))
                        unit = match.group(2)
                        if 'm' in unit:  # MB, MiB
                            return val / 1024.0
                        elif 'g' in unit:  # GB, GiB
                            return val
                        elif 't' in unit:  # TB, TiB
                            return val * 1024.0
                        return val
                    except Exception:
                        return 0.0
                  
                for idx, item in enumerate(items):  
                    title = item['title']  
                    seeders = item['seeders']  
                    cat_id = item.get('cat_id', '0_0')  
                    size_gb = parse_size_to_gb(item.get('size', ''))
                      
                    # 1. Сверхточное определение типа контента (Пак против Одиночной серии)  
                    r_type = "SINGLE"  
                    if cat_id.startswith("3_") or any(k in title.lower() for k in ["chapter", "ch.", "vol.", "cbz", "cbr", "manga"]):  
                        r_type = "MANGA"  
                    elif cat_id.startswith("2_"):  
                        r_type = "AUDIO"  
                    else:  
                        # Сначала проверяем на явные признаки одиночной серии (EP01, E01, Episode 1, S01E07)  
                        is_single = re.search(r'\b(ep(?:isode|s)?\s*\d{1,3}|e\d{1,3})\b', title, re.IGNORECASE)  
                        if not is_single:  
                            is_single = re.search(r'[sS]\d{1,2}[eE]\d{1,3}', title)  
                        if not is_single:
                            is_single = re.search(r'\s-\s\d{1,3}\b', title)
                              
                        if is_single or size_gb < 2.5:  
                            r_type = "SINGLE"  
                        else:  
                            # Если явных признаков серии нет, проверяем на признаки пака (Batch/Complete/Season)  
                            is_batch = any(k in title.lower() for k in ["batch", "complete", "pack", "collection", "s01-s", "s1-", "01-12", "01-24"])
                            if not is_batch:
                                season_match = re.search(r'\b(season\s*\d+|s\d{1,2})\b', title, re.IGNORECASE)
                                if season_match:
                                    is_batch = not re.search(r'[sS]\d{1,2}[eE]\d{1,3}', title)
                                    
                            if is_batch or size_gb >= 4.5:  
                                r_type = "BATCH"  
                          
                    # 2. Цензура (Регулярка с \b исключает ложный мэтч на "FRENCH" и поддерживает oads/ovas)  
                    censorship = "UNKNOWN"  
                    if re.search(r'\b(uncensored|uncut|no-censorship|nc|oads?|ovas?)\b', title, re.IGNORECASE) or "无修" in title:  
                        censorship = "UNCENSORED"  
                    elif re.search(r'\b(tv|censored)\b', title, re.IGNORECASE):  
                        censorship = "CENSORED"  
                          
                    # 3. Источник  
                    source = "WEB-DL"  
                    if any(k in title.lower() for k in ["remux", "bdremux"]):  
                        source = "BDRemux"  
                    elif any(k in title.lower() for k in ["bd", "bluray", "blue-ray", "bdrip"]):  
                        source = "BDRip"  
                    elif "dvd" in title.lower():  
                        source = "DVDRip"  
                    elif "hdtv" in title.lower() or "tvrip" in title.lower():  
                        source = "HDTV"  
                          
                    # 4. Релиз-группы  
                    group = "UNKNOWN"  
                    group_rating = 50  
                    comment = ""  
                      
                    group_mappings = {  
                        "vcb-studio": (100, "VCB-Studio", "Легендарный релиз! Ручная чистка картинки, 10-бит цвет, полное устранение дефектов оригинального диска. Шедевр кодинга. ⭐⭐⭐⭐⭐"),  
                        "reaktor": (95, "Reaktor", "Великолепный x265 пак без цензуры. Шикарный баланс размера и качества картинки! ⭐⭐⭐⭐"),  
                        "tenrai-sensei": (90, "Tenrai-Sensei", "Качественный x265/HEVC пак всего сезона. Отличная скорость скачивания. ⭐⭐⭐⭐"),  
                        "varyg": (93, "VARYG", "Превосходный мульти-аудио веб-рип. Идеален для склейки, содержит оригинальный качественный звук Amazon/CR. ⭐⭐⭐⭐"),  
                        "subsplease": (85, "SubsPlease", "Стабильный и чистый untouched WEB-DL со стримингов. Хороший оригинальный битрейт. ⭐⭐⭐"),  
                        "erai-raws": (85, "Erai-raws", "Untouched WEB-DL рип со стримингов. Хороший оригинальный битрейт. ⭐⭐⭐"),  
                        "moozzi2": (80, "Moozzi2", "DVD/BD-рип от Moozzi2. Картинка сочная и яркая, но иногда присутствует перенасыщение цветов. ⭐⭐⭐"),  
                        "tsundere-raws": (82, "Tsundere-Raws", "Качественные рипы, ориентированные на французскую аудиторию. Хороший битрейт. ⭐⭐⭐"),
                        "anime time": (96, "Anime Time", "Исключительное качество BDRip от легендарной группы! Потрясающий битрейт и обработка. ⭐⭐⭐⭐⭐")
                    }  
                      
                    for key, (rating, name, comm) in group_mappings.items():  
                        if key in title.lower():  
                            group = name  
                            group_rating = rating  
                            comment = comm  
                            break  
                              
                    # 5. Оценка Score  
                    score = group_rating  
                      
                    if seeders > 50: score += 15  
                    elif seeders > 20: score += 10  
                    elif seeders > 5: score += 5  
                    elif seeders == 0: score -= 50  
                      
                    if source == "BDRip": score += 20  
                    elif source == "BDRemux": score += 25  
                    elif source == "WEB-DL": score += 10  
                    elif source == "HDTV": score -= 10  
                      
                    if censorship == "UNCENSORED":  
                        score += 30  
                          
                    if r_type == "MANGA":  
                        score -= 60  
              
                    analyzed.append({  
                        'idx': idx + 1,  
                        'title': title,  
                        'size': item['size'],  
                        'seeders': seeders,  
                        'leechers': item.get('leechers', 0),  
                        'type': r_type,  
                        'censorship': censorship,  
                        'source': source,  
                        'group': group,  
                        'comment': comment,  
                        'score': score,  
                        'magnet_link': item['magnet_link'],  
                        'torrent_link': item['torrent_link']  
                    })  
                      
                analyzed.sort(key=lambda x: x['score'], reverse=True)  
                return analyzed

            expert_results = local_expert_analysis(nyaa_results)

            # ═══════════════════════════════════════════════════════
            #  4. NEXT-GEN LOCAL ONGOING CURATOR ENGINE v2 (FALLBACK)
            # ═══════════════════════════════════════════════════════
            ai_verdict = ""
            if expert_results:
                batches = [r for r in expert_results if r['type'] == 'BATCH' and r['score'] >= 85]
                
                if batches:
                    best_batch = batches[0]
                    ai_verdict += f"👑 РЕКОМЕНДУЕМ ПОЛНЫЙ ПАК (BATCH): №{best_batch['idx']}\n"
                    ai_verdict += f"Релиз: {best_batch['title']}\n"
                    ai_verdict += f"Размер: {best_batch['size']} | Сиды: {best_batch['seeders']}\n"
                    if best_batch['comment']:
                        ai_verdict += f"Локальный технический анализ: {best_batch['comment']}\n"
                    ai_verdict += f"NOHOMO Score: {best_batch['score']} баллов.\n"
                    ai_verdict += f"Скачать: <a href=\"{best_batch['magnet_link']}\" style=\"color: #06B6D4; font-weight: bold; text-decoration: none;\">[Magnet]</a> <a href=\"{best_batch['torrent_link']}\" style=\"color: #8B5CF6; font-weight: bold; text-decoration: none; margin-left: 10px;\">[Torrent]</a>\n\n"
                    ai_verdict += "📝 УМНЫЙ ПОШАГОВЫЙ ГИД ДЛЯ ПОЛЬЗОВАТЕЛЯ:\n"
                    ai_verdict += "Для этого тайтла доступны превосходные полные Blu-ray коллекции!\n"
                    ai_verdict += "Рекомендуем скачать этот полный пак, но скачивайте его пошагово, выбирая галочками в торрент-клиенте только нужные серии по очереди, чтобы сэкономить место на жестком диске!\n"
                else:
                    ai_verdict += "👑 ИИ-КУРАТОР: РЕКОМЕНДУЕМЫЙ ПОШАГОВЫЙ НАБОР СЕРИЙ (так как целого пака еще нет):\n"
                    ai_verdict += "Собрали для вас лучшие раздачи по каждой серии с максимальным битрейтом и сидами:\n\n"
                    
                    episodes_map = {}
                    for r in expert_results:
                        original_name = r['title']
                        
                        clean_title = original_name.lower()
                        clean_title = re.sub(r'\b\d+-bit\b', '', clean_title)
                        clean_title = re.sub(r'\b\d+(\.\d+)?\s*(khz|mhz|gb|mb|gib|mib)\b', '', clean_title)
                        clean_title = re.sub(r'\b\d{3,4}x\d{3,4}\b', '', clean_title)
                        
                        ep_num = None
                        se_match = re.search(r's\d+e(\d+)', clean_title)
                        if se_match:
                            ep_num = int(se_match.group(1))
                        else:
                            ep_match = re.search(r'\b(?:ep|e|episode|серия|серии|эпизод)\s*(\d+)\b', clean_title)
                            if ep_match:
                                ep_num = int(ep_match.group(1))
                            else:
                                solitary_match = re.search(r'\s-\s(\d+)\b', clean_title)
                                if solitary_match:
                                    ep_num = int(solitary_match.group(1))
                        
                        if ep_num is not None:
                            if ep_num not in episodes_map or r['score'] > episodes_map[ep_num]['score']:
                                episodes_map[ep_num] = r
                                
                    sorted_eps = sorted(episodes_map.keys())
                    if sorted_eps:
                        for ep_num in sorted_eps:
                            best_ep_rel = episodes_map[ep_num]
                            group_lbl = f" [{best_ep_rel['group']}]" if best_ep_rel['group'] != "UNKNOWN" else ""
                            ai_verdict += f"• Серия {ep_num} ➔ №{best_ep_rel['idx']}{group_lbl} ({best_ep_rel['size']}) | Сидов: {best_ep_rel['seeders']}"
                            ai_verdict += f" <a href=\"{best_ep_rel['magnet_link']}\" style=\"color: #06B6D4; font-weight: bold; text-decoration: none;\">[Magnet]</a> <a href=\"{best_ep_rel['torrent_link']}\" style=\"color: #8B5CF6; font-weight: bold; text-decoration: none; margin-left: 5px;\">[Torrent]</a>\n"
                            short_title = best_ep_rel['title'][:65] + "..." if len(best_ep_rel['title']) > 65 else best_ep_rel['title']
                            ai_verdict += f"  {short_title}\n\n"
                        ai_verdict += "Рекомендуем скачать эти индивидуальные серии через Magnet для лучшего качества!\n\n"
                    else:
                        best_choice = expert_results[0]
                        ai_verdict += f"• Рекомендуемый торрент: №{best_choice['idx']} ({best_choice['size']}) | Сидов: {best_choice['seeders']}"
                        ai_verdict += f" <a href=\"{best_choice['magnet_link']}\" style=\"color: #06B6D4; font-weight: bold; text-decoration: none;\">[Magnet]</a> <a href=\"{best_choice['torrent_link']}\" style=\"color: #8B5CF6; font-weight: bold; text-decoration: none; margin-left: 5px;\">[Torrent]</a>\n"
                        ai_verdict += f"  {best_choice['title']}\n\n"
            # ═══════════════════════════════════════════════════════
            #  5. МЕГА-УМНЫЙ ВЫЗОВ GPT API С ГЕНЕРАЦИЕЙ КЛИКАБЕЛЬНЫХ КНОПОК
            # ═══════════════════════════════════════════════════════
            if openai_key and not fast:
                try:
                    short_list = []
                    for idx, item in enumerate(expert_results[:15]):
                        short_list.append({
                            "num": idx + 1,
                            "title": item['title'],
                            "size": item['size'],
                            "seeders": item['seeders'],
                            "score": item.get('score', 0),
                            "type": item.get('type', 'SINGLE'),
                            "censorship": item.get('censorship', 'UNKNOWN'),
                            "magnet_link": item.get('magnet_link', ''),
                            "torrent_link": item.get('torrent_link', '')
                        })
                    
                    system_prompt = "Ты — профессиональный эксперт по аниме-релизам и видеокодекам."
                    
                    user_prompt_template = """Ты — профессиональный эксперт-анимешник и технический специалист по прецизионному кодированию видео.  
Перед тобой список торрент-раздач с сайта [Nyaa.si](http://Nyaa.si) по поисковому запросу "{query}".  
  
Твоя задача — выбрать АБСОЛЮТНО ЛУЧШУЮ раздачу, руководствуясь следующими ЖЕСТКИМИ профессиональными правилами:  
  
1. МАТЕМАТИЧЕСКИЙ ПРИОРИТЕТ ВЫСШЕГО БАЛЛА (SCORE):  
   - Тебе передаются результаты, где у каждого торрента рассчитан балл `score`.  
   - В Сценарии А твоя главная рекомендация (ТОП-1) ОБЯЗАНА быть раздачей с самым высоким `score` в списке! Не переопределяй этот балл своими догадками. Если у VCB-Studio балл 165, а у Trix 115, ты ОБЯЗАН рекомендовать VCB-Studio (№3) как лучшую!  
  
2. РАСПОЗНАВАНИЕ VCB-STUDIO (АБСОЛЮТНЫЙ КОРОЛЬ КАЧЕСТВА):  
   - Релизы от VCB-Studio часто содержат в начале названия китайские иероглифы (например: `[动漫国字幕组&恶魔岛字幕组&豌豆字幕组&VCB-Studio]`). Это оригинальные и элитные рипы от VCB-Studio! Всегда распознавай их по подстроке 'VCB-Studio' в имени.  
   - Всегда рекомендуй VCB-Studio в качестве ТОП-1 выбора для готовых сериалов, ДАЖЕ ЕСЛИ их пак весит очень много. Вес пака больше не преграда, так как пользователь будет скачивать из него серии поштучно с помощью твоего гида!  
  
3. ОТВЕРГАЙ СВЕРХТЯЖЕЛЫЕ REMUX-Ы (60-120+ ГБ) как лучший выбор:  
   - Несжатые образы дисков (Remux) весят слишком много и тащат в себе все визуальные дефекты оригинальных Blu-ray дисков (цифровой шум, мерцание контуров, ужасный цветовой бандинг в темных сценах). BDRip от VCB-Studio ВСЕГДА чище и лучше, чем Remux!  
  
4. ЖЕСТКИЙ ПРИОРИТЕТ БЕЗ ЦЕНЗУРЫ (UNCENSORED / 🔞):  
   - Для таких тайтлов (этти, экшен, комедии вроде Prison School или Kill Blue) версия БЕЗ ЦЕНЗУРЫ (Uncensored / Uncut / NC / OVA / OAD) имеет абсолютное, решающее значение. Версии с цензурой (TV / Censored) отбрасывай в самый конец!  
  
5. ИНТЕГРАЦИЯ АКТИВНЫХ HTML-КНОПОК СКАЧИВАНИЯ:  
   - Для каждого торрента, который ты рекомендуешь (в качестве ТОП-1 или в пошаговом наборе), ты ОБЯЗАН сгенерировать рядом активные, кликабельные HTML-ссылки на Magnet и Torrent, используя поля `magnet_link` и `torrent_link` из переданного тебе JSON!  
   - Форматируй ссылки строго в таком виде:  
     `<a href="ССЫЛКА_ИЗ_JSON" style="color: #06B6D4; font-weight: bold; text-decoration: none; margin-left: 10px;">[Magnet]</a> <a href="ССЫЛКА_ИЗ_JSON" style="color: #8B5CF6; font-weight: bold; text-decoration: none; margin-left: 5px;">[Torrent]</a>`  
  
6. ИНТЕЛЛЕКТУАЛЬНЫЙ "ПОШАГОВЫЙ НАБОР СЕРИЙ" (ДВА СЦЕНАРИЯ):  
  
   Сценарий А: Если сериал закончен и в списке есть качественные полные паки (как Атака Титанов):  
   - Рекомендуй в качестве ТОП-1 элитный пак с максимальным `score` (в приоритете VCB-Studio). Сгенерируй для него HTML-кнопки Magnet и Torrent!  
   - Построй "Умный пошаговый гид". Напиши пользователю:   
     "Рекомендуем скачать Пак №X [Имя], так как у него эталонная картинка без дефектов диска. Не качайте весь пак сразу — скачивайте его пошагово, выбирая галочками в торрент-клиенте отдельные файлы серий по очереди:  
      • Серия 1 (внутри папки Season 1, файл [имя_файла.mkv]) <a href="MAGNET_ИЗ_JSON" style="color: #06B6D4; font-weight: bold; text-decoration: none; margin-left: 10px;">[Magnet]</a> <a href="TORRENT_ИЗ_JSON" style="color: #8B5CF6; font-weight: bold; text-decoration: none; margin-left: 5px;">[Torrent]</a>  
      • Серия 2 (внутри папки Season 1, файл [имя_файла.mkv])..."  
  
   Сценарий Б: Если сериал сейчас выходит (онгоинг, как Kill Blue) и полных BATCH-паков нет:  
   - В этом случае построй "Пошаговый набор серий". Обязательно найди в списке ВСЕ уникальные номера эпизодов (например, Episode 6, Episode 7, Episode 8, Episode 9) и выбери для КАЖДОГО уникального эпизода ровно ОДИН лучший торрент из списка (весом до 1.5 ГБ) с максимальным битрейтом и сидами.  
   - Выведи их в виде красивого нумерованного списка по порядку эпизодов, снабдив КАЖДЫЙ ЭПИЗОД его собственными кнопками [Magnet] и [Torrent] из JSON:  
     • Эпизод 6 -> №X [имя_раздачи] (Размер, Сиды) <a href="MAGNET_ИЗ_JSON" style="color: #06B6D4; font-weight: bold; text-decoration: none; margin-left: 10px;">[Magnet]</a> <a href="TORRENT_ИЗ_JSON" style="color: #8B5CF6; font-weight: bold; text-decoration: none; margin-left: 5px;">[Torrent]</a>  
     • Эпизод 7 -> №Y [имя_раздачи] (Размер, Сиды) <a href="MAGNET_ИЗ_JSON" style="color: #06B6D4; font-weight: bold; text-decoration: none; margin-left: 10px;">[Magnet]</a> <a href="TORRENT_ИЗ_JSON" style="color: #8B5CF6; font-weight: bold; text-decoration: none; margin-left: 5px;">[Torrent]</a>  
  
Вот список раздач для анализа:  
{json_data_results}  
  
Проанализируй этот список и напиши короткий, емкий вердикт на русском языке в строгом соответствии со Сценарием А или Б. Сделай текст оформленным аккуратно с переносами строк. Ограничься объемом в 15-20 строк."""  
                    
                    user_prompt = user_prompt_template.replace("{query}", processed_query).replace("{json_data_results}", json.dumps(short_list, ensure_ascii=False))
                    
                    req_data = json.dumps({
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3
                    }).encode('utf-8')
                    
                    req = urllib.request.Request(
                        "https://api.openai.com/v1/chat/completions",
                        data=req_data,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {openai_key}"
                        }
                    )
                    with urllib.request.urlopen(req, timeout=12) as response:
                        res_json = json.loads(response.read().decode('utf-8'))
                        ai_verdict = res_json['choices'][0]['message']['content'].strip()
                except Exception as e:
                    log_to_file(f"GPT Nyaa analysis failed: {e}")

            return json.dumps({
                "status": "success",
                "query": processed_query,
                "results": expert_results,
                "ai_verdict": ai_verdict
            })
        except Exception as global_e:
            log_to_file(f"Exception in search_nyaa_torrents: {global_e}")
            return json.dumps({"status": "error", "message": f"Произошла непредвиденная ошибка на стороне бэкенда: {global_e}"})

def run_server():
    # IMPORTANT: Bottle's default wsgiref server is single-threaded.
    # The player serves local video through /media; a long video stream can occupy the only request
    # handler and make Watch Together /api/watch/state fail for friends. Use a threaded WSGI server
    # so media streaming, sync polling, assistant API, and UI requests can run at the same time.
    from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
    from socketserver import ThreadingMixIn

    class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True
        allow_reuse_address = True

    try:
        httpd = make_server('0.0.0.0', PORT, app, server_class=ThreadingWSGIServer, handler_class=WSGIRequestHandler)
        log_to_file(f'Threaded local server started on 0.0.0.0:{PORT}')
        httpd.serve_forever()
    except Exception as e:
        log_to_file(f'Threaded server failed, falling back to bottle.run: {e}')
        bottle.run(app, host='0.0.0.0', port=PORT, quiet=True)

if __name__ == '__main__':
    # Symmetrically pre-create keys.json on app launch so the user can easily see and edit it!
    keys_file = get_keys_file()
    if not os.path.exists(keys_file):
        try:
            import json
            with open(keys_file, "w", encoding="utf-8") as f:
                json.dump({"OPENAI_API_KEY": "", "TAVILY_API_KEY": "", "QBIT_URL": "", "QBIT_USERNAME": "", "QBIT_PASSWORD": "", "MOVIE_RAW_PROVIDER": "prowlarr", "PROWLARR_URL": "http://127.0.0.1:9696", "PROWLARR_API_KEY": "", "FLARESOLVERR_PATH": "", "FLARESOLVERR_URL": "http://127.0.0.1:8191", "FLARESOLVERR_AUTOSTART": False}, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    # Start the local web server in a daemon thread so it terminates with the app
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Initialize PyWebView Window and inject the API
    api = PlayerAPI()
    API_INSTANCE = api
    window = webview.create_window(
        title='Minimal Media Player Pro',
        url=f'http://127.0.0.1:{PORT}/',
        js_api=api,
        width=1000,
        height=680,
        min_size=(800, 520),
        background_color='#020204'
    )
    api.window = window
    
    # Launch pywebview window main loop.
    # Explicit storage_path improves WebView2 cookie/session persistence across restarts.
    try:
        webview.start(storage_path=USER_DATA_DIR if USER_DATA_DIR else None)
    except TypeError:
        # Older pywebview builds may not support storage_path; env WEBVIEW2_USER_DATA_FOLDER is already set above.
        webview.start()
