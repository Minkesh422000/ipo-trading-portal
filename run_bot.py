#!/usr/bin/env python
"""
run_bot.py — IPO Swing Trading Bot (standalone CLI runner)

Usage:
    python run_bot.py                # live mode: scan + place orders + track positions
    python run_bot.py --dry-run      # scan only, log signals but place NO orders
    python run_bot.py --test-notify  # send all Telegram alert types then exit
    python run_bot.py --scan-now     # run EOD scan immediately then exit (useful for testing)

Prerequisites:
    1. pip install -r requirements.txt
    2. Set env vars (or .streamlit/secrets.toml):
         TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
         ENCRYPTION_KEY (for Kite API secrets)
         DB_PATH (default: ipo_backtest.db)
    3. At least one Kite account logged in via the Streamlit app (Accounts page)
"""
from __future__ import annotations

import argparse
import logging
import sys

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("run_bot")


def _test_notifications() -> None:
    """Send all Telegram alert types and exit."""
    from core.notifier import (
        send_bot_startup_alert, send_auto_order_alert, send_target_hit_alert,
        send_sl_hit_alert, send_daily_summary, send_token_warning,
    )
    logger.info("Sending test notifications...")
    send_bot_startup_alert(accounts_count=2)
    send_auto_order_alert(
        symbol="TESTIPO", company="Test IPO Ltd",
        entry=100.0, sl=90.0, t1=110.0, t2=120.0, t3=130.0,
        qty=300, order_id="999999",
        gtt_sl_id=111, gtt_t1_id=222, gtt_t2_id=333,
    )
    send_target_hit_alert("TESTIPO", "T1", 110.0, 100.0, 10.0, new_sl=100.0)
    send_target_hit_alert("TESTIPO", "T2", 120.0, 100.0, 20.0, new_sl=110.0)
    send_target_hit_alert("TESTIPO", "T3", 130.0, 100.0, 30.0)
    send_sl_hit_alert("TESTIPO", 90.0, 100.0, -10.0)
    send_daily_summary(scanned=50, signals_fired=3, orders_placed=2)
    send_token_warning("acc_123", "My Zerodha Account")
    logger.info("All test notifications sent. Check your Telegram.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IPO Swing Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and detect signals but do NOT place any orders",
    )
    parser.add_argument(
        "--test-notify", action="store_true",
        help="Send test Telegram alerts for all notification types, then exit",
    )
    parser.add_argument(
        "--scan-now", action="store_true",
        help="Run the EOD scan immediately (skip IST scheduling), then exit",
    )
    args = parser.parse_args()

    # Test mode: send all alerts and exit
    if args.test_notify:
        _test_notifications()
        return

    # Init DB
    from core.db import init_db, DB_PATH
    logger.info("Connecting to database: %s", DB_PATH)
    conn = init_db(DB_PATH)

    if conn is None:
        logger.error("Failed to initialise database (Supabase mode requires network). Exiting.")
        sys.exit(1)

    # One-shot scan mode
    if args.scan_now:
        logger.info("Running immediate EOD scan (--scan-now)...")
        from core.scheduler import _run_eod_scan
        _run_eod_scan(conn, dry_run=args.dry_run)
        logger.info("Scan complete. Exiting.")
        return

    # Live scheduler loop
    if args.dry_run:
        logger.info("Starting in DRY-RUN mode — no orders will be placed.")
    else:
        logger.info("Starting in LIVE mode — orders will be placed on Kite.")

    from core.scheduler import run_loop
    run_loop(conn, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
