"""
core/scheduler.py — IST-aware market scheduler for the IPO swing bot.

Schedule:
  09:10 IST  — Morning token check + startup Telegram ping
  09:15–15:30 — Every 5 min: position tracker (target/SL monitoring)
  15:35 IST  — EOD scan: screen IPOs, place LIMIT orders for new signals

Run via:
    python run_bot.py [--dry-run] [--test-notify]
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime

import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# NSE trading holidays 2025 and 2026
NSE_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 26),   # Republic Day
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr (Ramzan Eid)
    date(2025, 4, 10),   # Shri Ram Navami
    date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    date(2025, 10, 2),   # Dussehra (same day — check NSE official calendar)
    date(2025, 10, 20),  # Diwali Laxmi Pujan
    date(2025, 10, 21),  # Diwali Balipratipada
    date(2025, 11, 5),   # Prakash Gurpurb Sri Guru Nanak Dev Ji
    date(2025, 12, 25),  # Christmas
    # 2026 (update when NSE publishes official calendar)
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 20),   # Holi (approximate — confirm)
    date(2026, 4, 3),    # Good Friday (approximate)
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 12, 25),  # Christmas
}


def is_market_day(d: date = None) -> bool:
    """Return True if d (default: today IST) is a trading day (Mon-Fri, not NSE holiday)."""
    if d is None:
        d = datetime.now(IST).date()
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d not in NSE_HOLIDAYS


def is_market_hours(now: datetime = None) -> bool:
    """Return True between 09:15 and 15:30 IST on a market day."""
    if now is None:
        now = datetime.now(IST)
    if not is_market_day(now.date()):
        return False
    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end   = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start <= now <= end


def _run_morning_check(conn, accounts: list[dict]) -> None:
    """Check Kite token validity and send startup Telegram alert."""
    from core.kite_manager import KiteManager
    from core.notifier import send_bot_startup_alert, send_token_warning

    valid_count = 0
    for acc in accounts:
        acc_id = acc["id"]
        if KiteManager.is_token_valid(acc_id, conn):
            valid_count += 1
        else:
            logger.warning("Token expired for account %s (%s)", acc_id, acc.get("nickname", ""))
            send_token_warning(acc_id, acc.get("nickname", ""))

    send_bot_startup_alert(accounts_count=valid_count)
    logger.info("Morning check done — %d/%d accounts valid", valid_count, len(accounts))


def _run_intraday_tracker(conn, dry_run: bool = False) -> None:
    """Run the position tracker (target/SL monitoring)."""
    from core.position_tracker import check_position_updates
    try:
        events = check_position_updates(conn, dry_run=dry_run)
        if events:
            logger.info("Position tracker: %d event(s) this cycle", len(events))
    except Exception as exc:
        logger.error("Position tracker error: %s", exc)


def _run_eod_scan(conn, dry_run: bool = False) -> None:
    """EOD scan: screen IPOs, place LIMIT orders for new signals."""
    import json
    from core.db import get_all_strategies, get_strategy_assignments, get_auto_execute_assignments
    from core.notifier import send_daily_summary
    from core.strategy_engine import run_all_strategies
    from core.order_manager import auto_place_ipo_order, OrderError
    from core.notifier import send_auto_order_alert

    logger.info("Starting EOD scan...")

    # Generate signals via strategy engine (persists to DB, sends bulk alert)
    try:
        run_all_strategies(conn)
    except Exception as exc:
        logger.error("Strategy engine error during EOD scan: %s", exc)
        return

    # Auto-place orders for assignments with auto_execute=1
    auto_assignments = get_auto_execute_assignments(conn)
    if not auto_assignments:
        logger.info("No auto-execute assignments configured — skipping order placement")
        send_daily_summary(scanned=0, signals_fired=0, orders_placed=0)
        return

    from core.db import get_pending_signals
    pending = get_pending_signals(conn)

    orders_placed = 0
    for sig in pending:
        acc_id = sig["account_id"]
        # Check if this account has auto_execute for this strategy
        auto_enabled = any(
            a["account_id"] == acc_id and a["strategy_id"] == sig["strategy_id"]
            for a in auto_assignments
        )
        if not auto_enabled:
            continue

        symbol = sig["symbol"]
        logger.info("Auto-placing order for %s (account %s)", symbol, acc_id)

        if dry_run:
            logger.info("[DRY RUN] Would place LIMIT BUY %s @ %.2f, SL %.2f",
                        symbol, sig["entry_price"], sig["sl_price"])
            orders_placed += 1
            continue

        try:
            result = auto_place_ipo_order(
                account_id=acc_id,
                symbol=symbol,
                qty=sig["quantity"],
                entry=sig["entry_price"],
                sl=sig["sl_price"],
                t1=sig["t1"],
                t2=sig["t2"],
                t3=sig["t3"],
                conn=conn,
                strategy_id=sig["strategy_id"],
                signal_id=sig["id"],
            )
            send_auto_order_alert(
                symbol=symbol,
                company=sig.get("company", symbol),
                entry=sig["entry_price"],
                sl=sig["sl_price"],
                t1=sig["t1"],
                t2=sig["t2"],
                t3=sig["t3"],
                qty=sig["quantity"],
                order_id=result["order_id"],
                gtt_sl_id=result.get("gtt_sl_id"),
                gtt_t1_id=result.get("gtt_t1_id"),
                gtt_t2_id=result.get("gtt_t2_id"),
            )
            orders_placed += 1
            if result.get("errors"):
                logger.warning("GTT errors for %s: %s", symbol, result["errors"])
        except OrderError as exc:
            logger.error("Order placement failed for %s: %s", symbol, exc)

    send_daily_summary(
        scanned=len(pending),
        signals_fired=len(pending),
        orders_placed=orders_placed,
    )
    logger.info("EOD scan complete — %d orders placed", orders_placed)


def run_loop(conn, dry_run: bool = False) -> None:
    """
    Main blocking scheduler loop.

    Wakes every 60 seconds, fires tasks based on IST time.
    Designed to run as a long-lived background process.
    """
    from core.db import get_all_accounts

    logger.info("Scheduler started (dry_run=%s). Ctrl+C to stop.", dry_run)

    last_morning_check = None
    last_tracker_run   = None
    last_eod_scan      = None

    while True:
        try:
            now = datetime.now(IST)
            today = now.date()

            if not is_market_day(today):
                time.sleep(60)
                continue

            accounts = get_all_accounts(conn)

            # Morning check at 09:10 IST (once per day)
            if now.hour == 9 and now.minute == 10 and last_morning_check != today:
                _run_morning_check(conn, accounts)
                last_morning_check = today

            # Intraday tracker every 5 min between 09:15 and 15:30
            if is_market_hours(now):
                if (last_tracker_run is None
                        or (now - last_tracker_run).seconds >= 300):  # 5 min
                    _run_intraday_tracker(conn, dry_run=dry_run)
                    last_tracker_run = now

            # EOD scan at 15:35 IST (once per day)
            if now.hour == 15 and now.minute == 35 and last_eod_scan != today:
                _run_eod_scan(conn, dry_run=dry_run)
                last_eod_scan = today

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
            break
        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc)

        time.sleep(60)
