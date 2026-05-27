"""
ipo_alert.py — IPO 2-Week Breakout: Telegram alerts + Google Sheet write-back.

Usage:
  GSHEET_CSV_URL=<url> TELEGRAM_BOT_TOKEN=<token> TELEGRAM_CHAT_ID=<id> \
  GSHEET_SERVICE_ACCOUNT_JSON=<base64-json> python ipo_alert.py

Sheet columns (A-D filled by user, E-Q written by script):
  A: nse_symbol       B: name          C: listing_date   D: capital_allocated
  E: status           F: entry_price   G: sl_price
  H: t1               I: t1_hit_date
  J: t2               K: t2_hit_date
  L: t3               M: t3_hit_date
  N: current_price    O: qty           P: gain_pct       Q: gain_inr

Status values written to sheet:
  Watching | Near Breakout | Entry Trigger | In Trade | T1 Hit | T2 Hit | T3 Hit | SL Hit

Environment variables:
  GSHEET_CSV_URL               — Public CSV export URL of your Google Sheet
  TELEGRAM_BOT_TOKEN           — From @BotFather on Telegram
  TELEGRAM_CHAT_ID             — Your Telegram chat/user ID
  GSHEET_SERVICE_ACCOUNT_JSON  — Base64-encoded service account JSON (for write-back)
                                  Get from: Google Cloud Console → IAM → Service Accounts

  Optional (Vercel deployment):
  KV_REST_API_URL   — Vercel KV REST URL
  KV_REST_API_TOKEN — Vercel KV REST token
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from math import floor

sys.path.insert(0, os.path.dirname(__file__))

from strategies.ipo_breakout import IPOBreakoutStrategy

STATE_FILE = os.path.join(os.path.dirname(__file__), "alert_state.json")

# Sheet column layout (0-indexed)
SHEET_HEADERS = [
    "nse_symbol", "name", "listing_date", "capital_allocated",
    "status", "entry_price", "sl_price",
    "t1", "t1_hit_date",
    "t2", "t2_hit_date",
    "t3", "t3_hit_date",
    "current_price", "qty", "gain_pct", "gain_inr",
]

# ── 1. Config ──────────────────────────────────────────────────────────────────

def _require_env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        print(f"[ERROR] Environment variable {name} is not set.")
        sys.exit(1)
    return val


def _extract_sheet_id(csv_url: str) -> str | None:
    """Extract Google Sheet ID from any Sheets URL."""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", csv_url)
    return m.group(1) if m else None


# ── 2. State (Vercel KV or local JSON) ────────────────────────────────────────

_KV_KEY = "ipo_alert_state"


def _kv_headers() -> dict:
    token = os.getenv("KV_REST_API_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _kv_url() -> str:
    return os.getenv("KV_REST_API_URL", "").rstrip("/")


def _kv_available() -> bool:
    return bool(_kv_url() and os.getenv("KV_REST_API_TOKEN"))


def load_state() -> dict[str, str]:
    if _kv_available():
        try:
            req = urllib.request.Request(f"{_kv_url()}/get/{_KV_KEY}", headers=_kv_headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
                raw = body.get("result") or "{}"
                state = json.loads(raw) if isinstance(raw, str) else raw
                print(f"[STATE] Loaded from Vercel KV ({len(state)} symbols)")
                return state
        except Exception as e:
            print(f"[STATE] KV load failed: {e} — using empty state")
            return {}

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict[str, str]) -> None:
    if _kv_available():
        data = json.dumps(json.dumps(state)).encode()
        req = urllib.request.Request(
            f"{_kv_url()}/set/{_KV_KEY}", data=data, method="POST",
            headers={**_kv_headers(), "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                print(f"[STATE] Saved to Vercel KV ({len(state)} symbols)")
                return
        except Exception as e:
            print(f"[STATE] KV save failed: {e}")

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"[STATE] Saved alert_state.json ({len(state)} symbols)")


# ── 3. Read IPO watchlist ──────────────────────────────────────────────────────

def load_ipo_list(csv_url: str) -> tuple[list[dict], dict[str, float]]:
    """
    Returns (ipo_list, capital_map) where capital_map = {symbol: capital_allocated}.
    capital_allocated is optional — 0.0 if not provided by user.
    """
    if not csv_url.startswith("http"):
        print(f"[SHEET] Reading local file: {csv_url}")
        try:
            with open(csv_url, "r") as f:
                raw = f.read()
        except Exception as e:
            print(f"[ERROR] Could not read local file: {e}")
            sys.exit(1)
    else:
        print(f"[SHEET] Fetching IPO watchlist from Google Sheets...")
        try:
            import requests as _req
            resp = _req.get(csv_url, timeout=15)
            resp.raise_for_status()
            raw = resp.text
        except Exception as e:
            print(f"[ERROR] Could not fetch Google Sheet: {e}")
            sys.exit(1)

    reader = csv.DictReader(io.StringIO(raw))
    ipos, capital_map = [], {}
    for row in reader:
        sym = row.get("nse_symbol", "").strip().upper()
        name = row.get("name", sym).strip()
        listing_raw = row.get("listing_date", "").strip()
        if not sym or not listing_raw:
            continue
        try:
            listing_date = date.fromisoformat(listing_raw)
        except ValueError:
            print(f"[WARN] Skipping {sym} — bad listing_date: {listing_raw!r}")
            continue
        if (date.today() - listing_date).days > 730:
            continue

        capital_raw = row.get("capital_allocated", "").strip().replace(",", "")
        try:
            capital_map[sym] = float(capital_raw) if capital_raw else 0.0
        except ValueError:
            capital_map[sym] = 0.0

        ipos.append({"nse_symbol": sym, "name": name, "listing_date": listing_date})

    print(f"[SHEET] Loaded {len(ipos)} active IPO(s)")
    return ipos, capital_map


# ── 4. Fetch OHLC ──────────────────────────────────────────────────────────────

def fetch_all_ohlc(ipo_list: list[dict]) -> dict[str, list[dict]]:
    try:
        import yfinance as yf
    except ImportError:
        print("[ERROR] yfinance not installed.")
        sys.exit(1)

    import time
    result: dict[str, list[dict]] = {}

    for ipo in ipo_list:
        sym = ipo["nse_symbol"]
        listing_date: date = ipo["listing_date"]
        fetch_to = min(date.today(), listing_date + timedelta(days=730))

        try:
            ticker = yf.Ticker(f"{sym}.NS")
            df = ticker.history(
                start=listing_date.isoformat(),
                end=(fetch_to + timedelta(days=1)).isoformat(),
                interval="1d", auto_adjust=True,
            )
            if df is None or df.empty:
                result[sym] = []
                print(f"[OHLC] {sym}: no data")
                continue

            rows = []
            for ts, row in df.iterrows():
                bar_date = ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10])
                rows.append({
                    "date": bar_date.isoformat(),
                    "open": float(row["Open"]), "high": float(row["High"]),
                    "low":  float(row["Low"]),  "close": float(row["Close"]),
                    "volume": int(row.get("Volume", 0)),
                })
            rows.sort(key=lambda x: x["date"])
            result[sym] = rows
            print(f"[OHLC] {sym}: {len(rows)} bars")
        except Exception as e:
            result[sym] = []
            print(f"[OHLC] {sym}: failed — {e}")

        time.sleep(0.15)

    return result


# ── 5. Hit-date helpers ────────────────────────────────────────────────────────

def _first_high_above(bars: list[dict], price: float, after: str) -> str:
    """First bar date where HIGH >= price, strictly after `after` date."""
    for b in bars:
        if b["date"] <= after:
            continue
        if b["high"] >= price:
            return b["date"]
    return ""


def _first_low_below(bars: list[dict], price: float, after: str) -> str:
    """First bar date where LOW <= price, strictly after `after` date."""
    for b in bars:
        if b["date"] <= after:
            continue
        if b["low"] <= price:
            return b["date"]
    return ""


# ── 6. Compute sheet row data ──────────────────────────────────────────────────

def _clean_status(row: dict) -> str:
    """Map scanner row to a clean human-readable status for the sheet."""
    status = row["status"]
    entry_status = row.get("entry_status", "")

    if status == "WATCHING":
        return "Watching"
    if status == "NEAR":
        return "Near Breakout"
    if status == "FRESH":
        return "Entry Trigger"
    if status == "NO_DATA":
        return "No Data"

    # PAST — determine from entry_status emoji labels
    if "T3 Hit" in entry_status:
        return "T3 Hit"
    if "T2 Hit" in entry_status:
        return "T2 Hit"
    if "T1 Hit" in entry_status:
        return "T1 Hit"
    if "Stopped Out" in entry_status:
        return "SL Hit"
    if "In Trade" in entry_status:
        return "In Trade"
    if "Below Entry" in entry_status:
        return "Entry Pending"
    if "Entry Pending" in entry_status:
        return "Entry Pending"

    return status.capitalize()


def build_sheet_row(
    row: dict,
    bars: list[dict],
    capital: float,
) -> dict:
    """
    Build a complete dict of all sheet columns for one IPO.
    `capital` is the user-provided capital_allocated (0 if not set).
    """
    sym         = row["symbol"]
    status_lbl  = _clean_status(row)
    entry       = row.get("entry_price") or 0.0
    sl          = row.get("sl_price")    or 0.0
    t1          = row.get("t1")          or 0.0
    t2          = row.get("t2")          or 0.0
    t3          = row.get("t3")          or 0.0
    current     = row.get("current_price") or 0.0
    signal_date = row.get("signal_date") or ""

    # Hit dates (only meaningful once a breakout signal exists)
    t1_hit_date = _first_high_above(bars, t1, signal_date) if (t1 and signal_date) else ""
    t2_hit_date = _first_high_above(bars, t2, signal_date) if (t2 and signal_date) else ""
    t3_hit_date = _first_high_above(bars, t3, signal_date) if (t3 and signal_date) else ""

    # For SL hit: effective SL moves to breakeven after T1 is hit
    effective_sl = entry if t1_hit_date else sl
    sl_hit_date  = _first_low_below(bars, effective_sl, signal_date) if (effective_sl and signal_date) else ""

    # Override status if SL was hit before any target (to avoid showing In Trade)
    if sl_hit_date and not t1_hit_date and status_lbl == "In Trade":
        status_lbl = "SL Hit"

    # Capital / gain
    qty = floor(capital / entry) if (capital > 0 and entry > 0) else 0

    # Use best exit price for realised trades
    if status_lbl == "T3 Hit":
        ref_price = t3
    elif status_lbl == "T2 Hit":
        ref_price = t2
    elif status_lbl == "T1 Hit":
        ref_price = t1
    elif status_lbl == "SL Hit":
        ref_price = effective_sl
    else:
        ref_price = current  # mark-to-market for all live / pending

    gain_pct = round((ref_price - entry) / entry * 100, 2) if entry else 0.0
    gain_inr = round((ref_price - entry) * qty, 2)         if (entry and qty) else 0.0

    return {
        "status":        status_lbl,
        "entry_price":   round(entry, 2),
        "sl_price":      round(sl, 2),
        "t1":            round(t1, 2),
        "t1_hit_date":   t1_hit_date,
        "t2":            round(t2, 2),
        "t2_hit_date":   t2_hit_date,
        "t3":            round(t3, 2),
        "t3_hit_date":   t3_hit_date,
        "current_price": round(current, 2),
        "qty":           qty,
        "gain_pct":      gain_pct,
        "gain_inr":      gain_inr,
    }


# ── 7. Auto-sync new IPOs from Chittorgarh → Sheet ───────────────────────────

def fetch_chittorgarh_ipos(days_back: int = 90) -> list[dict]:
    """
    Fetch recently listed IPOs from Chittorgarh API (no DB needed).
    Returns [{nse_symbol, name, listing_date}] for NSE-listed IPOs
    that listed within the last `days_back` days.
    """
    from scraper import fetch_ipo_listings_for_year

    today     = date.today()
    from_date = today - timedelta(days=days_back)
    years     = sorted(set([from_date.year, today.year]))

    all_ipos: list[dict] = []
    for year in years:
        try:
            all_ipos.extend(fetch_ipo_listings_for_year(year))
        except Exception as e:
            print(f"[CHITTORGARH] Failed to fetch {year}: {e}")

    result = []
    for ipo in all_ipos:
        sym          = (ipo.get("nse_symbol") or "").strip().upper()
        listing_date = ipo.get("listing_date")
        name         = (ipo.get("name") or sym).strip()
        if not sym or not listing_date:
            continue
        if from_date <= listing_date <= today:
            result.append({"nse_symbol": sym, "name": name, "listing_date": listing_date})

    result.sort(key=lambda x: x["listing_date"], reverse=True)
    return result


def sync_chittorgarh_to_sheet(csv_url: str) -> None:
    """
    Fetch recent IPOs from Chittorgarh and append any new ones to the Google Sheet.

    - Requires GSHEET_SERVICE_ACCOUNT_JSON for write access.
    - Skips silently if credentials are not set.
    - Only adds NSE-listed IPOs from the last 90 days.
    - Never overwrites existing rows — only appends missing symbols.
    """
    import base64

    sa_raw = os.getenv("GSHEET_SERVICE_ACCOUNT_JSON", "").strip()
    if not sa_raw:
        print("[SYNC] No service account set — skipping Chittorgarh auto-sync.")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("[SYNC] gspread not installed — skipping sync.")
        return

    # Fetch from Chittorgarh
    print("[SYNC] Fetching recent IPOs from Chittorgarh...")
    try:
        new_ipos = fetch_chittorgarh_ipos(days_back=90)
    except Exception as e:
        print(f"[SYNC] Chittorgarh fetch error: {e}")
        return
    print(f"[SYNC] Found {len(new_ipos)} recently listed NSE IPOs")

    # Open Google Sheet
    try:
        sa_info = json.loads(base64.b64decode(sa_raw).decode())
    except Exception:
        try:
            sa_info = json.loads(sa_raw)
        except Exception as e:
            print(f"[SYNC] Invalid service account JSON: {e}")
            return

    sheet_id = _extract_sheet_id(csv_url)
    if not sheet_id:
        print("[SYNC] Cannot extract Sheet ID from URL.")
        return

    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds  = Credentials.from_service_account_info(sa_info, scopes=scopes)
        gc     = gspread.authorize(creds)
        ws     = gc.open_by_key(sheet_id).get_worksheet(0)
    except Exception as e:
        print(f"[SYNC] Cannot open sheet: {e}")
        return

    # Read existing symbols so we don't duplicate rows
    all_values = ws.get_all_values()
    if not all_values:
        # Empty sheet — write headers first
        ws.update("A1", [SHEET_HEADERS])
        existing_symbols: set[str] = set()
    else:
        headers   = [h.strip().lower() for h in all_values[0]]
        sym_col   = headers.index("nse_symbol") if "nse_symbol" in headers else 0
        existing_symbols = {
            r[sym_col].strip().upper()
            for r in all_values[1:]
            if len(r) > sym_col and r[sym_col].strip()
        }

    # Append new IPOs (user fills capital_allocated later)
    added = 0
    for ipo in new_ipos:
        sym = ipo["nse_symbol"]
        if sym in existing_symbols:
            continue
        ws.append_row(
            [sym, ipo["name"], ipo["listing_date"].isoformat(), ""],
            value_input_option="USER_ENTERED",
        )
        existing_symbols.add(sym)
        added += 1
        print(f"[SYNC] + {sym}  ({ipo['name']})  listed {ipo['listing_date']}")

    if added == 0:
        print("[SYNC] Sheet already up to date — no new IPOs to add.")
    else:
        print(f"[SYNC] Added {added} new IPO(s). Set capital_allocated to track gains.")


# ── 8. Write back to Google Sheet ─────────────────────────────────────────────

def write_sheet(csv_url: str, sheet_data: dict[str, dict]) -> None:
    """
    Update the Google Sheet with computed columns for each symbol.
    Requires GSHEET_SERVICE_ACCOUNT_JSON env var (base64-encoded service account JSON).
    Adds missing header columns automatically.
    Skips silently if credentials are not configured.
    """
    import base64

    sa_raw = os.getenv("GSHEET_SERVICE_ACCOUNT_JSON", "").strip()
    if not sa_raw:
        print("[SHEET] No GSHEET_SERVICE_ACCOUNT_JSON set — skipping write-back.")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("[SHEET] gspread / google-auth not installed — skipping write-back.")
        print("        Install: pip install gspread google-auth")
        return

    # Decode JSON (supports raw JSON or base64-encoded JSON)
    try:
        sa_info = json.loads(base64.b64decode(sa_raw).decode())
    except Exception:
        try:
            sa_info = json.loads(sa_raw)
        except Exception as e:
            print(f"[SHEET] Invalid service account JSON: {e}")
            return

    sheet_id = _extract_sheet_id(csv_url)
    if not sheet_id:
        print("[SHEET] Could not extract Sheet ID from URL — skipping write-back.")
        return

    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds  = Credentials.from_service_account_info(sa_info, scopes=scopes)
        gc     = gspread.authorize(creds)
        ws     = gc.open_by_key(sheet_id).get_worksheet(0)
    except Exception as e:
        print(f"[SHEET] Could not open sheet: {e}")
        return

    # Ensure all required headers exist; add missing ones to the right
    current_headers = ws.row_values(1)
    for col_name in SHEET_HEADERS:
        if col_name not in current_headers:
            current_headers.append(col_name)
            ws.update_cell(1, len(current_headers), col_name)
            print(f"[SHEET] Added header column: {col_name}")

    # Build column index map (1-based)
    col_idx = {h: i + 1 for i, h in enumerate(current_headers)}

    # Script-managed columns (we never overwrite user-filled ones)
    WRITE_COLS = [
        "status", "entry_price", "sl_price",
        "t1", "t1_hit_date", "t2", "t2_hit_date", "t3", "t3_hit_date",
        "current_price", "qty", "gain_pct", "gain_inr",
    ]

    # Read existing rows to find which row each symbol is on
    all_rows = ws.get_all_values()
    sym_col  = col_idx.get("nse_symbol", 1) - 1  # 0-indexed for list access

    cells_to_update = []
    for row_idx, sheet_row in enumerate(all_rows[1:], start=2):  # skip header
        sym = sheet_row[sym_col].strip().upper() if len(sheet_row) > sym_col else ""
        if sym not in sheet_data:
            continue
        computed = sheet_data[sym]
        for col_name in WRITE_COLS:
            if col_name not in col_idx:
                continue
            val = computed.get(col_name, "")
            cells_to_update.append(
                gspread.Cell(row_idx, col_idx[col_name], str(val) if val != 0 else "0")
            )

    if cells_to_update:
        ws.update_cells(cells_to_update, value_input_option="USER_ENTERED")
        print(f"[SHEET] Updated {len(cells_to_update)} cells across {len(sheet_data)} symbols.")
    else:
        print("[SHEET] No cells to update.")


# ── 8. Telegram alerts ─────────────────────────────────────────────────────────

def send_alert(text: str) -> bool:
    from core.notifier import send_message
    ok = send_message(text, parse_mode="HTML")
    if not ok:
        print("[TG] Send failed — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
    return ok


def build_near_message(row: dict, computed: dict) -> str:
    sym     = row["symbol"]
    company = row["company"]
    pct     = abs(row.get("pct_to_breakout") or 0)
    entry   = computed["entry_price"]
    sl      = computed["sl_price"]
    t1, t2, t3 = computed["t1"], computed["t2"], computed["t3"]
    R = round(entry - sl, 2)
    return (
        f"⚠️ <b>IPO NEAR BREAKOUT — {sym}</b>\n"
        f"<i>{company}</i>\n\n"
        f"Obs window closed. Within <b>{pct:.1f}%</b> of 2-week high.\n\n"
        f"<b>Entry (2WH):</b> ₹{entry}  |  <b>SL:</b> ₹{sl}  (R=₹{R})\n"
        f"<b>T1:</b> ₹{t1}  |  <b>T2:</b> ₹{t2}  |  <b>T3:</b> ₹{t3}\n\n"
        f"👉 Set LIMIT BUY at ₹{entry}\n"
        f"<a href='https://kite.zerodha.com/chart/web/ciq/NSE/{sym}/EQ'>📈 Chart</a>"
    )


def build_fresh_message(row: dict, computed: dict) -> str:
    sym     = row["symbol"]
    company = row["company"]
    entry   = computed["entry_price"]
    sl      = computed["sl_price"]
    t1, t2, t3 = computed["t1"], computed["t2"], computed["t3"]
    R  = round(entry - sl, 2)
    rr = round((t3 - entry) / R, 1) if R > 0 else 0
    signal_date = row.get("signal_date") or "today"
    qty  = computed["qty"]
    cap_line = f"\n<b>Capital:</b> ₹{computed.get('qty', 0) * entry:,.0f}  ({qty} qty)" if qty else ""
    return (
        f"🚨 <b>IPO BREAKOUT FIRED — {sym}</b>\n"
        f"<i>{company}</i>\n\n"
        f"Close crossed 2-week high on <b>{signal_date}</b>!\n\n"
        f"<b>Entry:</b> ₹{entry}  |  <b>SL:</b> ₹{sl}  (R=₹{R})\n"
        f"<b>T1:</b> ₹{t1}  |  <b>T2:</b> ₹{t2}  |  <b>T3:</b> ₹{t3}\n"
        f"<b>R:R</b> = 1:{rr}{cap_line}\n\n"
        f"<a href='https://kite.zerodha.com/chart/web/ciq/NSE/{sym}/EQ'>📈 Chart</a>"
    )


# ── 9. Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    csv_url = _require_env("GSHEET_CSV_URL")
    state   = load_state()

    # Step 1 — Auto-add new IPOs from Chittorgarh (requires service account)
    sync_chittorgarh_to_sheet(csv_url)

    # Step 2 — Read the (now up-to-date) sheet
    ipo_list, capital_map = load_ipo_list(csv_url)
    if not ipo_list:
        print("[DONE] No active IPOs to track.")
        return

    ohlc_data    = fetch_all_ohlc(ipo_list)
    scanner_rows = IPOBreakoutStrategy.compute_scanner_states(ipo_list, ohlc_data)

    # Build computed data for every symbol (used for sheet write-back + alerts)
    sheet_data: dict[str, dict] = {}
    for row in scanner_rows:
        sym     = row["symbol"]
        bars    = ohlc_data.get(sym, [])
        capital = capital_map.get(sym, 0.0)
        sheet_data[sym] = build_sheet_row(row, bars, capital)

    # Send Telegram alerts for status changes
    alerts_sent = 0
    for row in scanner_rows:
        sym      = row["symbol"]
        status   = row["status"]
        prev     = state.get(sym, "")
        computed = sheet_data[sym]

        print(f"[SCAN] {sym}: {prev or 'NEW'} -> {status}  [{computed['status']}]")

        if status == "NEAR" and prev != "NEAR":
            if send_alert(build_near_message(row, computed)):
                alerts_sent += 1
        elif status == "FRESH" and prev != "FRESH":
            if send_alert(build_fresh_message(row, computed)):
                alerts_sent += 1

        state[sym] = status

    save_state(state)

    # Write all computed data back to Google Sheet
    write_sheet(csv_url, sheet_data)

    # ── EOD summary Telegram message ──────────────────────────────────────────
    import pytz
    from datetime import datetime
    ist      = pytz.timezone("Asia/Kolkata")
    run_time = datetime.now(ist).strftime("%d %b %Y, %I:%M %p IST")

    # Count statuses
    status_counts: dict[str, list[str]] = {}
    for sym, d in sheet_data.items():
        lbl = d["status"]
        status_counts.setdefault(lbl, []).append(sym)

    # Build status lines (only non-empty)
    STATUS_EMOJI = {
        "Entry Trigger": "🚨",
        "Near Breakout": "⚠️",
        "T3 Hit":        "🏆",
        "T2 Hit":        "✅",
        "T1 Hit":        "🟢",
        "SL Hit":        "🔴",
        "In Trade":      "🟡",
        "Entry Pending": "⏳",
        "Watching":      "👀",
        "Past":          "📦",
    }
    priority = ["Entry Trigger", "Near Breakout", "T3 Hit", "T2 Hit",
                "T1 Hit", "SL Hit", "In Trade", "Entry Pending", "Watching", "Past"]

    status_lines = ""
    for lbl in priority:
        syms = status_counts.get(lbl, [])
        if syms:
            emoji = STATUS_EMOJI.get(lbl, "•")
            status_lines += f"\n{emoji} <b>{lbl}</b>: {', '.join(syms)}"

    # Google Sheet URL
    sheet_id   = _extract_sheet_id(csv_url) or ""
    sheet_link = f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else csv_url

    summary = (
        f"✅ <b>IPO Scanner ran — {run_time}</b>\n"
        f"Scanned <b>{len(scanner_rows)}</b> IPOs  |  Alerts sent: <b>{alerts_sent}</b>\n"
        f"{status_lines}\n\n"
        f"<a href='{sheet_link}'>📊 Open Google Sheet</a>"
    )
    send_alert(summary)

    print(f"\n[DONE] Scanned {len(scanner_rows)} IPO(s). Alerts: {alerts_sent}")


if __name__ == "__main__":
    main()
