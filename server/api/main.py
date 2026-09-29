import os
import time
import json
import hmac
import base64
import hashlib
import sqlite3
import secrets
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

import requests
from cachetools import TTLCache
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

APP_TOKEN = os.getenv("MODERNPLAYER_SERVER_TOKEN", "").strip()
PROWLARR_URL = os.getenv("PROWLARR_URL", "http://127.0.0.1:9696").rstrip("/")
PROWLARR_API_KEY = os.getenv("PROWLARR_API_KEY", "").strip()
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://127.0.0.1:8191").rstrip("/")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "").strip()
FANART_API_KEY = os.getenv("FANART_API_KEY", "").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS_PER_REQUEST", "1600") or 1600)
DEEPSEEK_TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.35") or 0.35)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
TAVILY_SEARCH_DEPTH = os.getenv("TAVILY_SEARCH_DEPTH", "advanced").strip()
TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "6") or 6)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
TVDB_API_KEY = os.getenv("TVDB_API_KEY", "").strip()
TRAKT_CLIENT_ID = os.getenv("TRAKT_CLIENT_ID", "").strip()
MDBLIST_API_KEY = os.getenv("MDBLIST_API_KEY", "").strip()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
ENABLE_PUBLIC_HEALTH = os.getenv("ENABLE_PUBLIC_HEALTH", "true").lower() in ("1", "true", "yes")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() in ("1", "true", "yes")
JWT_SECRET = os.getenv("JWT_SECRET", "change_this_to_another_long_random_string").strip()
DEV_USERNAME = os.getenv("DEV_USERNAME", "admin").strip().lower()
DEV_PASSWORD = os.getenv("DEV_PASSWORD", "change_me").strip()
ALLOW_PUBLIC_SIGNUP = os.getenv("ALLOW_PUBLIC_SIGNUP", "false").lower() in ("1", "true", "yes")
REQUIRE_EMAIL_VERIFICATION = os.getenv("REQUIRE_EMAIL_VERIFICATION", "true").lower() in ("1", "true", "yes")
REGISTER_RATE_LIMIT_PER_IP_PER_HOUR = int(os.getenv("REGISTER_RATE_LIMIT_PER_IP_PER_HOUR", "5") or 5)
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@modernplayer.local").strip()
DEFAULT_USER_DAILY_AI_LIMIT = int(os.getenv("DEFAULT_USER_DAILY_AI_LIMIT", "50") or 50)
DEFAULT_USER_DAILY_RAW_SEARCH_LIMIT = int(os.getenv("DEFAULT_USER_DAILY_RAW_SEARCH_LIMIT", "100") or 100)
DEV_DAILY_AI_LIMIT = int(os.getenv("DEV_DAILY_AI_LIMIT", "5000") or 5000)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./modernplayer.db")
RAW_CACHE_TTL = int(os.getenv("RAW_CACHE_TTL_SECONDS", "21600") or 21600)
META_CACHE_TTL = int(os.getenv("META_CACHE_TTL_SECONDS", "86400") or 86400)

raw_cache = TTLCache(maxsize=600, ttl=RAW_CACHE_TTL)
meta_cache = TTLCache(maxsize=1500, ttl=META_CACHE_TTL)
CLOUD_WATCH_ROOMS = {}

app = FastAPI(title="ModernPlayer Cloud API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

KEY_LINKS = {
    "oracle_cloud_free_tier": "https://www.oracle.com/cloud/free/",
    "tmdb_api_settings": "https://www.themoviedb.org/settings/api",
    "tmdb_api_docs": "https://developer.themoviedb.org/docs/authentication-application",
    "omdb_api_key": "https://www.omdbapi.com/apikey.aspx",
    "fanart_api_key": "https://fanart.tv/get-an-api-key/",
    "anilist_api_docs_keyless": "https://anilist.gitbook.io/anilist-apiv2-docs/",
    "jikan_api_docs_keyless": "https://docs.api.jikan.moe/",
    "prowlarr": "https://prowlarr.org/",
    "prowlarr_docker_wiki": "https://github.com/Servarr/Wiki/blob/master/prowlarr/installation/docker.md",
    "flaresolverr_github": "https://github.com/FlareSolverr/FlareSolverr",
    "inno_setup_installer": "https://jrsoftware.org/isinfo.php",
}


def db_path():
    if DATABASE_URL.startswith('sqlite:///'):
        return DATABASE_URL.replace('sqlite:///', '', 1)
    return './modernplayer.db'


def db():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    return con


def hash_password(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', (password or '').encode(), salt.encode(), 120_000).hex()
    return f'pbkdf2_sha256${salt}${digest}'


def verify_password(password: str, stored: str):
    try:
        algo, salt, digest = stored.split('$', 2)
        if algo != 'pbkdf2_sha256':
            return False
        candidate = hashlib.pbkdf2_hmac('sha256', (password or '').encode(), salt.encode(), 120_000).hex()
        return hmac.compare_digest(candidate, digest)
    except Exception:
        return False


def b64url(data: bytes):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def b64url_decode(text: str):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def make_token(user: dict):
    payload = {'sub': user['username'], 'email': user.get('email',''), 'role': user.get('role', 'user'), 'iat': int(time.time()), 'exp': int(time.time()) + 60 * 60 * 24 * 30}
    body = b64url(json.dumps(payload, separators=(',', ':')).encode())
    sig = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return body + '.' + b64url(sig)


def parse_token(auth_header: str | None):
    if not auth_header:
        return None
    token = auth_header[7:].strip() if auth_header.lower().startswith('bearer ') else auth_header.strip()
    try:
        body, sig = token.split('.', 1)
        expected = b64url(hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(b64url_decode(body).decode())
        if payload.get('exp', 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def init_db():
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at REAL NOT NULL
    )""")
    cur.execute('PRAGMA table_info(users)')
    cols = {r['name'] for r in cur.fetchall()}
    migrations = {
        'email': "ALTER TABLE users ADD COLUMN email TEXT",
        'email_verified': "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0",
        'banned': "ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0",
        'verify_token': "ALTER TABLE users ADD COLUMN verify_token TEXT",
        'verify_sent_at': "ALTER TABLE users ADD COLUMN verify_sent_at REAL",
        'last_login_at': "ALTER TABLE users ADD COLUMN last_login_at REAL",
    }
    for col, sql in migrations.items():
        if col not in cols:
            cur.execute(sql)
    try:
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) WHERE email IS NOT NULL AND email != ""')
    except Exception:
        pass
    cur.execute("""CREATE TABLE IF NOT EXISTS registration_attempts (
        ip TEXT NOT NULL,
        ts REAL NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS usage_daily (
        username TEXT NOT NULL,
        day TEXT NOT NULL,
        kind TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(username, day, kind)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS assistant_memory (
        username TEXT NOT NULL,
        mem_key TEXT NOT NULL,
        mem_value TEXT NOT NULL,
        updated_at REAL NOT NULL,
        PRIMARY KEY(username, mem_key)
    )""")
    con.commit()
    cur.execute('SELECT username FROM users WHERE username=?', (DEV_USERNAME,))
    if not cur.fetchone() and DEV_PASSWORD and DEV_PASSWORD != 'change_me':
        cur.execute('INSERT INTO users(username,password_hash,role,created_at,email_verified,banned) VALUES(?,?,?,?,1,0)', (DEV_USERNAME, hash_password(DEV_PASSWORD), 'dev', time.time()))
        con.commit()
    con.close()


def current_user(authorization: Optional[str] = None, x_modernplayer_token: Optional[str] = None):
    if APP_TOKEN and x_modernplayer_token == APP_TOKEN:
        return {'username': 'server-token', 'email': '', 'role': 'dev'}
    payload = parse_token(authorization)
    if not payload:
        if AUTH_ENABLED:
            raise HTTPException(status_code=401, detail='login required')
        return {'username': 'anonymous', 'email': '', 'role': 'user'}
    username = str(payload.get('sub') or '').lower()
    con = db(); cur = con.cursor()
    cur.execute('SELECT username,email,role,banned,email_verified FROM users WHERE username=?', (username,))
    row = cur.fetchone(); con.close()
    if not row:
        raise HTTPException(status_code=401, detail='user no longer exists')
    if int(row['banned'] or 0):
        raise HTTPException(status_code=403, detail='account banned')
    if REQUIRE_EMAIL_VERIFICATION and int(row['email_verified'] or 0) != 1 and row['role'] != 'dev':
        raise HTTPException(status_code=403, detail='email not verified')
    return {'username': row['username'], 'email': row['email'], 'role': row['role']}


def usage_limit_for(user, kind):
    if user.get('role') == 'dev':
        return DEV_DAILY_AI_LIMIT if kind == 'ai' else 10000
    return DEFAULT_USER_DAILY_AI_LIMIT if kind == 'ai' else DEFAULT_USER_DAILY_RAW_SEARCH_LIMIT


def increment_usage(user, kind):
    name = user.get('username') or 'anonymous'
    day = time.strftime('%Y-%m-%d')
    limit = usage_limit_for(user, kind)
    con = db(); cur = con.cursor()
    cur.execute('INSERT OR IGNORE INTO usage_daily(username,day,kind,count) VALUES(?,?,?,0)', (name, day, kind))
    cur.execute('SELECT count FROM usage_daily WHERE username=? AND day=? AND kind=?', (name, day, kind))
    count = int(cur.fetchone()['count'])
    if count >= limit:
        con.close(); raise HTTPException(status_code=429, detail=f'daily {kind} limit reached ({limit})')
    cur.execute('UPDATE usage_daily SET count=count+1 WHERE username=? AND day=? AND kind=?', (name, day, kind))
    con.commit(); con.close()
    return {'count': count + 1, 'limit': limit}


def client_ip(request: Request):
    fwd = request.headers.get('x-forwarded-for') or ''
    if fwd:
        return fwd.split(',')[0].strip()[:80]
    return (request.client.host if request.client else 'unknown')[:80]


def check_registration_rate_limit(ip: str):
    cutoff = time.time() - 3600
    con = db(); cur = con.cursor()
    cur.execute('DELETE FROM registration_attempts WHERE ts < ?', (cutoff,))
    cur.execute('SELECT COUNT(*) AS c FROM registration_attempts WHERE ip=? AND ts>=?', (ip, cutoff))
    count = int(cur.fetchone()['c'])
    if count >= REGISTER_RATE_LIMIT_PER_IP_PER_HOUR:
        con.commit(); con.close()
        raise HTTPException(status_code=429, detail='too many registration attempts from this IP')
    cur.execute('INSERT INTO registration_attempts(ip,ts) VALUES(?,?)', (ip, time.time()))
    con.commit(); con.close()


def public_base_url(request: Request | None = None):
    base = os.getenv('PUBLIC_BASE_URL', '').strip().rstrip('/')
    if base:
        return base
    if request:
        return str(request.base_url).rstrip('/')
    return 'http://127.0.0.1:8000'


def send_verification_email(email: str, username: str, token: str, request: Request | None = None):
    link = f"{public_base_url(request)}/api/auth/verify-email?token={token}"
    if not SMTP_HOST:
        return {'sent': False, 'reason': 'smtp_not_configured', 'verification_url': link}
    msg = EmailMessage()
    msg['Subject'] = 'Verify your ModernPlayer account'
    msg['From'] = SMTP_FROM
    msg['To'] = email
    msg.set_content(f"Hello {username},\n\nVerify your ModernPlayer account:\n{link}\n\nIf you did not create this account, ignore this email.\n")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            smtp.starttls()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return {'sent': True}
    except Exception as e:
        return {'sent': False, 'reason': str(e), 'verification_url': link}


def require_dev(user):
    if not user or user.get('role') != 'dev':
        raise HTTPException(status_code=403, detail='dev role required')


init_db()


def require_token(x_modernplayer_token: Optional[str] = None):
    if APP_TOKEN and x_modernplayer_token != APP_TOKEN:
        raise HTTPException(status_code=401, detail="Bad or missing X-ModernPlayer-Token")


def prowlarr_headers():
    return {"X-Api-Key": PROWLARR_API_KEY, "Accept": "application/json"}


def canonical_movie_queries(q: str):
    text = (q or "").strip()
    low = text.lower()
    out = []
    def add(x):
        x = " ".join(str(x or "").split())
        if x and x.lower() not in [v.lower() for v in out]:
            out.append(x)
    if "dictator" in low or "диктатор" in low:
        for x in ["The Dictator 2012", "The Dictator 2012 1080p", "The Dictator 2012 BluRay", "tt1645170"]:
            add(x)
        return out
    if "eyes wide shut" in low or "с широко закрытыми" in low:
        for x in ["Eyes Wide Shut 1999", "Eyes Wide Shut 1999 1080p", "Eyes Wide Shut 1999 BluRay", "tt0120663"]:
            add(x)
        return out
    if "zodiac" in low or "зодиак" in low:
        for x in ["Zodiac 2007", "Zodiac 2007 1080p", "Zodiac 2007 BluRay", "tt0443706"]:
            add(x)
        return out
    add(text)
    add(f"{text} 1080p")
    add(f"{text} BluRay")
    return out[:4]


def score_release(item):
    title = (item.get("title") or item.get("releaseTitle") or "").lower()
    seeders = int(item.get("seeders") or item.get("seedersCount") or 0)
    size = float(item.get("size") or 0) / (1024 ** 3)
    score = min(seeders, 100)
    if any(x in title for x in ["2160", "4k", "uhd"]): score += 1200
    elif "1080" in title: score += 800
    elif "720" in title: score += 160
    if "remux" in title: score += 420
    if "bluray" in title or "blu-ray" in title: score += 260
    if "web-dl" in title: score += 150
    if any(x in title for x in ["x265", "hevc", "h.265"]): score += 60
    if any(x in title for x in ["yify", "yts"]): score -= 220
    if any(x in title for x in [" cam", "telesync", "hdcam", "camrip"]): score -= 1500
    if size and size < 1.0 and "1080" in title: score -= 120
    return score


@app.get("/health")
def health():
    return {
        "ok": True,
        "version": "0.1.0",
        "time": time.time(),
        "configured": {
            "prowlarr": bool(PROWLARR_URL and PROWLARR_API_KEY),
            "flaresolverr_url": FLARESOLVERR_URL,
            "tmdb": bool(TMDB_API_KEY),
            "omdb": bool(OMDB_API_KEY),
            "fanart": bool(FANART_API_KEY),
            "deepseek": bool(DEEPSEEK_API_KEY),
            "deepseek_model": DEEPSEEK_MODEL,
            "openai": bool(OPENAI_API_KEY),
            "tavily": bool(TAVILY_API_KEY),
            "anthropic": bool(ANTHROPIC_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "groq": bool(GROQ_API_KEY),
            "openrouter": bool(OPENROUTER_API_KEY),
            "tvdb": bool(TVDB_API_KEY),
            "trakt": bool(TRAKT_CLIENT_ID),
            "mdblist": bool(MDBLIST_API_KEY),
            "youtube": bool(YOUTUBE_API_KEY),
            "token_required": bool(APP_TOKEN),
            "auth_enabled": AUTH_ENABLED,
            "public_signup": ALLOW_PUBLIC_SIGNUP,
            "default_user_daily_ai_limit": DEFAULT_USER_DAILY_AI_LIMIT,
            "dev_daily_ai_limit": DEV_DAILY_AI_LIMIT,
        },
    }


@app.get("/api/key-links")
def key_links(x_modernplayer_token: Optional[str] = Header(default=None)):
    # Allowed without token if server admin wants to share setup links; no secrets returned.
    if not ENABLE_PUBLIC_HEALTH:
        require_token(x_modernplayer_token)
    return {"status": "success", "links": KEY_LINKS}


@app.get("/api/config-template")
def config_template(x_modernplayer_token: Optional[str] = Header(default=None)):
    if not ENABLE_PUBLIC_HEALTH:
        require_token(x_modernplayer_token)
    return {
        "status": "success",
        "app_keys_json_patch": {
            "MOVIE_RAW_PROVIDER": "cloud",
            "MODERNPLAYER_API_URL": "https://YOUR_DOMAIN_OR_IP",
            "MODERNPLAYER_API_TOKEN": "PASTE_MODERNPLAYER_SERVER_TOKEN",
            "DUB_MODE": "browser_assisted",
            "MERGER_SYNC_MODE": "multipoint",
            "MERGER_USE_DEMUCS": False,
        },
        "server_env_required": {
            "MODERNPLAYER_SERVER_TOKEN": "required if private",
            "PROWLARR_URL": "http://127.0.0.1:9696",
            "PROWLARR_API_KEY": "from Prowlarr Settings > General",
        },
        "server_env_optional": ["TMDB_API_KEY", "OMDB_API_KEY", "FANART_API_KEY"],
    }


@app.post("/api/auth/register")
def auth_register(payload: dict, request: Request):
    if not ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(status_code=403, detail='public signup disabled')
    ip = client_ip(request)
    check_registration_rate_limit(ip)
    username = str(payload.get('username') or '').strip().lower()
    email = str(payload.get('email') or '').strip().lower()
    password = str(payload.get('password') or '')
    if len(username) < 3 or len(username) > 32 or not all(ch.isalnum() or ch in ('_', '-', '.') for ch in username):
        raise HTTPException(status_code=400, detail='username must be 3-32 chars and contain only letters numbers _ - .')
    if '@' not in email or '.' not in email or len(email) > 160:
        raise HTTPException(status_code=400, detail='valid email required')
    if len(password) < 8:
        raise HTTPException(status_code=400, detail='password >=8 required')
    token = secrets.token_urlsafe(32)
    email_verified = 0 if REQUIRE_EMAIL_VERIFICATION else 1
    con = db(); cur = con.cursor()
    try:
        cur.execute('INSERT INTO users(username,email,password_hash,role,created_at,email_verified,banned,verify_token,verify_sent_at) VALUES(?,?,?,?,?,?,?,?,?)',
                    (username, email, hash_password(password), 'user', time.time(), email_verified, 0, token if REQUIRE_EMAIL_VERIFICATION else None, time.time()))
        con.commit()
    except sqlite3.IntegrityError:
        con.close(); raise HTTPException(status_code=409, detail='username or email already exists')
    con.close()
    mail = send_verification_email(email, username, token, request) if REQUIRE_EMAIL_VERIFICATION else {'sent': False}
    return {'status': 'success', 'username': username, 'email': email, 'email_verification_required': REQUIRE_EMAIL_VERIFICATION, 'email_sent': bool(mail.get('sent')), 'verification_url': mail.get('verification_url') if not mail.get('sent') else None, 'mail_status': mail.get('reason') if not mail.get('sent') else 'sent'}


@app.post("/api/auth/login")
def auth_login(payload: dict):
    username_or_email = str(payload.get('username') or payload.get('email') or '').strip().lower()
    password = str(payload.get('password') or '')
    con = db(); cur = con.cursor()
    cur.execute('SELECT * FROM users WHERE username=? OR email=?', (username_or_email, username_or_email))
    row = cur.fetchone()
    if not row or not verify_password(password, row['password_hash']):
        con.close(); raise HTTPException(status_code=401, detail='bad username/password')
    if int(row['banned'] or 0):
        con.close(); raise HTTPException(status_code=403, detail='account banned')
    if REQUIRE_EMAIL_VERIFICATION and int(row['email_verified'] or 0) != 1 and row['role'] != 'dev':
        con.close(); raise HTTPException(status_code=403, detail='email not verified')
    cur.execute('UPDATE users SET last_login_at=? WHERE id=?', (time.time(), row['id']))
    con.commit(); con.close()
    user = {'username': row['username'], 'email': row['email'], 'role': row['role']}
    return {'status': 'success', 'token': make_token(user), 'user': user}


@app.get("/api/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token)
    day = time.strftime('%Y-%m-%d')
    con = db(); cur = con.cursor()
    cur.execute('SELECT kind,count FROM usage_daily WHERE username=? AND day=?', (user['username'], day))
    usage = {r['kind']: r['count'] for r in cur.fetchall()}
    con.close()
    return {'status': 'success', 'user': user, 'usage': usage, 'limits': {'ai': usage_limit_for(user, 'ai'), 'raw_search': usage_limit_for(user, 'raw_search')}}


@app.get("/api/auth/verify-email")
def verify_email(token: str = Query(...)):
    con = db(); cur = con.cursor()
    cur.execute('SELECT id,username,email FROM users WHERE verify_token=?', (token,))
    row = cur.fetchone()
    if not row:
        con.close(); raise HTTPException(status_code=404, detail='verification token not found')
    cur.execute('UPDATE users SET email_verified=1, verify_token=NULL WHERE id=?', (row['id'],))
    con.commit(); con.close()
    return {'status': 'success', 'message': 'email verified', 'username': row['username'], 'email': row['email']}


@app.post("/api/auth/resend-verification")
def resend_verification(payload: dict, request: Request):
    email = str(payload.get('email') or '').strip().lower()
    con = db(); cur = con.cursor()
    cur.execute('SELECT * FROM users WHERE email=?', (email,))
    row = cur.fetchone()
    if not row:
        con.close(); raise HTTPException(status_code=404, detail='email not found')
    if int(row['email_verified'] or 0) == 1:
        con.close(); return {'status': 'success', 'message': 'already verified'}
    token = row['verify_token'] or secrets.token_urlsafe(32)
    cur.execute('UPDATE users SET verify_token=?, verify_sent_at=? WHERE id=?', (token, time.time(), row['id']))
    con.commit(); con.close()
    mail = send_verification_email(email, row['username'], token, request)
    return {'status': 'success', 'email_sent': bool(mail.get('sent')), 'verification_url': mail.get('verification_url') if not mail.get('sent') else None, 'mail_status': mail.get('reason') if not mail.get('sent') else 'sent'}


@app.get("/api/admin/users")
def admin_users(authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token); require_dev(user)
    con = db(); cur = con.cursor()
    cur.execute('SELECT id,username,email,role,email_verified,banned,created_at,last_login_at FROM users ORDER BY id DESC LIMIT 500')
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return {'status': 'success', 'users': rows}


@app.post("/api/admin/users/{username}/ban")
def admin_ban_user(username: str, payload: dict = {}, authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token); require_dev(user)
    banned = 1 if payload.get('banned', True) else 0
    con = db(); cur = con.cursor()
    cur.execute('UPDATE users SET banned=? WHERE username=?', (banned, username.lower()))
    con.commit(); con.close()
    return {'status': 'success', 'username': username.lower(), 'banned': bool(banned)}


@app.post("/api/admin/users/{username}/verify")
def admin_verify_user(username: str, authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token); require_dev(user)
    con = db(); cur = con.cursor()
    cur.execute('UPDATE users SET email_verified=1, verify_token=NULL WHERE username=?', (username.lower(),))
    con.commit(); con.close()
    return {'status': 'success', 'username': username.lower(), 'email_verified': True}


@app.post("/api/admin/users/{username}/role")
def admin_role_user(username: str, payload: dict, authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token); require_dev(user)
    role = str(payload.get('role') or 'user').lower()
    if role not in ('user', 'dev'):
        raise HTTPException(status_code=400, detail='role must be user or dev')
    con = db(); cur = con.cursor()
    cur.execute('UPDATE users SET role=? WHERE username=?', (role, username.lower()))
    con.commit(); con.close()
    return {'status': 'success', 'username': username.lower(), 'role': role}


@app.get("/api/assistant/memory")
def get_memory(authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token)
    con = db(); cur = con.cursor()
    cur.execute('SELECT mem_key,mem_value,updated_at FROM assistant_memory WHERE username=? ORDER BY mem_key', (user['username'],))
    data = {r['mem_key']: {'value': json.loads(r['mem_value']), 'updated_at': r['updated_at']} for r in cur.fetchall()}
    con.close()
    return {'status': 'success', 'memory': data}


@app.post("/api/assistant/memory")
def set_memory(payload: dict, authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token)
    key = str(payload.get('key') or '').strip()[:80]
    value = payload.get('value')
    if not key:
        raise HTTPException(status_code=400, detail='memory key required')
    con = db(); cur = con.cursor()
    cur.execute('INSERT OR REPLACE INTO assistant_memory(username,mem_key,mem_value,updated_at) VALUES(?,?,?,?)', (user['username'], key, json.dumps(value, ensure_ascii=False), time.time()))
    con.commit(); con.close()
    return {'status': 'success'}


def assistant_needs_web(message: str):
    t = (message or '').lower()
    needles = [
        'today', 'now', 'current', 'latest', 'recent', '2025', '2026', 'this year', 'news', 'new ',
        'сегодня', 'сейчас', 'актуаль', 'последн', 'новин', 'новый', 'новые', 'в этом году', '2025', '2026',
        'самый интересный', 'лучший фильм', 'что вышло', 'что посмотреть'
    ]
    return any(x in t for x in needles)


def tavily_search(query: str):
    if not TAVILY_API_KEY:
        return {'enabled': False, 'results': [], 'answer': '', 'error': 'TAVILY_API_KEY is not configured'}
    try:
        payload = {
            'api_key': TAVILY_API_KEY,
            'query': query,
            'search_depth': TAVILY_SEARCH_DEPTH or 'advanced',
            'max_results': max(1, min(10, TAVILY_MAX_RESULTS)),
            'include_answer': True,
            'include_raw_content': False,
        }
        r = requests.post('https://api.tavily.com/search', json=payload, timeout=18)
        r.raise_for_status()
        data = r.json()
        return {'enabled': True, 'answer': data.get('answer') or '', 'results': data.get('results') or [], 'error': ''}
    except Exception as e:
        return {'enabled': True, 'answer': '', 'results': [], 'error': str(e)}


def get_user_memory_text(username: str):
    try:
        con = db(); cur = con.cursor()
        cur.execute('SELECT mem_key, mem_value FROM assistant_memory WHERE username=? ORDER BY mem_key LIMIT 30', (username,))
        rows = cur.fetchall(); con.close()
        if not rows:
            return ''
        lines = []
        for r in rows:
            try:
                val = json.loads(r['mem_value'])
            except Exception:
                val = r['mem_value']
            lines.append(f"- {r['mem_key']}: {val}")
        return '\n'.join(lines)
    except Exception:
        return ''


def call_openai_compatible(base_url: str, api_key: str, model: str, messages: list, max_tokens: int, temperature: float):
    url = base_url.rstrip('/') + '/v1/chat/completions'
    r = requests.post(url, headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}, json={
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }, timeout=45)
    r.raise_for_status()
    data = r.json()
    return data['choices'][0]['message']['content'].strip()


@app.post("/api/assistant/chat")
def assistant_chat(payload: dict, authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token)
    usage = increment_usage(user, 'ai')
    msg = str(payload.get('message') or '').strip()
    context = payload.get('context') or {}
    if not msg:
        raise HTTPException(status_code=400, detail='message required')

    web = None
    if assistant_needs_web(msg):
        web = tavily_search(msg)

    memory_text = get_user_memory_text(user.get('username') or 'anonymous')
    web_text = ''
    if web:
        if web.get('answer'):
            web_text += 'Tavily answer:\n' + web.get('answer','') + '\n\n'
        if web.get('results'):
            web_text += 'Tavily search results:\n'
            for i, r in enumerate(web.get('results', [])[:TAVILY_MAX_RESULTS], 1):
                web_text += f"{i}. {r.get('title','')}\nURL: {r.get('url','')}\nSnippet: {r.get('content','')}\n\n"
        if web.get('error'):
            web_text += 'Tavily error: ' + web.get('error') + '\n'

    system = (
        "You are :3 Assistant for ModernPlayer, a desktop anime/movie media player. "
        "You DO have internet access when server provides Tavily search results. "
        "Never claim that your knowledge cutoff prevents answering if Tavily results are present. "
        "Use current web results for recent questions. Be concise, practical, and direct. "
        "If web results are absent and the user asks for current info, say the server search returned no results, not that you are inherently offline. "
        "Answer in the user's language."
    )
    if memory_text:
        system += "\n\nUser memory/preferences:\n" + memory_text
    if web_text:
        system += "\n\nCurrent internet context from Tavily:\n" + web_text

    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': msg + ("\n\nApp context:\n" + json.dumps(context, ensure_ascii=False)[:2000] if context else '')}
    ]

    provider = 'none'
    try:
        if DEEPSEEK_API_KEY:
            provider = 'deepseek'
            answer = call_openai_compatible(DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, messages, DEEPSEEK_MAX_TOKENS, DEEPSEEK_TEMPERATURE)
        elif OPENAI_API_KEY:
            provider = 'openai'
            answer = call_openai_compatible('https://api.openai.com', OPENAI_API_KEY, os.getenv('OPENAI_MODEL','gpt-4o-mini'), messages, int(os.getenv('OPENAI_MAX_TOKENS_PER_REQUEST','1200') or 1200), 0.35)
        else:
            answer = 'Cloud assistant has no LLM key configured. Add DEEPSEEK_API_KEY or OPENAI_API_KEY to server .env.'
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'{provider} assistant call failed: {e}')

    return {
        'status': 'success',
        'answer': answer,
        'provider': provider,
        'model': DEEPSEEK_MODEL if provider == 'deepseek' else os.getenv('OPENAI_MODEL','gpt-4o-mini'),
        'web_used': bool(web and (web.get('results') or web.get('answer'))),
        'web_error': web.get('error') if web else '',
        'usage': usage,
        'user': user,
    }


@app.get("/api/raw/movie")
def raw_movie(q: str = Query(...), authorization: Optional[str] = Header(default=None), x_modernplayer_token: Optional[str] = Header(default=None)):
    user = current_user(authorization, x_modernplayer_token)
    increment_usage(user, 'raw_search')
    if not PROWLARR_API_KEY:
        raise HTTPException(status_code=500, detail="Prowlarr is not configured on server")
    key = "movie:" + q.strip().lower()
    if key in raw_cache:
        return raw_cache[key]
    all_results = []
    errors = []
    cats = [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060, 2070]
    for query in canonical_movie_queries(q):
        for mode in ("movie", "search"):
            try:
                params = [("query", query), ("type", mode), ("limit", "100")]
                for c in cats:
                    params.append(("categories", str(c)))
                r = requests.get(f"{PROWLARR_URL}/api/v1/search", params=params, headers=prowlarr_headers(), timeout=35)
                r.raise_for_status()
                data = r.json()
                for item in data if isinstance(data, list) else []:
                    title = item.get("title") or item.get("releaseTitle") or ""
                    if not title:
                        continue
                    size = item.get("size") or 0
                    all_results.append({
                        "title": title,
                        "indexer": item.get("indexer") or item.get("indexerName") or "",
                        "seeders": item.get("seeders") or item.get("seedersCount") or 0,
                        "size": size,
                        "size_gb": round(float(size or 0) / (1024 ** 3), 2),
                        "downloadUrl": item.get("downloadUrl") or "",
                        "magnetUrl": item.get("magnetUrl") or "",
                        "infoUrl": item.get("infoUrl") or item.get("guid") or "",
                        "score": score_release(item),
                        "matched_query": query,
                    })
            except Exception as e:
                errors.append(f"{query} [{mode}]: {e}")
    seen = set(); dedup = []
    for r in all_results:
        sk = (r["title"].lower(), r["indexer"].lower(), r["size"])
        if sk not in seen:
            seen.add(sk); dedup.append(r)
    dedup.sort(key=lambda x: x.get("score", 0), reverse=True)
    out = {"status": "success", "provider": "cloud_prowlarr", "query": q, "results": dedup[:50], "errors": errors[-8:]}
    raw_cache[key] = out
    return out


@app.get("/api/meta/movie")
def meta_movie(q: str = Query(...), year: Optional[int] = None, x_modernplayer_token: Optional[str] = Header(default=None)):
    require_token(x_modernplayer_token)
    key = f"tmdb:{q}:{year or ''}".lower()
    if key in meta_cache:
        return meta_cache[key]
    if not TMDB_API_KEY:
        return {"status": "not_configured", "message": "TMDB_API_KEY is not configured on server", "results": []}
    params = {"api_key": TMDB_API_KEY, "query": q}
    if year:
        params["year"] = year
    r = requests.get("https://api.themoviedb.org/3/search/movie", params=params, timeout=15)
    r.raise_for_status()
    out = {"status": "success", "provider": "tmdb", "query": q, "results": r.json().get("results", [])}
    meta_cache[key] = out
    return out


@app.get("/api/franchise/{slug}")
def franchise(slug: str):
    safe = "".join(ch for ch in slug.lower() if ch.isalnum() or ch in ("-", "_"))[:80]
    path = Path(__file__).parent / "franchise_guides" / f"{safe}.json"
    if not path.exists():
        return {"status": "missing", "slug": safe, "guide": None}
    return {"status": "success", "slug": safe, "guide": json.loads(path.read_text(encoding="utf-8"))}
