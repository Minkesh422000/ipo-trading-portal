"""
core/data_fetcher.py — Unified OHLC data fetcher.

DATA_SOURCE=yfinance  → uses Yahoo Finance / yfinance (free, no auth, cloud-friendly)
DATA_SOURCE=kite      → uses Zerodha Kite API (paid, better quality for Indian markets)

Both modes save results to the ohlc_cache table so the cache is shared regardless
of which source was used to populate it.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta
from typing import Optional

DATA_SOURCE = os.getenv("DATA_SOURCE", "yfinance")


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def fetch_ohlc(
    symbol: str,
    from_date: date,
    to_date: date,
    conn=None,
    account_id: Optional[str] = None,
    force_refresh: bool = False,
) -> list[dict]:
    """
    Fetch daily OHLC for `symbol` between from_date and to_date.

    Checks local cache first (unless force_refresh).
    Fetches from yfinance or Kite based on DATA_SOURCE env var.
    Always upserts fetched rows into ohlc_cache.

    Returns list of {date, open, high, low, close, volume} dicts sorted by date.
    """
    from core.db import get_ohlc, is_ohlc_cached, upsert_ohlc_rows

    from_str = from_date.isoformat()
    to_str = to_date.isoformat()

    if not force_refresh and conn is not None and is_ohlc_cached(conn, symbol, from_str, to_str):
        return get_ohlc(conn, symbol, from_str, to_str)

    if DATA_SOURCE == "kite":
        rows = _fetch_kite(symbol, from_date, to_date, account_id, conn)
    else:
        rows = _fetch_yfinance(symbol, from_date, to_date)

    if rows and conn is not None:
        upsert_ohlc_rows(conn, symbol, rows)

    return rows


def fetch_all_ohlc(
    ipo_list: list[dict],
    conn=None,
    force_refresh: bool = False,
    progress_cb=None,
) -> dict[str, list[dict]]:
    """
    Fetch OHLC for all IPOs in ipo_list.
    Skips symbols with no NSE symbol or already fully cached.
    Returns {symbol: [bar_dicts]} mapping.
    """
    result: dict[str, list[dict]] = {}
    items = [ipo for ipo in ipo_list if ipo.get("nse_symbol")]
    total = len(items)

    for i, ipo in enumerate(items):
        sym = ipo["nse_symbol"]
        listing_date = ipo["listing_date"]
        if isinstance(listing_date, str):
            listing_date = date.fromisoformat(listing_date)
        fetch_to = min(date.today(), listing_date + timedelta(days=365))

        try:
            bars = fetch_ohlc(sym, listing_date, fetch_to, conn=conn, force_refresh=force_refresh)
            result[sym] = bars
        except Exception:
            result[sym] = []

        if progress_cb:
            progress_cb(i + 1, total)

        # Rate-limit courtesy pause between fetches
        if DATA_SOURCE == "yfinance":
            time.sleep(0.1)
        else:
            time.sleep(0.35)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# yfinance backend
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_yfinance(symbol: str, from_date: date, to_date: date) -> list[dict]:
    """Fetch from Yahoo Finance using NSE suffix (.NS)."""
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("yfinance not installed. Run: pip install yfinance")

    ticker = yf.Ticker(f"{symbol}.NS")
    # yfinance end date is exclusive — add 1 day
    end = (to_date + timedelta(days=1)).isoformat()
    df = ticker.history(start=from_date.isoformat(), end=end, interval="1d", auto_adjust=True)

    if df is None or df.empty:
        return []

    rows = []
    for ts, row in df.iterrows():
        try:
            bar_date = ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10])
            rows.append({
                "date": bar_date.isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row.get("Volume", 0)),
            })
        except (KeyError, ValueError):
            continue

    rows.sort(key=lambda x: x["date"])
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Kite API backend
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_kite(
    symbol: str,
    from_date: date,
    to_date: date,
    account_id: Optional[str],
    conn,
) -> list[dict]:
    """Fetch from Zerodha Kite API using the first available active account."""
    from core.kite_manager import KiteManager

    kite = None
    if account_id:
        kite = KiteManager.get_kite(account_id, conn)

    if kite is None:
        # Fall back to first active account
        from core.db import get_all_accounts
        accounts = get_all_accounts(conn)
        for acc in accounts:
            kite = KiteManager.get_kite(acc["id"], conn)
            if kite is not None:
                break

    if kite is None:
        raise RuntimeError("No active Kite session found. Please log in to at least one account.")

    # Resolve instrument token
    from core.db import get_instrument_token, upsert_instrument_token, get_instruments_dump, upsert_instruments_dump

    token = get_instrument_token(conn, symbol)
    if token is None:
        instruments = get_instruments_dump(conn)
        if instruments is None:
            instruments = kite.instruments("NSE")
            upsert_instruments_dump(conn, instruments)

        candidates = [symbol, symbol.replace("-", ""), symbol + "-EQ"]
        for candidate in candidates:
            match = next(
                (i for i in instruments
                 if i["tradingsymbol"] == candidate.upper() and i["instrument_type"] == "EQ"),
                None,
            )
            if match:
                token = match["instrument_token"]
                upsert_instrument_token(conn, symbol, token, "NSE")
                break

    if token is None:
        return []

    # Fetch historical data with retry
    from kiteconnect import exceptions as kite_exc

    for attempt in range(3):
        try:
            raw = kite.historical_data(token, from_date, to_date, "day", continuous=False, oi=False)
            break
        except kite_exc.NetworkException:
            if attempt == 2:
                return []
            time.sleep(2 ** attempt)
        except Exception:
            return []

    rows = []
    for bar in raw:
        bar_date = bar["date"]
        if hasattr(bar_date, "date"):
            bar_date = bar_date.date()
        rows.append({
            "date": bar_date.isoformat() if hasattr(bar_date, "isoformat") else str(bar_date),
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": float(bar["close"]),
            "volume": int(bar.get("volume", 0)),
        })

    return rows
