"""
api/ipo_check.py — Vercel serverless function.

Vercel calls this via cron (see vercel.json).
It simply runs the same ipo_alert.main() logic.

All env vars (GSHEET_CSV_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, KV_REST_API_*) are set
in the Vercel dashboard under Project → Settings → Environment Variables.
"""
from http.server import BaseHTTPRequestHandler
import sys
import os

# Make the root project importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            import ipo_alert
            ipo_alert.main()
            msg = b"IPO alert scan complete."
            self.send_response(200)
        except Exception as e:
            msg = f"Error: {e}".encode()
            self.send_response(500)

        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg)

    # Vercel also sends POST for cron triggers
    def do_POST(self):
        self.do_GET()
