"""
core/notifier.py — Telegram notification module.

Sends trade signal alerts to a Telegram chat via Bot API.
No extra library needed — uses requests (already in requirements.txt).

Setup:
  1. Create a bot via @BotFather on Telegram → get TELEGRAM_BOT_TOKEN
  2. Start a chat with your bot → get your TELEGRAM_CHAT_ID
     (visit https://api.telegram.org/bot<TOKEN>/getUpdates after sending /start)
  3. Add both to .streamlit/secrets.toml and Streamlit Cloud secrets.

Usage:
  from core.notifier import send_signal_alert, send_message
  send_signal_alert(signal_dict)
  send_message("Custom message")
"""
from __future__ import annotations

import os
from typing import Optional

import requests


def _get_config() -> tuple[str, str]:
    """Return (bot_token, chat_id) from env or Streamlit secrets."""
    try:
        import streamlit as st
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "") or os.getenv("TELEGRAM_CHAT_ID", "")
    except Exception:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    return token, chat_id


def is_configured() -> bool:
    """Return True if Telegram credentials are set."""
    token, chat_id = _get_config()
    return bool(token and chat_id)


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Send a plain text message to the configured Telegram chat.
    Returns True on success, False on failure (never raises).
    """
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.ok
    except Exception:
        return False


def send_signal_alert(signal: dict, source: str = "Strategy") -> bool:
    """
    Send a formatted signal alert to Telegram.

    Args:
        signal: Signal dict with keys: symbol, company, signal_type,
                entry_price, sl_price, t1, t2, t3, quantity, notes
        source: "Strategy" or "AI Agent" — shown in the message header

    Returns True on success.
    """
    sym = signal.get("symbol", "?")
    company = signal.get("company", sym)
    action = signal.get("signal_type", "BUY")
    entry = signal.get("entry_price", 0)
    sl = signal.get("sl_price", 0)
    t1 = signal.get("t1", 0)
    t2 = signal.get("t2", 0)
    t3 = signal.get("t3", 0)
    qty = signal.get("quantity", 0)
    notes = signal.get("notes", "")

    R = entry - sl if entry and sl else 0
    rr = round((t3 - entry) / R, 1) if R > 0 else 0
    risk_amt = round(R * qty, 0) if R > 0 else 0

    icon = "🟢" if action == "BUY" else "🔴"
    source_icon = "🤖" if source == "AI Agent" else "📊"

    text = (
        f"{source_icon} <b>IPO Signal — {source}</b>\n"
        f"{icon} <b>{sym}</b> ({company})\n"
        f"\n"
        f"<b>Action:</b> {action}\n"
        f"<b>Entry:</b> ₹{entry:,.2f}\n"
        f"<b>Stop Loss:</b> ₹{sl:,.2f}\n"
        f"<b>T1:</b> ₹{t1:,.2f}  |  <b>T2:</b> ₹{t2:,.2f}  |  <b>T3:</b> ₹{t3:,.2f}\n"
        f"<b>Quantity:</b> {qty:,}\n"
        f"<b>Risk:</b> ₹{risk_amt:,.0f}  |  <b>R:R</b> 1:{rr}\n"
    )

    if notes:
        # Truncate long notes
        note_text = notes[:300] + "..." if len(notes) > 300 else notes
        text += f"\n<i>{note_text}</i>\n"

    text += f"\n<a href='https://kite.zerodha.com/chart/web/ciq/NSE/{sym}/EQ'>📈 View Chart</a>"

    return send_message(text)


def send_bulk_signal_alerts(signals: list[dict], source: str = "Strategy") -> int:
    """
    Send alerts for multiple signals. Returns count of successful sends.
    Sends a summary first, then individual alerts.
    """
    if not signals:
        return 0

    # Summary message
    summary = (
        f"{'🤖' if source == 'AI Agent' else '📊'} <b>{len(signals)} new signal(s) — {source}</b>\n\n"
    )
    for s in signals:
        summary += f"• <b>{s.get('symbol')}</b> — {s.get('signal_type', 'BUY')} @ ₹{s.get('entry_price', 0):,.2f}\n"

    send_message(summary)

    # Individual alerts
    sent = 0
    for signal in signals:
        if send_signal_alert(signal, source=source):
            sent += 1
    return sent


def send_order_placed_alert(symbol: str, order_id: str, order_type: str,
                             quantity: int, price: float, gtt_id: Optional[int] = None) -> bool:
    """Send a confirmation alert when an order is placed."""
    gtt_line = f"\n<b>GTT ID:</b> {gtt_id} (SL + T3 protected)" if gtt_id else ""
    text = (
        f"✅ <b>Order Placed</b>\n"
        f"<b>Symbol:</b> {symbol}\n"
        f"<b>Type:</b> {order_type}\n"
        f"<b>Qty:</b> {quantity:,}  |  <b>Price:</b> ₹{price:,.2f}\n"
        f"<b>Kite Order ID:</b> {order_id}"
        f"{gtt_line}"
    )
    return send_message(text)


# ── Bot-specific alerts ────────────────────────────────────────────────────────

def send_auto_order_alert(
    symbol: str,
    company: str,
    entry: float,
    sl: float,
    t1: float,
    t2: float,
    t3: float,
    qty: int,
    order_id: str,
    gtt_sl_id: Optional[int] = None,
    gtt_t1_id: Optional[int] = None,
    gtt_t2_id: Optional[int] = None,
) -> bool:
    """Alert when the bot auto-places a LIMIT entry + GTT orders."""
    R = entry - sl
    risk_amt = round(R * qty, 0)
    t1_qty = qty // 3
    t2_qty = qty // 3
    sl_qty = qty - t1_qty - t2_qty

    gtt_lines = ""
    if gtt_sl_id:
        gtt_lines += f"\n  SL GTT #{gtt_sl_id}: sell {sl_qty} @ ₹{sl:,.2f}"
    if gtt_t1_id:
        gtt_lines += f"\n  T1 GTT #{gtt_t1_id}: sell {t1_qty} @ ₹{t1:,.2f}"
    if gtt_t2_id:
        gtt_lines += f"\n  T2 GTT #{gtt_t2_id}: sell {t2_qty} @ ₹{t2:,.2f}"

    text = (
        f"🤖 <b>AUTO ORDER PLACED</b>\n"
        f"<b>{symbol}</b> ({company})\n"
        f"\n"
        f"<b>LIMIT BUY:</b> ₹{entry:,.2f} × {qty:,} | Order #{order_id}\n"
        f"<b>Risk:</b> ₹{risk_amt:,.0f} (R=₹{R:.2f})\n"
        f"\n"
        f"<b>GTT Orders:</b>{gtt_lines}\n"
        f"\n"
        f"<b>Targets:</b> T1 ₹{t1:,.2f} | T2 ₹{t2:,.2f} | T3 ₹{t3:,.2f}\n"
        f"<a href='https://kite.zerodha.com/chart/web/ciq/NSE/{symbol}/EQ'>📈 Chart</a>"
    )
    return send_message(text)


def send_target_hit_alert(
    symbol: str,
    target_name: str,    # "T1", "T2", or "T3"
    hit_price: float,
    entry: float,
    pnl_pct: float,
    new_sl: Optional[float] = None,
) -> bool:
    """Alert when a profit target is hit."""
    icons = {"T1": "🎯", "T2": "✅", "T3": "🏆"}
    icon = icons.get(target_name, "🎯")
    sl_line = f"\n<b>SL moved to:</b> ₹{new_sl:,.2f}" if new_sl else ""
    pnl_sign = "+" if pnl_pct >= 0 else ""
    text = (
        f"{icon} <b>{target_name} HIT — {symbol}</b>\n"
        f"<b>Hit price:</b> ₹{hit_price:,.2f}  |  <b>Entry:</b> ₹{entry:,.2f}\n"
        f"<b>P&L:</b> {pnl_sign}{pnl_pct:.1f}%"
        f"{sl_line}"
    )
    return send_message(text)


def send_sl_hit_alert(
    symbol: str,
    trigger_price: float,
    entry: float,
    loss_pct: float,
) -> bool:
    """Alert when stop-loss is triggered."""
    text = (
        f"🔴 <b>STOPPED OUT — {symbol}</b>\n"
        f"<b>SL triggered:</b> ₹{trigger_price:,.2f}  |  <b>Entry:</b> ₹{entry:,.2f}\n"
        f"<b>Loss:</b> -{abs(loss_pct):.1f}%"
    )
    return send_message(text)


def send_daily_summary(scanned: int, signals_fired: int, orders_placed: int) -> bool:
    """EOD summary from the bot's daily scan."""
    text = (
        f"📊 <b>EOD BOT SUMMARY</b>\n"
        f"Scanned: <b>{scanned}</b> IPOs\n"
        f"Signals: <b>{signals_fired}</b>\n"
        f"Orders placed: <b>{orders_placed}</b>"
    )
    return send_message(text)


def send_bot_startup_alert(accounts_count: int = 0) -> bool:
    """Alert when the bot starts up."""
    from datetime import datetime
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist).strftime("%H:%M IST")
    text = (
        f"🚀 <b>IPO Swing Bot Started</b>\n"
        f"Monitoring <b>{accounts_count}</b> account(s)\n"
        f"Started at: {now_ist}\n"
        f"Next scan: <b>15:35 IST</b> (after market close)"
    )
    return send_message(text)


def send_token_warning(account_id: str, nickname: str = "") -> bool:
    """Alert when a Kite access token has expired."""
    label = nickname or account_id
    text = (
        f"⚠️ <b>Kite Token Expired</b>\n"
        f"Account: <b>{label}</b>\n"
        f"Please re-login at the Streamlit app → Accounts page.\n"
        f"Bot will skip this account until token is refreshed."
    )
    return send_message(text)
