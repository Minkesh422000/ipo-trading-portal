"""
core/db.py — Dual-mode database layer.

DATABASE_MODE=sqlite  → uses local SQLite (default for local dev)
DATABASE_MODE=supabase → uses Supabase PostgreSQL (for cloud deployment)

The public interface is identical in both modes so callers never need
to know which backend is in use.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

# ── Configuration ─────────────────────────────────────────────────────────────
DATABASE_MODE = os.getenv("DATABASE_MODE", "sqlite")
DB_PATH = os.getenv("DB_PATH", "ipo_backtest.db")
INSTRUMENTS_DUMP_TTL_HOURS = 24

# Lazy Supabase client (only imported when needed)
_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _supabase_client = create_client(url, key)
    return _supabase_client


# ══════════════════════════════════════════════════════════════════════════════
# SQLite backend
# ══════════════════════════════════════════════════════════════════════════════

def init_db(db_path: str = DB_PATH) -> Optional[sqlite3.Connection]:
    """Create all tables and return a connection (SQLite mode only)."""
    if DATABASE_MODE == "supabase":
        _ensure_supabase_tables()
        return None  # callers must handle None conn in supabase mode

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        -- ── Existing tables ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS ohlc_cache (
            symbol  TEXT,
            date    TEXT,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  INTEGER,
            PRIMARY KEY (symbol, date)
        );
        CREATE TABLE IF NOT EXISTS instrument_cache (
            symbol           TEXT PRIMARY KEY,
            instrument_token INTEGER,
            exchange         TEXT,
            fetched_at       TEXT
        );
        CREATE TABLE IF NOT EXISTS instruments_dump (
            fetched_date TEXT PRIMARY KEY,
            payload      TEXT
        );
        CREATE TABLE IF NOT EXISTS scrape_cache (
            year       INTEGER PRIMARY KEY,
            payload    TEXT,
            scraped_at TEXT
        );

        -- ── New v2 tables ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS accounts (
            id                  TEXT PRIMARY KEY,
            nickname            TEXT NOT NULL,
            kite_api_key        TEXT NOT NULL,
            kite_api_secret     TEXT NOT NULL,
            kite_user_id        TEXT,
            access_token        TEXT,
            token_generated_at  TEXT,
            is_active           INTEGER DEFAULT 1,
            created_at          TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS holdings (
            account_id      TEXT,
            symbol          TEXT,
            quantity        INTEGER,
            average_price   REAL,
            last_price      REAL,
            pnl             REAL,
            pnl_pct         REAL,
            fetched_at      TEXT,
            PRIMARY KEY (account_id, symbol)
        );
        CREATE TABLE IF NOT EXISTS positions (
            account_id      TEXT,
            symbol          TEXT,
            quantity        INTEGER,
            average_price   REAL,
            last_price      REAL,
            pnl             REAL,
            product         TEXT,
            fetched_at      TEXT,
            PRIMARY KEY (account_id, symbol)
        );
        CREATE TABLE IF NOT EXISTS margins (
            account_id      TEXT PRIMARY KEY,
            available_cash  REAL,
            used_margin     REAL,
            total_balance   REAL,
            fetched_at      TEXT
        );
        CREATE TABLE IF NOT EXISTS strategies (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL,
            description TEXT,
            params_json TEXT,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS strategy_assignments (
            strategy_id  TEXT,
            account_id   TEXT,
            risk_pct     REAL DEFAULT 0.01,
            capital_alloc REAL,
            is_active    INTEGER DEFAULT 1,
            PRIMARY KEY (strategy_id, account_id)
        );
        CREATE TABLE IF NOT EXISTS signals (
            id           TEXT PRIMARY KEY,
            strategy_id  TEXT,
            account_id   TEXT,
            symbol       TEXT,
            company      TEXT,
            signal_type  TEXT,
            entry_price  REAL,
            sl_price     REAL,
            t1 REAL, t2 REAL, t3 REAL,
            quantity     INTEGER,
            generated_at TEXT,
            status       TEXT DEFAULT 'PENDING',
            order_id     TEXT,
            notes        TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id               TEXT PRIMARY KEY,
            account_id       TEXT,
            kite_order_id    TEXT,
            symbol           TEXT,
            transaction_type TEXT,
            quantity         INTEGER,
            order_type       TEXT,
            price            REAL,
            trigger_price    REAL,
            product          TEXT,
            status           TEXT,
            placed_at        TEXT,
            strategy_id      TEXT,
            signal_id        TEXT
        );
        CREATE TABLE IF NOT EXISTS gtt_orders (
            id              TEXT PRIMARY KEY,
            account_id      TEXT,
            kite_gtt_id     INTEGER,
            symbol          TEXT,
            upper_trigger   REAL,
            lower_trigger   REAL,
            quantity        INTEGER,
            status          TEXT,
            created_at      TEXT,
            signal_id       TEXT
        );
    """)
    conn.commit()
    _run_migrations(conn)
    return conn


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply incremental ALTER TABLE migrations safely (idempotent)."""
    migrations = [
        # v2 bot additions to signals
        "ALTER TABLE signals ADD COLUMN t1_hit_at TEXT",
        "ALTER TABLE signals ADD COLUMN t2_hit_at TEXT",
        "ALTER TABLE signals ADD COLUMN t3_hit_at TEXT",
        "ALTER TABLE signals ADD COLUMN sl_hit_at TEXT",
        "ALTER TABLE signals ADD COLUMN kite_order_id TEXT",
        "ALTER TABLE signals ADD COLUMN gtt_sl_id INTEGER",
        "ALTER TABLE signals ADD COLUMN gtt_t1_id INTEGER",
        "ALTER TABLE signals ADD COLUMN gtt_t2_id INTEGER",
        # v2 bot addition to strategy_assignments
        "ALTER TABLE strategy_assignments ADD COLUMN auto_execute INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass  # column already exists — skip silently
    conn.commit()


def _ensure_supabase_tables():
    """Supabase tables must be created via Supabase dashboard SQL editor.
    This function just validates the connection."""
    _get_supabase()  # will raise if credentials missing


# ══════════════════════════════════════════════════════════════════════════════
# OHLC cache
# ══════════════════════════════════════════════════════════════════════════════

def upsert_ohlc_rows(conn: Optional[sqlite3.Connection], symbol: str, rows: list[dict]) -> None:
    if DATABASE_MODE == "supabase":
        sb = _get_supabase()
        records = [{"symbol": symbol, **r} for r in rows]
        sb.table("ohlc_cache").upsert(records).execute()
        return
    conn.executemany(
        "INSERT OR REPLACE INTO ohlc_cache (symbol, date, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(symbol, r["date"], r["open"], r["high"], r["low"], r["close"], r.get("volume", 0))
         for r in rows],
    )
    conn.commit()


def get_ohlc(conn: Optional[sqlite3.Connection], symbol: str, from_date: str, to_date: str) -> list[dict]:
    if DATABASE_MODE == "supabase":
        sb = _get_supabase()
        res = (sb.table("ohlc_cache")
               .select("date,open,high,low,close,volume")
               .eq("symbol", symbol)
               .gte("date", from_date)
               .lte("date", to_date)
               .order("date")
               .execute())
        return res.data or []
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM ohlc_cache "
        "WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
        (symbol, from_date, to_date),
    ).fetchall()
    return [dict(r) for r in rows]


def is_ohlc_cached(conn: Optional[sqlite3.Connection], symbol: str, from_date: str, to_date: str) -> bool:
    if DATABASE_MODE == "supabase":
        sb = _get_supabase()
        res = (sb.table("ohlc_cache")
               .select("date")
               .eq("symbol", symbol)
               .gte("date", from_date)
               .lte("date", to_date)
               .order("date", desc=True)
               .limit(1)
               .execute())
        if not res.data:
            return False
        return res.data[0]["date"] >= to_date
    row = conn.execute(
        "SELECT MAX(date) as max_date, COUNT(*) as cnt FROM ohlc_cache "
        "WHERE symbol = ? AND date >= ? AND date <= ?",
        (symbol, from_date, to_date),
    ).fetchone()
    if not row or not row["max_date"]:
        return False
    return row["max_date"] >= to_date and row["cnt"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# Instrument cache
# ══════════════════════════════════════════════════════════════════════════════

def get_instrument_token(conn: Optional[sqlite3.Connection], symbol: str) -> Optional[int]:
    if DATABASE_MODE == "supabase":
        sb = _get_supabase()
        res = sb.table("instrument_cache").select("instrument_token").eq("symbol", symbol).execute()
        return res.data[0]["instrument_token"] if res.data else None
    row = conn.execute(
        "SELECT instrument_token FROM instrument_cache WHERE symbol = ?", (symbol,)
    ).fetchone()
    return row["instrument_token"] if row else None


def upsert_instrument_token(conn: Optional[sqlite3.Connection], symbol: str, token: int, exchange: str) -> None:
    now = datetime.utcnow().isoformat()
    if DATABASE_MODE == "supabase":
        _get_supabase().table("instrument_cache").upsert({
            "symbol": symbol, "instrument_token": token,
            "exchange": exchange, "fetched_at": now,
        }).execute()
        return
    conn.execute(
        "INSERT OR REPLACE INTO instrument_cache (symbol, instrument_token, exchange, fetched_at) "
        "VALUES (?, ?, ?, ?)", (symbol, token, exchange, now),
    )
    conn.commit()


def get_instruments_dump(conn: Optional[sqlite3.Connection]) -> Optional[list]:
    cutoff = (datetime.utcnow() - timedelta(hours=INSTRUMENTS_DUMP_TTL_HOURS)).date().isoformat()
    if DATABASE_MODE == "supabase":
        res = (sb.table("instruments_dump")
               .select("payload")
               .gte("fetched_date", cutoff)
               .order("fetched_date", desc=True)
               .limit(1)
               .execute())
        return json.loads(res.data[0]["payload"]) if res.data else None
    row = conn.execute(
        "SELECT payload FROM instruments_dump WHERE fetched_date >= ? ORDER BY fetched_date DESC LIMIT 1",
        (cutoff,),
    ).fetchone()
    return json.loads(row["payload"]) if row else None


def upsert_instruments_dump(conn: Optional[sqlite3.Connection], instruments: list[dict]) -> None:
    today = date.today().isoformat()
    payload = json.dumps(instruments)
    if DATABASE_MODE == "supabase":
        _get_supabase().table("instruments_dump").upsert({"fetched_date": today, "payload": payload}).execute()
        return
    conn.execute(
        "INSERT OR REPLACE INTO instruments_dump (fetched_date, payload) VALUES (?, ?)",
        (today, payload),
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Scrape cache
# ══════════════════════════════════════════════════════════════════════════════

def get_scrape_cache(conn: Optional[sqlite3.Connection], year: int) -> Optional[list]:
    if DATABASE_MODE == "supabase":
        sb = _get_supabase()
        res = sb.table("scrape_cache").select("payload").eq("year", year).execute()
        return json.loads(res.data[0]["payload"]) if res.data else None
    row = conn.execute("SELECT payload FROM scrape_cache WHERE year = ?", (year,)).fetchone()
    return json.loads(row["payload"]) if row else None


def upsert_scrape_cache(conn: Optional[sqlite3.Connection], year: int, ipo_list: list[dict]) -> None:
    serialisable = []
    for ipo in ipo_list:
        entry = dict(ipo)
        if isinstance(entry.get("listing_date"), date):
            entry["listing_date"] = entry["listing_date"].isoformat()
        serialisable.append(entry)
    now = datetime.utcnow().isoformat()
    payload = json.dumps(serialisable)
    if DATABASE_MODE == "supabase":
        _get_supabase().table("scrape_cache").upsert(
            {"year": year, "payload": payload, "scraped_at": now}
        ).execute()
        return
    conn.execute(
        "INSERT OR REPLACE INTO scrape_cache (year, payload, scraped_at) VALUES (?, ?, ?)",
        (year, payload, now),
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Accounts
# ══════════════════════════════════════════════════════════════════════════════

def get_all_accounts(conn: Optional[sqlite3.Connection]) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = _get_supabase().table("accounts").select("*").eq("is_active", 1).execute()
        return res.data or []
    rows = conn.execute("SELECT * FROM accounts WHERE is_active = 1").fetchall()
    return [dict(r) for r in rows]


def get_account(conn: Optional[sqlite3.Connection], account_id: str) -> Optional[dict]:
    if DATABASE_MODE == "supabase":
        res = _get_supabase().table("accounts").select("*").eq("id", account_id).execute()
        return res.data[0] if res.data else None
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def upsert_account(conn: Optional[sqlite3.Connection], account: dict) -> None:
    if DATABASE_MODE == "supabase":
        _get_supabase().table("accounts").upsert(account).execute()
        return
    conn.execute("""
        INSERT OR REPLACE INTO accounts
        (id, nickname, kite_api_key, kite_api_secret, kite_user_id,
         access_token, token_generated_at, is_active, created_at)
        VALUES (:id, :nickname, :kite_api_key, :kite_api_secret, :kite_user_id,
                :access_token, :token_generated_at, :is_active, :created_at)
    """, account)
    conn.commit()


def update_account_token(conn: Optional[sqlite3.Connection], account_id: str,
                         access_token: str, kite_user_id: str = None) -> None:
    now = datetime.utcnow().isoformat()
    if DATABASE_MODE == "supabase":
        updates = {"access_token": access_token, "token_generated_at": now}
        if kite_user_id:
            updates["kite_user_id"] = kite_user_id
        _get_supabase().table("accounts").update(updates).eq("id", account_id).execute()
        return
    if kite_user_id:
        conn.execute(
            "UPDATE accounts SET access_token=?, token_generated_at=?, kite_user_id=? WHERE id=?",
            (access_token, now, kite_user_id, account_id),
        )
    else:
        conn.execute(
            "UPDATE accounts SET access_token=?, token_generated_at=? WHERE id=?",
            (access_token, now, account_id),
        )
    conn.commit()


def delete_account(conn: Optional[sqlite3.Connection], account_id: str) -> None:
    if DATABASE_MODE == "supabase":
        _get_supabase().table("accounts").update({"is_active": 0}).eq("id", account_id).execute()
        return
    conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (account_id,))
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Holdings / Positions / Margins
# ══════════════════════════════════════════════════════════════════════════════

def upsert_holdings(conn: Optional[sqlite3.Connection], account_id: str, holdings: list[dict]) -> None:
    now = datetime.utcnow().isoformat()
    if DATABASE_MODE == "supabase":
        records = [{"account_id": account_id, "fetched_at": now, **h} for h in holdings]
        _get_supabase().table("holdings").upsert(records).execute()
        return
    conn.execute("DELETE FROM holdings WHERE account_id = ?", (account_id,))
    conn.executemany("""
        INSERT INTO holdings (account_id, symbol, quantity, average_price, last_price, pnl, pnl_pct, fetched_at)
        VALUES (:account_id, :symbol, :quantity, :average_price, :last_price, :pnl, :pnl_pct, :fetched_at)
    """, [{"account_id": account_id, "fetched_at": now, **h} for h in holdings])
    conn.commit()


def get_holdings(conn: Optional[sqlite3.Connection], account_id: str) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = _get_supabase().table("holdings").select("*").eq("account_id", account_id).execute()
        return res.data or []
    rows = conn.execute("SELECT * FROM holdings WHERE account_id = ?", (account_id,)).fetchall()
    return [dict(r) for r in rows]


def upsert_positions(conn: Optional[sqlite3.Connection], account_id: str, positions: list[dict]) -> None:
    now = datetime.utcnow().isoformat()
    if DATABASE_MODE == "supabase":
        records = [{"account_id": account_id, "fetched_at": now, **p} for p in positions]
        _get_supabase().table("positions").upsert(records).execute()
        return
    conn.execute("DELETE FROM positions WHERE account_id = ?", (account_id,))
    conn.executemany("""
        INSERT INTO positions (account_id, symbol, quantity, average_price, last_price, pnl, product, fetched_at)
        VALUES (:account_id, :symbol, :quantity, :average_price, :last_price, :pnl, :product, :fetched_at)
    """, [{"account_id": account_id, "fetched_at": now, **p} for p in positions])
    conn.commit()


def get_positions(conn: Optional[sqlite3.Connection], account_id: str) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = _get_supabase().table("positions").select("*").eq("account_id", account_id).execute()
        return res.data or []
    rows = conn.execute("SELECT * FROM positions WHERE account_id = ?", (account_id,)).fetchall()
    return [dict(r) for r in rows]


def upsert_margins(conn: Optional[sqlite3.Connection], account_id: str, margins: dict) -> None:
    now = datetime.utcnow().isoformat()
    record = {"account_id": account_id, "fetched_at": now, **margins}
    if DATABASE_MODE == "supabase":
        _get_supabase().table("margins").upsert(record).execute()
        return
    conn.execute("""
        INSERT OR REPLACE INTO margins (account_id, available_cash, used_margin, total_balance, fetched_at)
        VALUES (:account_id, :available_cash, :used_margin, :total_balance, :fetched_at)
    """, record)
    conn.commit()


def get_margins(conn: Optional[sqlite3.Connection], account_id: str) -> Optional[dict]:
    if DATABASE_MODE == "supabase":
        res = _get_supabase().table("margins").select("*").eq("account_id", account_id).execute()
        return res.data[0] if res.data else None
    row = conn.execute("SELECT * FROM margins WHERE account_id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
# Strategies
# ══════════════════════════════════════════════════════════════════════════════

def get_all_strategies(conn: Optional[sqlite3.Connection]) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = _get_supabase().table("strategies").select("*").execute()
        return res.data or []
    rows = conn.execute("SELECT * FROM strategies").fetchall()
    return [dict(r) for r in rows]


def upsert_strategy(conn: Optional[sqlite3.Connection], strategy: dict) -> None:
    if DATABASE_MODE == "supabase":
        _get_supabase().table("strategies").upsert(strategy).execute()
        return
    conn.execute("""
        INSERT OR REPLACE INTO strategies (id, name, type, description, params_json, is_active, created_at)
        VALUES (:id, :name, :type, :description, :params_json, :is_active, :created_at)
    """, strategy)
    conn.commit()


def get_strategy_assignments(conn: Optional[sqlite3.Connection], strategy_id: str) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = (_get_supabase().table("strategy_assignments")
               .select("*").eq("strategy_id", strategy_id).eq("is_active", 1).execute())
        return res.data or []
    rows = conn.execute(
        "SELECT * FROM strategy_assignments WHERE strategy_id = ? AND is_active = 1",
        (strategy_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_strategy_assignment(conn: Optional[sqlite3.Connection], assignment: dict) -> None:
    if DATABASE_MODE == "supabase":
        sb = _get_supabase()
        try:
            sb.table("strategy_assignments").upsert(assignment).execute()
        except Exception:
            # Fallback: retry without auto_execute in case column not yet added in Supabase
            fallback = {k: v for k, v in assignment.items() if k != "auto_execute"}
            sb.table("strategy_assignments").upsert(fallback).execute()
        return
    conn.execute("""
        INSERT OR REPLACE INTO strategy_assignments
        (strategy_id, account_id, risk_pct, capital_alloc, is_active, auto_execute)
        VALUES (:strategy_id, :account_id, :risk_pct, :capital_alloc, :is_active, :auto_execute)
    """, {**assignment, "auto_execute": assignment.get("auto_execute", 0)})
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Signals
# ══════════════════════════════════════════════════════════════════════════════

def insert_signal(conn: Optional[sqlite3.Connection], signal: dict) -> None:
    if DATABASE_MODE == "supabase":
        _get_supabase().table("signals").insert(signal).execute()
        return
    conn.execute("""
        INSERT OR REPLACE INTO signals
        (id, strategy_id, account_id, symbol, company, signal_type,
         entry_price, sl_price, t1, t2, t3, quantity, generated_at, status, order_id, notes)
        VALUES (:id, :strategy_id, :account_id, :symbol, :company, :signal_type,
                :entry_price, :sl_price, :t1, :t2, :t3, :quantity, :generated_at, :status, :order_id, :notes)
    """, signal)
    conn.commit()


def get_pending_signals(conn: Optional[sqlite3.Connection], account_id: str = None) -> list[dict]:
    if DATABASE_MODE == "supabase":
        q = _get_supabase().table("signals").select("*").eq("status", "PENDING")
        if account_id:
            q = q.eq("account_id", account_id)
        return (q.order("generated_at", desc=True).execute()).data or []
    if account_id:
        rows = conn.execute(
            "SELECT * FROM signals WHERE status='PENDING' AND account_id=? ORDER BY generated_at DESC",
            (account_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM signals WHERE status='PENDING' ORDER BY generated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_signal_status(conn: Optional[sqlite3.Connection], signal_id: str,
                         status: str, order_id: str = None) -> None:
    if DATABASE_MODE == "supabase":
        updates = {"status": status}
        if order_id:
            updates["order_id"] = order_id
        _get_supabase().table("signals").update(updates).eq("id", signal_id).execute()
        return
    if order_id:
        conn.execute("UPDATE signals SET status=?, order_id=? WHERE id=?", (status, order_id, signal_id))
    else:
        conn.execute("UPDATE signals SET status=? WHERE id=?", (status, signal_id))
    conn.commit()


def get_signal_history(conn: Optional[sqlite3.Connection], limit: int = 50) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = (_get_supabase().table("signals").select("*")
               .order("generated_at", desc=True).limit(limit).execute())
        return res.data or []
    rows = conn.execute(
        "SELECT * FROM signals ORDER BY generated_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# Orders
# ══════════════════════════════════════════════════════════════════════════════

def insert_order(conn: Optional[sqlite3.Connection], order: dict) -> None:
    if DATABASE_MODE == "supabase":
        _get_supabase().table("orders").insert(order).execute()
        return
    conn.execute("""
        INSERT OR REPLACE INTO orders
        (id, account_id, kite_order_id, symbol, transaction_type, quantity,
         order_type, price, trigger_price, product, status, placed_at, strategy_id, signal_id)
        VALUES (:id, :account_id, :kite_order_id, :symbol, :transaction_type, :quantity,
                :order_type, :price, :trigger_price, :product, :status, :placed_at, :strategy_id, :signal_id)
    """, order)
    conn.commit()


def get_orders(conn: Optional[sqlite3.Connection], account_id: str, limit: int = 100) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = (_get_supabase().table("orders").select("*")
               .eq("account_id", account_id)
               .order("placed_at", desc=True).limit(limit).execute())
        return res.data or []
    rows = conn.execute(
        "SELECT * FROM orders WHERE account_id=? ORDER BY placed_at DESC LIMIT ?",
        (account_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# GTT Orders
# ══════════════════════════════════════════════════════════════════════════════

def insert_gtt(conn: Optional[sqlite3.Connection], gtt: dict) -> None:
    if DATABASE_MODE == "supabase":
        _get_supabase().table("gtt_orders").insert(gtt).execute()
        return
    conn.execute("""
        INSERT OR REPLACE INTO gtt_orders
        (id, account_id, kite_gtt_id, symbol, upper_trigger, lower_trigger, quantity, status, created_at, signal_id)
        VALUES (:id, :account_id, :kite_gtt_id, :symbol, :upper_trigger, :lower_trigger, :quantity, :status, :created_at, :signal_id)
    """, gtt)
    conn.commit()


def get_gtts(conn: Optional[sqlite3.Connection], account_id: str) -> list[dict]:
    if DATABASE_MODE == "supabase":
        res = (_get_supabase().table("gtt_orders").select("*")
               .eq("account_id", account_id).order("created_at", desc=True).execute())
        return res.data or []
    rows = conn.execute(
        "SELECT * FROM gtt_orders WHERE account_id=? ORDER BY created_at DESC", (account_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def update_gtt_status(conn: Optional[sqlite3.Connection], kite_gtt_id: int, status: str) -> None:
    if DATABASE_MODE == "supabase":
        _get_supabase().table("gtt_orders").update({"status": status}).eq("kite_gtt_id", kite_gtt_id).execute()
        return
    conn.execute("UPDATE gtt_orders SET status=? WHERE kite_gtt_id=?", (status, kite_gtt_id))
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Bot-specific signal functions
# ══════════════════════════════════════════════════════════════════════════════

def get_active_signals(conn: Optional[sqlite3.Connection], account_id: str = None) -> list[dict]:
    """Return signals in EXECUTED or PENDING_FILL status (live positions being tracked)."""
    active_statuses = ("EXECUTED", "PENDING_FILL", "T1_HIT", "T2_HIT")
    placeholders = ",".join("?" for _ in active_statuses)
    if DATABASE_MODE == "supabase":
        q = (_get_supabase().table("signals").select("*")
             .in_("status", list(active_statuses)))
        if account_id:
            q = q.eq("account_id", account_id)
        return (q.order("generated_at", desc=True).execute()).data or []
    if account_id:
        rows = conn.execute(
            f"SELECT * FROM signals WHERE status IN ({placeholders}) AND account_id=? ORDER BY generated_at DESC",
            (*active_statuses, account_id),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM signals WHERE status IN ({placeholders}) ORDER BY generated_at DESC",
            active_statuses,
        ).fetchall()
    return [dict(r) for r in rows]


def update_signal_target_hit(
    conn: Optional[sqlite3.Connection],
    signal_id: str,
    target: str,          # "T1", "T2", "T3", or "SL"
    hit_at: str,          # ISO timestamp
    new_status: str,      # "T1_HIT", "T2_HIT", "T3_HIT", "STOPPED_OUT"
) -> None:
    col = f"{target.lower()}_hit_at"
    if DATABASE_MODE == "supabase":
        _get_supabase().table("signals").update({col: hit_at, "status": new_status}).eq("id", signal_id).execute()
        return
    conn.execute(f"UPDATE signals SET {col}=?, status=? WHERE id=?", (hit_at, new_status, signal_id))
    conn.commit()


def update_signal_gtt_ids(
    conn: Optional[sqlite3.Connection],
    signal_id: str,
    gtt_sl_id: Optional[int] = None,
    gtt_t1_id: Optional[int] = None,
    gtt_t2_id: Optional[int] = None,
    kite_order_id: Optional[str] = None,
) -> None:
    """Persist GTT IDs and entry order ID on a signal after auto-placement."""
    updates: dict = {}
    if gtt_sl_id is not None:
        updates["gtt_sl_id"] = gtt_sl_id
    if gtt_t1_id is not None:
        updates["gtt_t1_id"] = gtt_t1_id
    if gtt_t2_id is not None:
        updates["gtt_t2_id"] = gtt_t2_id
    if kite_order_id is not None:
        updates["kite_order_id"] = kite_order_id
    if not updates:
        return
    if DATABASE_MODE == "supabase":
        _get_supabase().table("signals").update(updates).eq("id", signal_id).execute()
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE signals SET {set_clause} WHERE id=?",
        (*updates.values(), signal_id),
    )
    conn.commit()


def delete_strategy_assignment(conn: Optional[sqlite3.Connection], strategy_id: str, account_id: str) -> None:
    if DATABASE_MODE == "supabase":
        (_get_supabase().table("strategy_assignments")
         .delete()
         .eq("strategy_id", strategy_id)
         .eq("account_id", account_id)
         .execute())
        return
    conn.execute(
        "DELETE FROM strategy_assignments WHERE strategy_id=? AND account_id=?",
        (strategy_id, account_id),
    )
    conn.commit()


def get_auto_execute_assignments(conn: Optional[sqlite3.Connection]) -> list[dict]:
    """Return strategy assignments with auto_execute=1 across all active strategies."""
    if DATABASE_MODE == "supabase":
        res = (_get_supabase().table("strategy_assignments")
               .select("*").eq("is_active", 1).eq("auto_execute", 1).execute())
        return res.data or []
    rows = conn.execute(
        "SELECT * FROM strategy_assignments WHERE is_active=1 AND auto_execute=1"
    ).fetchall()
    return [dict(r) for r in rows]
