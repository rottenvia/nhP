# ModernPlayer Cloud API — Amazon/Ubuntu deploy

## Links for keys

- Oracle Free Tier: https://www.oracle.com/cloud/free/
- TMDB key: https://www.themoviedb.org/settings/api
- TMDB docs: https://developer.themoviedb.org/docs/authentication-application
- OMDb key: https://www.omdbapi.com/apikey.aspx
- Fanart key: https://fanart.tv/get-an-api-key/
- AniList docs, no key: https://anilist.gitbook.io/anilist-apiv2-docs/
- Jikan docs, no key: https://docs.api.jikan.moe/
- Prowlarr: https://prowlarr.org/
- FlareSolverr: https://github.com/FlareSolverr/FlareSolverr

## Upload with WinSCP

Upload this `server/` folder to:

```text
/home/ubuntu/modernplayer-server
```

Final structure:

```text
/home/ubuntu/modernplayer-server/docker-compose.yml
/home/ubuntu/modernplayer-server/api/main.py
/home/ubuntu/modernplayer-server/api/.env.example
```

## Install packages

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg git unzip nano nginx python3 python3-venv python3-pip ufw
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```

Reconnect SSH.

## Start Prowlarr + FlareSolverr

```bash
cd ~/modernplayer-server
docker compose up -d
```

Use SSH tunnel from Windows:

```cmd
ssh -i "C:\path\oracle-or-amazon-key.pem" -L 9696:127.0.0.1:9696 -L 8191:127.0.0.1:8191 ubuntu@SERVER_IP
```

Open:

```text
http://127.0.0.1:9696
```

Set Prowlarr auth, add indexers, copy API key from Settings > General.

In Prowlarr add FlareSolverr proxy URL:

```text
http://flaresolverr:8191
```

## Configure API .env

```bash
cd ~/modernplayer-server/api
cp .env.example .env
nano .env
```

Set:

```env
MODERNPLAYER_SERVER_TOKEN=<openssl rand -hex 32>
PROWLARR_API_KEY=<Prowlarr API key>
TMDB_API_KEY=<optional>
OMDB_API_KEY=<optional>
FANART_API_KEY=<optional>
```

Generate token:

```bash
openssl rand -hex 32
```

## Install Python API

```bash
cd ~/modernplayer-server/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Test in another SSH:

```bash
curl http://127.0.0.1:8000/health
```

## systemd service

```bash
sudo nano /etc/systemd/system/modernplayer-api.service
```

Paste:

```ini
[Unit]
Description=ModernPlayer API
After=network.target docker.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/modernplayer-server/api
Environment="PATH=/home/ubuntu/modernplayer-server/api/.venv/bin"
ExecStart=/home/ubuntu/modernplayer-server/api/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable modernplayer-api
sudo systemctl start modernplayer-api
sudo systemctl status modernplayer-api
```

Logs:

```bash
journalctl -u modernplayer-api -f
```

## Nginx

```bash
sudo cp ~/modernplayer-server/nginx/modernplayer-api.conf /etc/nginx/sites-available/modernplayer-api
sudo ln -s /etc/nginx/sites-available/modernplayer-api /etc/nginx/sites-enabled/modernplayer-api
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://SERVER_IP/health
http://SERVER_IP/api/key-links
http://SERVER_IP/api/config-template
```

## App keys.json cloud mode

```json
{
  "MOVIE_RAW_PROVIDER": "cloud",
  "MODERNPLAYER_API_URL": "http://SERVER_IP",
  "MODERNPLAYER_API_TOKEN": "PASTE_MODERNPLAYER_SERVER_TOKEN",
  "DUB_MODE": "browser_assisted",
  "MERGER_SYNC_MODE": "multipoint",
  "MERGER_USE_DEMUCS": false
}
```

App support for `MOVIE_RAW_PROVIDER=cloud` must be enabled in app.py after server deploy.

---

# New: accounts, dev/user roles, Assistant memory, and server-side keys

The server now supports a basic auth/role scaffold. It is intentionally simple and SQLite-based for MVP.

## Important `.env` fields

```env
AUTH_ENABLED=true
JWT_SECRET=<openssl rand -hex 32>
DEV_USERNAME=admin
DEV_PASSWORD=<your strong password>
ALLOW_PUBLIC_SIGNUP=false

DEFAULT_USER_DAILY_AI_LIMIT=50
DEFAULT_USER_DAILY_RAW_SEARCH_LIMIT=100
DEV_DAILY_AI_LIMIT=5000

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_DAILY_BUDGET_USD=2.00
OPENAI_MAX_REQUESTS_PER_USER_PER_DAY=50
OPENAI_MAX_TOKENS_PER_REQUEST=1200

TAVILY_API_KEY=
TAVILY_MAX_REQUESTS_PER_USER_PER_DAY=30

TMDB_API_KEY=
OMDB_API_KEY=
FANART_API_KEY=
TVDB_API_KEY=
TRAKT_CLIENT_ID=
TRAKT_CLIENT_SECRET=
MDBLIST_API_KEY=
YOUTUBE_API_KEY=

DATABASE_URL=sqlite:///./modernplayer.db
```

## Dev account

On server startup, if `DEV_USERNAME` and `DEV_PASSWORD` are set and the user does not exist yet, the server creates a dev user automatically.

Example:

```env
AUTH_ENABLED=true
DEV_USERNAME=marsel
DEV_PASSWORD=very_long_password_here
```

Restart:

```bash
sudo systemctl restart modernplayer-api
```

Login test:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"marsel","password":"very_long_password_here"}'
```

It returns:

```json
{
  "status": "success",
  "token": "...",
  "user": {"username":"marsel","role":"dev"}
}
```

Use token:

```bash
curl http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## User registration

Default:

```env
ALLOW_PUBLIC_SIGNUP=false
```

That means random users cannot create accounts. Later you can enable it:

```env
ALLOW_PUBLIC_SIGNUP=true
```

Register endpoint:

```bash
curl -X POST http://SERVER/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"friend","password":"strongpassword123"}'
```

## Assistant memory

Per-user memory endpoints:

```bash
GET  /api/assistant/memory
POST /api/assistant/memory
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/assistant/memory \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key":"preferred_quality","value":"1080p x265, avoid huge remux"}'
```

Read:

```bash
curl http://127.0.0.1:8000/api/assistant/memory \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Assistant endpoint

MVP endpoint exists:

```bash
POST /api/assistant/chat
```

It currently checks auth and daily limits, but OpenAI/Tavily full wiring is the next implementation step.

## Daily limits

Normal user:

```env
DEFAULT_USER_DAILY_AI_LIMIT=50
DEFAULT_USER_DAILY_RAW_SEARCH_LIMIT=100
```

Dev:

```env
DEV_DAILY_AI_LIMIT=5000
```

The raw movie endpoint now consumes `raw_search` usage. Assistant endpoint consumes `ai` usage.

## Recommended production defaults

For private beta:

```env
AUTH_ENABLED=true
ALLOW_PUBLIC_SIGNUP=false
DEFAULT_USER_DAILY_AI_LIMIT=30
DEFAULT_USER_DAILY_RAW_SEARCH_LIMIT=80
OPENAI_DAILY_BUDGET_USD=2.00
```

Give accounts manually by temporarily enabling signup, registering users, then disabling signup again, or later add an admin endpoint.

---

# Email verification, anti-spam signup, ban/admin controls

New auth features added:

- unique username
- unique email
- email verification token
- SMTP email sending
- registration rate limit per IP
- banned users cannot login or use existing tokens
- admin/dev endpoints to list users, ban/unban, verify email, change role

## .env fields

```env
AUTH_ENABLED=true
ALLOW_PUBLIC_SIGNUP=false
REQUIRE_EMAIL_VERIFICATION=true
REGISTER_RATE_LIMIT_PER_IP_PER_HOUR=5

SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
```

If `SMTP_HOST` is empty, `/api/auth/register` returns `verification_url` in JSON. This is useful for testing but not for production.

## Register user

Temporarily enable public signup or later use invite system:

```env
ALLOW_PUBLIC_SIGNUP=true
```

Restart:

```bash
sudo systemctl restart modernplayer-api
```

Register:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"friend","email":"friend@example.com","password":"FriendPassword123"}'
```

If SMTP is not configured, response includes:

```json
"verification_url": "http://.../api/auth/verify-email?token=..."
```

Open that URL once to verify email.

## Login

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"friend","password":"FriendPassword123"}'
```

You can login by username or email.

## Admin/dev endpoints

Use dev token from `/api/auth/login`:

```bash
TOKEN="paste_token_here"
```

List users:

```bash
curl http://127.0.0.1:8000/api/admin/users \
  -H "Authorization: Bearer $TOKEN"
```

Ban user:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/users/friend/ban \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"banned":true}'
```

Unban:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/users/friend/ban \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"banned":false}'
```

Verify email manually:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/users/friend/verify \
  -H "Authorization: Bearer $TOKEN"
```

Change role:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/users/friend/role \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"user"}'
```

## Production recommendation

For now keep:

```env
ALLOW_PUBLIC_SIGNUP=false
```

until invite codes / captcha / email SMTP are fully tested. Existing users can still login when signup is disabled.
