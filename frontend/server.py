"""
frontend/server.py — Flask dev server for the Brkout trading UI.

Serves static files from frontend/ and exposes /api/data with live data
from DB, Kite API, and the IPO scanner.

Usage:
    cd "Stock Strategy building"
    python frontend/server.py
    # → http://localhost:7654
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from datetime import datetime, date, timedelta

# ── Make project root importable ───────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

# ── Load secrets → env vars (before importing core modules) ───────────────────
try:
    import toml
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        secrets = toml.load(str(secrets_path))
        for k, v in secrets.items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)
        print(f"[server] Loaded secrets from {secrets_path}")
    else:
        print(f"[server] WARNING: {secrets_path} not found — using env vars only")
except ImportError:
    print("[server] WARNING: toml not installed — run: pip install toml")

# ── Flask ──────────────────────────────────────────────────────────────────────
from flask import Flask, send_from_directory, jsonify

FRONTEND_DIR = Path(__file__).parent.resolve()
app = Flask(__name__, static_folder=str(FRONTEND_DIR))


# ── Static file serving ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/kite-callback")
def kite_callback():
    """
    Zerodha redirects here after OAuth login.
    Configure this URL in your Kite developer console:
      http://localhost:7654/kite-callback
    """
    from flask import request as freq
    request_token = freq.args.get("request_token", "")
    account_id    = freq.args.get("account_id", "")
    status        = freq.args.get("status", "")

    if status != "success" or not request_token:
        return """<html><body style="font-family:monospace;background:#0d1117;color:#f0f6fc;padding:40px">
        <h2>❌ Login failed or cancelled</h2>
        <p>Status: """ + status + """</p>
        <a href="http://localhost:7654/#connections" style="color:#22c55e">← Back to Brkout</a>
        </body></html>"""

    # If account_id was passed via state param, use it; otherwise try first account
    if not account_id:
        try:
            from core.db import init_db, get_all_accounts
            conn = init_db()
            accounts = get_all_accounts(conn)
            account_id = accounts[0]["id"] if accounts else ""
        except Exception:
            pass

    if not account_id:
        return """<html><body style="font-family:monospace;background:#0d1117;color:#f0f6fc;padding:40px">
        <h2>⚠ No account found</h2>
        <p>Could not determine which account to link. Please use the manual token flow.</p>
        <p>Your request_token: <code style="color:#22c55e">""" + request_token + """</code></p>
        <a href="http://localhost:7654/#connections" style="color:#22c55e">← Back to Brkout</a>
        </body></html>"""

    # Auto-complete login
    try:
        from core.db import init_db
        from core.kite_manager import KiteManager
        conn = init_db()
        ok, err = KiteManager.complete_login(account_id, request_token, conn)
    except Exception as e:
        ok, err = False, str(e)

    if ok:
        return """<html>
        <head><meta http-equiv="refresh" content="2;url=http://localhost:7654/#connections"/></head>
        <body style="font-family:monospace;background:#0d1117;color:#f0f6fc;padding:40px;text-align:center">
        <h2 style="color:#22c55e">✓ Connected!</h2>
        <p>Kite token saved. Redirecting back to Brkout…</p>
        </body></html>"""
    else:
        return """<html><body style="font-family:monospace;background:#0d1117;color:#f0f6fc;padding:40px">
        <h2>❌ Token exchange failed</h2>
        <p style="color:#f87171">""" + err + """</p>
        <p>request_token: <code style="color:#22c55e">""" + request_token + """</code></p>
        <a href="http://localhost:7654/#connections" style="color:#22c55e">← Back to Brkout</a>
        </body></html>"""


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(str(FRONTEND_DIR), filename)


# ── Kite auth endpoints ────────────────────────────────────────────────────────

@app.route("/api/kite/login-url/<account_id>")
def kite_login_url(account_id):
    """Return the Kite OAuth login URL for a given account."""
    from flask import Response
    try:
        from core.db import init_db, get_account
        from core.kite_manager import KiteManager, _decrypt
        conn = init_db()
        account = get_account(conn, account_id)
        if not account:
            return jsonify({"ok": False, "error": "Account not found"}), 404
        api_key = _decrypt(account["kite_api_key"])
        login_url = KiteManager.generate_login_url(api_key)
        # Append account_id as state so callback knows which account to link
        sep = "&" if "?" in login_url else "?"
        callback = f"http://localhost:7654/kite-callback?account_id={account_id}"
        return jsonify({"ok": True, "url": login_url, "callback": callback})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/kite/update-credentials", methods=["POST"])
def kite_update_credentials():
    """Update api_key and/or api_secret for an account."""
    from flask import request as freq
    body = freq.get_json(force=True) or {}
    account_id = body.get("account_id", "")
    api_key    = body.get("api_key", "").strip()
    api_secret = body.get("api_secret", "").strip()
    if not account_id or not api_key or not api_secret:
        return jsonify({"ok": False, "error": "account_id, api_key and api_secret required"}), 400
    try:
        from core.db import init_db, get_account
        from core.kite_manager import _encrypt
        from core.db import DATABASE_MODE
        conn = init_db()
        account = get_account(conn, account_id)
        if not account:
            return jsonify({"ok": False, "error": "Account not found"}), 404
        enc_key    = _encrypt(api_key)
        enc_secret = _encrypt(api_secret)
        if DATABASE_MODE == "supabase":
            from core.db import _get_supabase
            _get_supabase().table("accounts").update({
                "kite_api_key": enc_key,
                "kite_api_secret": enc_secret,
                "access_token": None,
                "token_generated_at": None,
            }).eq("id", account_id).execute()
        else:
            conn.execute(
                "UPDATE accounts SET kite_api_key=?, kite_api_secret=?, access_token=NULL, token_generated_at=NULL WHERE id=?",
                (enc_key, enc_secret, account_id)
            )
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/kite/complete-login", methods=["POST"])
def kite_complete_login():
    """Exchange a request_token for an access_token (manual paste flow)."""
    from flask import request as freq, Response
    body = freq.get_json(force=True) or {}
    account_id    = body.get("account_id", "")
    request_token = body.get("request_token", "").strip()
    if not account_id or not request_token:
        return jsonify({"ok": False, "error": "account_id and request_token required"}), 400
    try:
        from core.db import init_db
        from core.kite_manager import KiteManager
        conn = init_db()
        ok, err = KiteManager.complete_login(account_id, request_token, conn)
        return jsonify({"ok": ok, "error": err})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── On-demand rescan endpoint ──────────────────────────────────────────────────

@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Trigger a fresh IPO scan with force_refresh=True and return the universe."""
    from flask import Response
    try:
        from core.db import init_db
        conn = init_db()
        ipo_universe = _run_ipo_scanner(conn, force_refresh=True)
        resp = Response(
            json.dumps({"ok": True, "ipo_universe": ipo_universe, "count": len(ipo_universe)}, default=str),
            mimetype="application/json"
        )
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Live data endpoint ─────────────────────────────────────────────────────────

@app.route("/api/data")
def api_data():
    from flask import Response
    payload = build_payload()
    resp = Response(json.dumps(payload, default=str), mimetype="application/json")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def build_payload() -> dict:
    """Fetch all live data, fall back gracefully on errors."""
    from core.db import (
        init_db, get_all_accounts, get_all_strategies,
        get_strategy_assignments, get_active_signals, get_signal_history,
        get_orders, get_gtts, get_positions, get_margins,
    )
    from core.kite_manager import KiteManager

    # Initialise DB connection
    try:
        conn = init_db()
    except Exception as e:
        print(f"[server] DB init error: {e}")
        return {}

    payload: dict = {}

    # ── Accounts / Brokers ─────────────────────────────────────────────────────
    accounts = []
    try:
        raw_accounts = get_all_accounts(conn)
        for acc in raw_accounts:
            connected = KiteManager.is_token_valid(acc)
            balance = None
            if connected:
                try:
                    margins = get_margins(conn, acc["id"])
                    balance = margins.get("available_cash") if margins else None
                except Exception:
                    pass
            accounts.append({
                "id":        acc.get("id"),
                "name":      acc.get("nickname", acc.get("id")),
                "account":   acc.get("kite_user_id", "—"),
                "broker":    "Zerodha",
                "connected": connected,
                "balance":   balance,
            })
        print(f"[server] Accounts: {len(accounts)}")
    except Exception as e:
        print(f"[server] Accounts error: {e}")

    payload["brokers"] = accounts

    # ── Strategies ─────────────────────────────────────────────────────────────
    strategies = []
    try:
        raw_strats = get_all_strategies(conn)
        for s in raw_strats:
            assignments = get_strategy_assignments(conn, s["id"])
            total_capital = sum(a.get("capital_alloc", 0) or 0 for a in assignments)
            strategies.append({
                "id":        s.get("id"),
                "name":      s.get("name"),
                "type":      s.get("type"),
                "active":    bool(s.get("is_active", 1)),
                "capital":   total_capital,
                "used":      0,        # live Kite positions will update this
                "openR":     0.0,
                "winRate":   0.0,
                "assignments": assignments,
            })
        print(f"[server] Strategies: {len(strategies)}")
    except Exception as e:
        print(f"[server] Strategies error: {e}")

    payload["strategies"] = strategies

    # ── Active signals (open positions being tracked) ──────────────────────────
    active_signals = []
    try:
        active_signals = get_active_signals(conn)
        print(f"[server] Active signals: {len(active_signals)}")
    except Exception as e:
        print(f"[server] Active signals error: {e}")

    payload["active_signals"] = active_signals

    # ── Signals today (dashboard feed) ────────────────────────────────────────
    signals_today = []
    today_str = date.today().isoformat()
    try:
        all_recent = get_signal_history(conn, limit=200)
        for sig in all_recent:
            gen_at = sig.get("generated_at", "")
            if not gen_at.startswith(today_str):
                continue
            status = sig.get("status", "")
            action = "FIRED" if status in ("EXECUTED", "PENDING_FILL") else \
                     "VOID"  if status in ("STOPPED_OUT", "INVALID") else "WATCH"
            signals_today.append({
                "time":   gen_at[11:16] if len(gen_at) >= 16 else "—",
                "sym":    sig.get("symbol", ""),
                "msg":    sig.get("notes") or f"{sig.get('signal_type', 'Signal')} @ ₹{sig.get('entry_price', '')}",
                "action": action,
            })
        print(f"[server] Signals today: {len(signals_today)}")
    except Exception as e:
        print(f"[server] Signals today error: {e}")

    payload["signals_today"] = signals_today

    # ── Closed trades ──────────────────────────────────────────────────────────
    closed_trades = []
    try:
        history = get_signal_history(conn, limit=100)
        closed_statuses = {"T3_HIT", "T2_HIT", "T1_HIT", "STOPPED_OUT"}
        for sig in history:
            if sig.get("status") not in closed_statuses:
                continue
            entry = sig.get("entry_price") or 0
            sl    = sig.get("sl_price") or entry
            t1    = sig.get("t1") or entry
            t2    = sig.get("t2") or entry
            t3    = sig.get("t3") or entry
            status = sig.get("status", "")
            exit_price = (
                t3 if status == "T3_HIT" else
                t2 if status == "T2_HIT" else
                t1 if status == "T1_HIT" else sl
            )
            qty  = sig.get("quantity") or 1
            R    = (entry - sl) if (entry - sl) != 0 else 1
            pnl  = (exit_price - entry) * qty
            r_mult = (exit_price - entry) / R if R else 0
            outcome = (
                "T3" if status == "T3_HIT" else
                "T2" if status == "T2_HIT" else
                "T1" if status == "T1_HIT" else "SL"
            )
            closed_trades.append({
                "date":    (sig.get("generated_at") or "")[:10],
                "sym":     sig.get("symbol", ""),
                "qty":     qty,
                "entry":   entry,
                "exit":    exit_price,
                "setup":   sig.get("signal_type", "IPO Breakout"),
                "quality": 4,          # default — no quality field yet
                "outcome": outcome,
                "r":       round(r_mult, 2),
                "pnl":     round(pnl, 2),
            })
        print(f"[server] Closed trades: {len(closed_trades)}")
    except Exception as e:
        print(f"[server] Closed trades error: {e}")

    payload["closed_trades"] = closed_trades

    # ── Equity curve (cumulative P&L from closed trades) ──────────────────────
    equity_curve = []
    try:
        if closed_trades:
            sorted_trades = sorted(closed_trades, key=lambda t: t["date"])
            running = 1_000_000.0   # starting notional capital
            peak    = running
            for t in sorted_trades:
                running += t["pnl"]
                peak     = max(peak, running)
                equity_curve.append({"val": round(running, 2), "peak": round(peak, 2)})
        print(f"[server] Equity curve: {len(equity_curve)} points")
    except Exception as e:
        print(f"[server] Equity curve error: {e}")

    payload["equity_curve"] = equity_curve

    # ── Positions (DB cache + Kite live) ──────────────────────────────────────
    positions = []
    try:
        # Map active signals by symbol for SL/target lookup
        sig_map = {s["symbol"]: s for s in active_signals}

        for acc in accounts:
            acc_id = acc["id"]

            # Try live Kite positions first
            kite = None
            if acc["connected"]:
                try:
                    kite = KiteManager.get_kite(acc_id, conn)
                except Exception:
                    pass

            if kite:
                try:
                    live = kite.positions()
                    for p in live.get("net", []):
                        if p.get("quantity", 0) == 0:
                            continue
                        sym = p.get("tradingsymbol", "")
                        sig = sig_map.get(sym, {})
                        entry = p.get("average_price", 0)
                        last  = p.get("last_price", entry)
                        sl    = sig.get("sl_price", entry * 0.95)
                        t1    = sig.get("t1", entry * 1.05)
                        t2    = sig.get("t2", entry * 1.10)
                        t3    = sig.get("t3", entry * 1.15)
                        R     = (entry - sl) if (entry - sl) != 0 else 1
                        r_val = (last - entry) / R if R else 0
                        positions.append({
                            "sym":      sym,
                            "qty":      p.get("quantity"),
                            "entry":    entry,
                            "last":     last,
                            "sl":       sl,
                            "target1":  t1,
                            "target2":  t2,
                            "target3":  t3,
                            "r":        round(r_val, 2),
                            "broker":   acc["name"],
                            "strategy": "IPO Breakout",
                            "entered":  sig.get("generated_at", "")[:16],
                        })
                    print(f"[server] Live Kite positions for {acc_id}: {len(positions)}")
                    continue   # skip DB cache for this account
                except Exception as e:
                    print(f"[server] Kite positions error for {acc_id}: {e}")

            # Fall back to DB cached positions
            try:
                db_pos = get_positions(conn, acc_id)
                for p in db_pos:
                    if (p.get("quantity") or 0) == 0:
                        continue
                    sym   = p.get("symbol", "")
                    sig   = sig_map.get(sym, {})
                    entry = p.get("average_price", 0)
                    last  = p.get("last_price", entry)
                    sl    = sig.get("sl_price", entry * 0.95)
                    t1    = sig.get("t1", entry * 1.05)
                    t2    = sig.get("t2", entry * 1.10)
                    t3    = sig.get("t3", entry * 1.15)
                    R     = (entry - sl) if (entry - sl) != 0 else 1
                    r_val = (last - entry) / R if R else 0
                    positions.append({
                        "sym":      sym,
                        "qty":      p.get("quantity"),
                        "entry":    entry,
                        "last":     last,
                        "sl":       sl,
                        "target1":  t1,
                        "target2":  t2,
                        "target3":  t3,
                        "r":        round(r_val, 2),
                        "broker":   acc["name"],
                        "strategy": "IPO Breakout",
                        "entered":  sig.get("generated_at", "")[:16],
                    })
            except Exception as e:
                print(f"[server] DB positions error for {acc_id}: {e}")

        print(f"[server] Total positions: {len(positions)}")
    except Exception as e:
        print(f"[server] Positions error: {e}")

    payload["positions"] = positions

    # ── Pending orders (GTT + LIMIT from DB + Kite) ────────────────────────────
    pending_orders = []
    try:
        for acc in accounts:
            acc_id = acc["id"]

            # Live GTTs from Kite
            kite = None
            if acc["connected"]:
                try:
                    kite = KiteManager.get_kite(acc_id, conn)
                except Exception:
                    pass

            if kite:
                try:
                    gtts = kite.get_gtts()
                    for g in gtts:
                        if g.get("status") != "active":
                            continue
                        cond = (g.get("condition") or {})
                        orders_list = g.get("orders") or [{}]
                        o = orders_list[0] if orders_list else {}
                        pending_orders.append({
                            "sym":     g.get("tradingsymbol", ""),
                            "type":    "GTT",
                            "side":    o.get("transaction_type", "BUY"),
                            "qty":     o.get("quantity", 0),
                            "trigger": cond.get("trigger_values", [None])[0],
                            "limit":   o.get("price"),
                            "sl":      None,
                            "target":  None,
                            "placed":  g.get("created_at", ""),
                            "broker":  acc["name"],
                        })
                except Exception as e:
                    print(f"[server] Kite GTT error for {acc_id}: {e}")

            # DB GTTs
            try:
                db_gtts = get_gtts(conn, acc_id)
                for g in db_gtts:
                    if g.get("status") != "active":
                        continue
                    pending_orders.append({
                        "sym":     g.get("symbol", ""),
                        "type":    "GTT",
                        "side":    "BUY",
                        "qty":     g.get("quantity", 0),
                        "trigger": g.get("upper_trigger"),
                        "limit":   g.get("upper_trigger"),
                        "sl":      g.get("lower_trigger"),
                        "target":  None,
                        "placed":  g.get("created_at", ""),
                        "broker":  acc["name"],
                    })
            except Exception as e:
                print(f"[server] DB GTT error for {acc_id}: {e}")

            # DB pending limit orders
            try:
                db_orders = get_orders(conn, acc_id, limit=50)
                for o in db_orders:
                    if o.get("status") not in ("OPEN", "TRIGGER PENDING", "pending"):
                        continue
                    pending_orders.append({
                        "sym":     o.get("symbol", ""),
                        "type":    o.get("order_type", "LIMIT"),
                        "side":    o.get("transaction_type", "BUY"),
                        "qty":     o.get("quantity", 0),
                        "trigger": o.get("trigger_price"),
                        "limit":   o.get("price"),
                        "sl":      None,
                        "target":  None,
                        "placed":  o.get("placed_at", ""),
                        "broker":  acc["name"],
                    })
            except Exception as e:
                print(f"[server] DB orders error for {acc_id}: {e}")

        print(f"[server] Pending orders: {len(pending_orders)}")
    except Exception as e:
        print(f"[server] Pending orders error: {e}")

    payload["pending_orders"] = pending_orders

    # ── IPO Universe (scanner) ─────────────────────────────────────────────────
    ipo_universe = _run_ipo_scanner(conn, force_refresh=False)
    payload["ipo_universe"] = ipo_universe

    return payload


def _run_ipo_scanner(conn, force_refresh: bool = False) -> list[dict]:
    """Fetch IPO list → OHLC → compute scanner states. Returns frontend-shaped list."""
    try:
        from datetime import timedelta
        from scraper import fetch_ipo_listings
        from core.data_fetcher import fetch_all_ohlc
        from strategies.ipo_breakout import IPOBreakoutStrategy

        today = date.today()
        ipo_list = fetch_ipo_listings(today - timedelta(days=180), today, conn)
        if not ipo_list:
            print("[server] IPO scanner: no IPOs returned by scraper")
            return []

        ohlc_data = fetch_all_ohlc(ipo_list, conn=conn, force_refresh=force_refresh)
        states = IPOBreakoutStrategy.compute_scanner_states(ipo_list, ohlc_data)

        result = []
        status_map = {
            "FRESH":    "fired",    # broke 2W high within last 5 bars — actionable now
            "NEAR":     "armed",    # within 3% of trigger — on watchlist
            "WATCHING": "pending",  # still in 2-week observation window
            "PAST":     "past",     # fired more than 5 bars ago — trade already underway
            "NO_DATA":  "invalid",
        }
        for s in states:
            raw_status = s.get("status", "NO_DATA")
            result.append({
                "sym":         s.get("symbol", ""),
                "name":        s.get("name", s.get("symbol", "")),
                "sector":      s.get("sector", "—"),
                "listDate":    str(s.get("listing_date", "")),
                "listPrice":   s.get("listing_price"),
                "hi":          s.get("two_week_high"),
                "lo":          s.get("two_week_low"),
                "last":        s.get("current_price"),
                "status":      status_map.get(raw_status, "pending"),
                "rawStatus":   raw_status,
                "entryStatus": s.get("entry_status", ""),
                "score":       s.get("score", 0),
                "pctFromEntry": s.get("pct_from_entry"),
                "vol":         f"{s.get('volume_ratio', 0):.1f}x" if s.get("volume_ratio") else "—",
                "marketCap":   s.get("market_cap_cr"),
                "daysOld":     s.get("days_since_listing", 0),
            })

        print(f"[server] IPO scanner: {len(result)} IPOs (force_refresh={force_refresh})")
        return result

    except Exception as e:
        import traceback
        print(f"[server] IPO scanner error: {e}")
        traceback.print_exc()
        return []


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[server] Serving frontend from: {FRONTEND_DIR}")
    print(f"[server] Starting on http://localhost:7654  (localhost only)")
    app.run(host="127.0.0.1", port=7654, debug=False)
