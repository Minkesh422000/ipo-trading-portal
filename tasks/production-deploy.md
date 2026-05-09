# Production Deployment Checklist — Brkout Frontend

Changes needed before going live. All items are in `frontend/server.py`
and `frontend/src/data.jsx` unless noted.

---

## 1. Bind to all interfaces (server.py)

**Current (local only):**
```python
app.run(host="127.0.0.1", port=7654, debug=False)
```
**Change to:**
```python
app.run(host="0.0.0.0", port=7654, debug=False)
```
Or better — don't use Flask dev server at all (see item 3).

---

## 2. Add authentication (server.py)

Currently there is NO auth — anyone who reaches the server can see
positions, P&L, broker names, and change API credentials.

Add a simple token check on every route:

```python
import secrets as _secrets

API_TOKEN = os.environ.get("BRKOUT_API_TOKEN", "")   # set this in env

@app.before_request
def check_auth():
    from flask import request, abort
    # Allow kite-callback without auth (Kite redirects here)
    if request.path == "/kite-callback":
        return
    token = request.headers.get("X-API-Token") or request.args.get("token")
    if API_TOKEN and not _secrets.compare_digest(token or "", API_TOKEN):
        abort(401)
```

Set `BRKOUT_API_TOKEN` in your server's environment (random 32-char string).
The frontend then needs to send `X-API-Token: <token>` on every fetch — add it
to `fetchLiveData()` and all POST calls in connections.jsx.

---

## 3. Use gunicorn instead of Flask dev server (server.py)

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:7654 "frontend.server:app"
# or if running from project root:
gunicorn -w 2 -b 0.0.0.0:7654 frontend.server:app
```

Run via systemd or supervisor so it restarts on crash.

---

## 4. Update Kite redirect URL

In Kite developer console (developers.kite.trade/apps), change:

```
# Local (current)
http://localhost:7654/kite-callback

# Production — replace with your actual domain/IP
https://yourdomain.com/kite-callback
```

Also update the callback URL returned by `/api/kite/login-url/<id>` in server.py:
```python
callback = f"https://yourdomain.com/kite-callback?account_id={account_id}"
```

---

## 5. HTTPS (strongly recommended)

Run nginx as a reverse proxy in front of gunicorn with a Let's Encrypt cert:

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;
    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:7654;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 6. Secrets management

Current approach reads from `.streamlit/secrets.toml`. On the server either:
- Keep the same file (ensure it's not world-readable: `chmod 600 .streamlit/secrets.toml`)
- Or set env vars directly and remove the toml dependency

---

## 7. Data refresh interval (data.jsx)

60 seconds is fine for local. On a live server with multiple users consider
increasing to 120s to reduce DB/Kite API load:

```js
const REFRESH_INTERVAL_MS = 120_000;
```

---

## Summary of files to touch at deploy time

| File | Change |
|------|--------|
| `frontend/server.py` | host → `0.0.0.0`, add auth, update callback URL |
| `frontend/src/data.jsx` | add `X-API-Token` header to fetch, optionally increase interval |
| `frontend/src/pages/connections.jsx` | add token header to all POST calls |
| Kite developer console | update redirect URL to production domain |
| Server OS | set `BRKOUT_API_TOKEN` env var, use gunicorn + nginx |
