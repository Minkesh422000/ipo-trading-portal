"""
core/strategy_engine.py — Runs all active strategies across assigned accounts
and persists the generated signals to the DB.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from strategies import STRATEGY_REGISTRY


def run_all_strategies(
    conn,
    progress_cb=None,
) -> list[dict]:
    """
    1. Load all active strategies from DB
    2. For each strategy, load its account assignments
    3. Fetch required OHLC data
    4. Run strategy.generate_signals()
    5. Persist new signals to DB
    Returns list of signal dicts that were generated.
    """
    from core.db import (
        get_all_strategies, get_strategy_assignments, get_account,
        get_all_accounts, get_holdings, insert_signal,
    )
    from core.data_fetcher import fetch_all_ohlc
    from scraper import fetch_ipo_listings

    strategies = [s for s in get_all_strategies(conn) if s.get("is_active")]
    if not strategies:
        return []

    # Determine IPO date range: last 6 months of listings
    today = date.today()
    from_date = today - timedelta(days=180)

    # Fetch IPO list once (shared across all strategies)
    try:
        ipo_list = fetch_ipo_listings(from_date, today, conn)
    except Exception:
        ipo_list = []

    # Fetch OHLC for all symbols once
    if ipo_list:
        ohlc_data = fetch_all_ohlc(ipo_list, conn=conn)
    else:
        ohlc_data = {}

    all_signals = []
    total = len(strategies)

    for idx, strat_row in enumerate(strategies):
        if progress_cb:
            progress_cb(idx, total, strat_row["name"])

        strat_type = strat_row["type"]
        if strat_type not in STRATEGY_REGISTRY:
            continue

        strategy_cls = STRATEGY_REGISTRY[strat_type]
        strategy = strategy_cls()

        import json
        params = json.loads(strat_row.get("params_json") or "{}")

        assignments = get_strategy_assignments(conn, strat_row["id"])
        if not assignments:
            continue

        for assignment in assignments:
            account_id = assignment["account_id"]
            risk_pct = assignment.get("risk_pct", 0.01)
            capital_alloc = assignment.get("capital_alloc") or 1_000_000.0

            # Get current holdings to avoid double-buying
            existing_holdings = get_holdings(conn, account_id)

            try:
                signals = strategy.generate_signals(
                    ipo_list=ipo_list,
                    ohlc_data=ohlc_data,
                    params=params,
                    capital=capital_alloc,
                    risk_pct=risk_pct,
                    existing_holdings=existing_holdings,
                )
            except Exception:
                continue

            now = datetime.utcnow().isoformat()
            for sig in signals:
                signal_dict = {
                    "id": str(uuid.uuid4()),
                    "strategy_id": strat_row["id"],
                    "account_id": account_id,
                    "symbol": sig.symbol,
                    "company": sig.company,
                    "signal_type": sig.action,
                    "entry_price": sig.entry_price,
                    "sl_price": sig.sl_price,
                    "t1": sig.t1,
                    "t2": sig.t2,
                    "t3": sig.t3,
                    "quantity": sig.quantity,
                    "generated_at": now,
                    "status": "PENDING",
                    "order_id": None,
                    "notes": sig.reason,
                }
                insert_signal(conn, signal_dict)
                all_signals.append(signal_dict)

    if progress_cb:
        progress_cb(total, total, "Done")

    # Send Telegram alerts for newly generated signals
    if all_signals:
        try:
            from core.notifier import send_bulk_signal_alerts, is_configured
            if is_configured():
                send_bulk_signal_alerts(all_signals, source="Strategy")
        except Exception:
            pass  # never block signal generation due to notification failure

    return all_signals
