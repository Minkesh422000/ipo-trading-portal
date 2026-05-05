"""
core/position_tracker.py — Live position monitoring for the IPO swing bot.

Runs every 5 minutes during market hours (called by core/scheduler.py).

For each EXECUTED/PENDING_FILL signal it:
  1. Fetches current GTT statuses from Kite
  2. Detects which targets/SL have been hit based on GTT trigger state
  3. Updates SL GTT dynamically as targets fire:
       After T1 → cancel SL GTT, place new one for 2/3 qty at entry (breakeven)
       After T2 → cancel SL GTT, place new one for 1/3 qty at T1
       T3       → place LIMIT SELL at market for remaining 1/3
       SL hit   → cancel unfilled T1/T2 GTTs, mark STOPPED_OUT
  4. Sends Telegram alerts for every state change
  5. Persists state to DB

State machine per signal:
    PENDING_FILL → EXECUTED → T1_HIT → T2_HIT → T3_HIT
                                     ↘ STOPPED_OUT (at any stage)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_gtt_status(kite, gtt_id: Optional[int]) -> Optional[str]:
    """Return GTT status string from Kite ('active', 'triggered', 'cancelled', etc.)."""
    if gtt_id is None:
        return None
    try:
        gtt = kite.get_gtt(trigger_id=gtt_id)
        return gtt.get("status") if gtt else None
    except Exception:
        return None


def _fetch_ltp(kite, symbol: str) -> Optional[float]:
    """Return last traded price for NSE symbol."""
    try:
        data = kite.ltp([f"NSE:{symbol}"])
        return data.get(f"NSE:{symbol}", {}).get("last_price")
    except Exception:
        return None


def check_position_updates(conn, dry_run: bool = False) -> list[dict]:
    """
    Main position tracking loop. Checks all active signals and acts on state changes.

    Args:
        conn: DB connection
        dry_run: If True, detect events but do not place/cancel orders.

    Returns:
        List of event dicts describing what happened this cycle.
    """
    from core.db import (
        get_active_signals, update_signal_target_hit,
        update_signal_status, update_signal_gtt_ids,
    )
    from core.kite_manager import KiteManager
    from core.order_manager import update_sl_gtt, place_order, cancel_gtt, OrderError
    from core.notifier import send_target_hit_alert, send_sl_hit_alert

    signals = get_active_signals(conn)
    if not signals:
        return []

    events = []

    for sig in signals:
        signal_id = sig["id"]
        account_id = sig["account_id"]
        symbol = sig["symbol"]
        entry = sig["entry_price"]
        sl = sig["sl_price"]
        t1 = sig["t1"]
        t2 = sig["t2"]
        t3 = sig["t3"]
        qty = sig["quantity"]
        status = sig["status"]
        gtt_sl_id = sig.get("gtt_sl_id")
        gtt_t1_id = sig.get("gtt_t1_id")
        gtt_t2_id = sig.get("gtt_t2_id")

        kite = KiteManager.get_kite(account_id, conn)
        if kite is None:
            logger.warning("No Kite session for account %s — skipping signal %s", account_id, signal_id)
            continue

        ltp = _fetch_ltp(kite, symbol)
        if ltp is None:
            logger.warning("Could not fetch LTP for %s", symbol)
            continue

        t1_qty = qty // 3
        t2_qty = qty // 3
        runner_qty = qty - t1_qty - t2_qty

        # ── Check GTT statuses ───────────────────────────────────────────────
        sl_status  = _fetch_gtt_status(kite, gtt_sl_id)
        t1_status  = _fetch_gtt_status(kite, gtt_t1_id)
        t2_status  = _fetch_gtt_status(kite, gtt_t2_id)

        t1_triggered = (t1_status == "triggered")
        t2_triggered = (t2_status == "triggered")
        sl_triggered = (sl_status == "triggered")

        # ── SL hit (highest priority — stop everything) ──────────────────────
        if sl_triggered and status not in ("STOPPED_OUT", "T3_HIT"):
            hit_at = _now_iso()
            loss_pct = round((sl - entry) / entry * 100, 2) if entry else 0

            if not dry_run:
                # Cancel unfilled T1/T2 GTTs
                for gid in (gtt_t1_id, gtt_t2_id):
                    if gid and _fetch_gtt_status(kite, gid) == "active":
                        try:
                            cancel_gtt(account_id, gid, conn)
                        except Exception:
                            pass
                update_signal_target_hit(conn, signal_id, "SL", hit_at, "STOPPED_OUT")
                send_sl_hit_alert(symbol, sl, entry, loss_pct)

            events.append({
                "signal_id": signal_id, "symbol": symbol, "event": "SL_HIT",
                "price": sl, "loss_pct": loss_pct, "dry_run": dry_run,
            })
            logger.info("SL hit for %s (%.2f)", symbol, sl)
            continue

        # ── T1 hit for first time ────────────────────────────────────────────
        if t1_triggered and status == "EXECUTED":
            hit_at = _now_iso()
            pnl_pct = round((t1 - entry) / entry * 100, 2) if entry else 0

            if not dry_run:
                # Move SL to breakeven (entry price) for remaining 2/3 qty
                try:
                    new_gtt_id = update_sl_gtt(
                        account_id=account_id,
                        old_gtt_id=gtt_sl_id,
                        symbol=symbol,
                        new_qty=t2_qty + runner_qty,
                        new_sl=entry,         # breakeven
                        last_price=ltp,
                        conn=conn,
                        signal_id=signal_id,
                    )
                    update_signal_gtt_ids(conn, signal_id, gtt_sl_id=new_gtt_id)
                except OrderError as exc:
                    logger.error("Failed to update SL GTT after T1 for %s: %s", symbol, exc)

                update_signal_target_hit(conn, signal_id, "T1", hit_at, "T1_HIT")
                send_target_hit_alert(symbol, "T1", t1, entry, pnl_pct, new_sl=entry)

            events.append({
                "signal_id": signal_id, "symbol": symbol, "event": "T1_HIT",
                "price": t1, "pnl_pct": pnl_pct, "dry_run": dry_run,
            })
            logger.info("T1 hit for %s (%.2f) +%.1f%%", symbol, t1, pnl_pct)

        # ── T2 hit for first time ────────────────────────────────────────────
        if t2_triggered and status == "T1_HIT":
            hit_at = _now_iso()
            pnl_pct = round((t2 - entry) / entry * 100, 2) if entry else 0

            if not dry_run:
                # Move SL to T1 for remaining 1/3 qty
                current_gtt_sl = sig.get("gtt_sl_id")
                try:
                    new_gtt_id = update_sl_gtt(
                        account_id=account_id,
                        old_gtt_id=current_gtt_sl,
                        symbol=symbol,
                        new_qty=runner_qty,
                        new_sl=t1,            # SL to T1 after T2 hit
                        last_price=ltp,
                        conn=conn,
                        signal_id=signal_id,
                    )
                    update_signal_gtt_ids(conn, signal_id, gtt_sl_id=new_gtt_id)
                except OrderError as exc:
                    logger.error("Failed to update SL GTT after T2 for %s: %s", symbol, exc)

                update_signal_target_hit(conn, signal_id, "T2", hit_at, "T2_HIT")
                send_target_hit_alert(symbol, "T2", t2, entry, pnl_pct, new_sl=t1)

            events.append({
                "signal_id": signal_id, "symbol": symbol, "event": "T2_HIT",
                "price": t2, "pnl_pct": pnl_pct, "dry_run": dry_run,
            })
            logger.info("T2 hit for %s (%.2f) +%.1f%%", symbol, t2, pnl_pct)

        # ── T3 hit (detect via LTP — no GTT placed for T3, runner is free) ───
        if status == "T2_HIT" and t3 is not None and ltp >= t3:
            hit_at = _now_iso()
            pnl_pct = round((t3 - entry) / entry * 100, 2) if entry else 0

            if not dry_run and runner_qty > 0:
                # Place market SELL for runner position
                try:
                    place_order(
                        account_id=account_id,
                        symbol=symbol,
                        transaction_type="SELL",
                        quantity=runner_qty,
                        order_type="MARKET",
                        product="CNC",
                        conn=conn,
                        signal_id=signal_id,
                    )
                except OrderError as exc:
                    logger.error("Failed to place T3 SELL for %s: %s", symbol, exc)

                update_signal_target_hit(conn, signal_id, "T3", hit_at, "T3_HIT")
                send_target_hit_alert(symbol, "T3", t3, entry, pnl_pct, new_sl=None)

            events.append({
                "signal_id": signal_id, "symbol": symbol, "event": "T3_HIT",
                "price": t3, "pnl_pct": pnl_pct, "dry_run": dry_run,
            })
            logger.info("T3 hit for %s (%.2f) +%.1f%%", symbol, t3, pnl_pct)

    return events
