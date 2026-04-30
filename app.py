"""
app.py — Home Dashboard for the IPO Trading Portal.

Shows a consolidated view of all accounts, pending signals, and quick actions.
"""
from __future__ import annotations

import streamlit as st

from core.db import (
    get_all_accounts, get_holdings, get_margins,
    get_pending_signals, init_db,
)
from core.kite_manager import KiteManager

st.set_page_config(
    page_title="IPO Trading Portal",
    page_icon="📈",
    layout="wide",
)

# ── Initialise DB ──────────────────────────────────────────────────────────────
conn = init_db()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📈 IPO Trading Portal")
st.caption(
    "Multi-account Zerodha trading portal · IPO 2-Week Breakout Strategy · "
    "Powered by Kite API + yfinance"
)
st.divider()

# ── Account status bar ────────────────────────────────────────────────────────
accounts = get_all_accounts(conn)

if not accounts:
    st.info(
        "**Welcome! Let's get started:**\n\n"
        "1. Go to **👤 Accounts** in the left sidebar\n"
        "2. Add your Zerodha account (API Key + Secret)\n"
        "3. Complete the Kite OAuth login\n"
        "4. Come back here to see your portfolio and signals\n\n"
        "**No API key?** The backtester works with free yfinance data — "
        "go to **🔬 Backtester** to try it out."
    )
    st.stop()

# ── Consolidated metrics ───────────────────────────────────────────────────────
total_holdings = 0
total_pnl = 0.0
total_cash = 0.0
active_tokens = 0

for acc in accounts:
    holdings = get_holdings(conn, acc["id"])
    margins = get_margins(conn, acc["id"]) or {}
    total_holdings += len(holdings)
    total_pnl += sum(h.get("pnl", 0) for h in holdings)
    total_cash += margins.get("available_cash", 0)
    if KiteManager.is_token_valid(acc):
        active_tokens += 1

pending_signals = get_pending_signals(conn)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Accounts", f"{len(accounts)}")
col2.metric("Tokens Active", f"{active_tokens}/{len(accounts)}",
            delta=None if active_tokens == len(accounts) else f"{len(accounts)-active_tokens} expired",
            delta_color="inverse")
col3.metric("Holdings", total_holdings)
col4.metric("Total P&L", f"₹{total_pnl:,.0f}")
col5.metric("Available Cash", f"₹{total_cash:,.0f}")

st.divider()

# ── Account status cards ──────────────────────────────────────────────────────
st.subheader("Account Status")
acc_cols = st.columns(min(len(accounts), 3))

for i, acc in enumerate(accounts):
    is_valid = KiteManager.is_token_valid(acc)
    with acc_cols[i % 3]:
        with st.container(border=True):
            st.markdown(f"**{acc['nickname']}**")
            if is_valid:
                st.success("✅ Token active")
            else:
                st.error("❌ Token expired")
                st.page_link("pages/1_Accounts.py", label="→ Login now", icon="🔐")

            m = get_margins(conn, acc["id"]) or {}
            h = get_holdings(conn, acc["id"])
            st.caption(
                f"Holdings: {len(h)} · "
                f"Cash: ₹{m.get('available_cash', 0):,.0f}"
            )

# ── Pending signals ────────────────────────────────────────────────────────────
st.divider()
st.subheader(f"🔔 Pending Signals ({len(pending_signals)})")

if not pending_signals:
    st.info("No pending signals. Go to **📡 Signals** and run a strategy scan.")
else:
    acc_map = {a["id"]: a["nickname"] for a in accounts}
    for sig in pending_signals[:5]:  # show max 5 on dashboard
        entry = sig.get("entry_price", 0) or 0
        sl = sig.get("sl_price", 0) or 0
        t3 = sig.get("t3", 0) or 0
        qty = sig.get("quantity", 0) or 0
        account_name = acc_map.get(sig["account_id"], sig["account_id"])
        with st.container(border=True):
            sc1, sc2, sc3 = st.columns([2, 2, 1])
            sc1.markdown(f"🟢 **{sig['symbol']}** — {sig.get('company', '')}")
            sc1.caption(f"{account_name} · {sig.get('strategy_id', '')}")
            sc2.markdown(
                f"Buy @ ₹{entry:.2f} | SL: ₹{sl:.2f} | T3: ₹{t3:.2f} | Qty: {qty}"
            )
            sc3.page_link("pages/3_Signals.py", label="→ View & Execute", icon="📡")

    if len(pending_signals) > 5:
        st.page_link("pages/3_Signals.py",
                     label=f"→ View all {len(pending_signals)} signals", icon="📡")

# ── Quick links ────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Quick Navigation")
lc1, lc2, lc3, lc4, lc5 = st.columns(5)
lc1.page_link("pages/1_Accounts.py", label="👤 Accounts", icon="👤")
lc2.page_link("pages/2_Portfolio.py", label="📊 Portfolio", icon="📊")
lc3.page_link("pages/3_Signals.py", label="📡 Signals", icon="📡")
lc4.page_link("pages/5_Strategies.py", label="⚡ Strategies", icon="⚡")
lc5.page_link("pages/6_Backtester.py", label="🔬 Backtester", icon="🔬")
