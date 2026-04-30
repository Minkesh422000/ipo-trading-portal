"""
pages/2_Portfolio.py — Holdings, positions, and capital across all accounts.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.db import (
    get_all_accounts, get_holdings, get_margins, get_positions, init_db,
)
from core.kite_manager import KiteManager

st.set_page_config(page_title="Portfolio — IPO Portal", page_icon="📊", layout="wide")
st.title("📊 Portfolio")

conn = init_db()
accounts = get_all_accounts(conn)

if not accounts:
    st.warning("No accounts configured. Go to **👤 Accounts** to add one.")
    st.stop()

# ── Account selector ──────────────────────────────────────────────────────────
account_options = {"All Accounts (Consolidated)": None}
account_options.update({f"{a['nickname']} ({a['id']})": a["id"] for a in accounts})

selected_label = st.selectbox("Select Account", list(account_options.keys()))
selected_id = account_options[selected_label]

# Refresh button
if st.button("🔄 Refresh from Kite", type="primary"):
    ids_to_refresh = [selected_id] if selected_id else [a["id"] for a in accounts]
    for acc_id in ids_to_refresh:
        acc = next((a for a in accounts if a["id"] == acc_id), None)
        if not acc:
            continue
        if not KiteManager.is_token_valid(acc):
            st.warning(f"⚠️ {acc['nickname']}: Token expired — skipping. Please log in via Accounts page.")
            continue
        with st.spinner(f"Refreshing {acc['nickname']}..."):
            result = KiteManager.refresh_portfolio(acc_id, conn)
        if result.get("error"):
            st.error(f"{acc['nickname']}: {result['error']}")
        else:
            st.success(f"✅ {acc['nickname']} refreshed.")
    st.rerun()

st.divider()

# ── Determine which accounts to show ──────────────────────────────────────────
display_ids = [selected_id] if selected_id else [a["id"] for a in accounts]

# ── Consolidated metrics ───────────────────────────────────────────────────────
all_holdings: list[dict] = []
all_positions: list[dict] = []
total_cash = 0.0
total_balance = 0.0
total_pnl = 0.0

for acc_id in display_ids:
    all_holdings.extend(get_holdings(conn, acc_id))
    all_positions.extend(get_positions(conn, acc_id))
    m = get_margins(conn, acc_id) or {}
    total_cash += m.get("available_cash", 0.0)
    total_balance += m.get("total_balance", 0.0)

total_pnl = sum(h.get("pnl", 0.0) for h in all_holdings)
invested_value = sum(
    h.get("average_price", 0) * h.get("quantity", 0) for h in all_holdings
)
current_value = sum(
    h.get("last_price", 0) * h.get("quantity", 0) for h in all_holdings
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Holdings", len(all_holdings))
col2.metric("Invested Value", f"₹{invested_value:,.0f}")
col3.metric("Current Value", f"₹{current_value:,.0f}")
col4.metric("Total P&L", f"₹{total_pnl:,.0f}",
            delta=f"{total_pnl/invested_value*100:.1f}%" if invested_value > 0 else None)
col5.metric("Available Cash", f"₹{total_cash:,.0f}")

# ── Holdings table ─────────────────────────────────────────────────────────────
st.subheader("📦 Holdings")
if all_holdings:
    df_h = pd.DataFrame(all_holdings)

    # Add account nickname if showing all
    if not selected_id and len(accounts) > 1:
        acc_map = {a["id"]: a["nickname"] for a in accounts}
        df_h["Account"] = df_h["account_id"].map(acc_map)
        cols = ["Account", "symbol", "quantity", "average_price", "last_price", "pnl", "pnl_pct"]
    else:
        cols = ["symbol", "quantity", "average_price", "last_price", "pnl", "pnl_pct"]

    # Filter to available columns
    cols = [c for c in cols if c in df_h.columns]
    df_h = df_h[cols].sort_values("pnl", ascending=False) if "pnl" in df_h.columns else df_h[cols]

    col_config = {
        "symbol": "Symbol",
        "quantity": st.column_config.NumberColumn("Qty", format="%d"),
        "average_price": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
        "last_price": st.column_config.NumberColumn("LTP (₹)", format="₹%.2f"),
        "pnl": st.column_config.NumberColumn("P&L (₹)", format="₹%.0f"),
        "pnl_pct": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
    }
    st.dataframe(df_h, use_container_width=True, hide_index=True, column_config=col_config)
else:
    st.info("No holdings data. Click **🔄 Refresh from Kite** to load.")

# ── Positions table ────────────────────────────────────────────────────────────
if all_positions:
    st.subheader("⚡ Open Positions (Intraday)")
    df_p = pd.DataFrame(all_positions)
    if not selected_id and len(accounts) > 1:
        acc_map = {a["id"]: a["nickname"] for a in accounts}
        df_p["Account"] = df_p["account_id"].map(acc_map)
    pos_cols = [c for c in ["Account", "symbol", "quantity", "average_price", "last_price", "pnl", "product"]
                if c in df_p.columns]
    st.dataframe(df_p[pos_cols], use_container_width=True, hide_index=True)

# ── Per-account breakdown ──────────────────────────────────────────────────────
if not selected_id and len(accounts) > 1:
    st.subheader("💼 Capital by Account")
    rows = []
    for acc in accounts:
        m = get_margins(conn, acc["id"]) or {}
        h = get_holdings(conn, acc["id"])
        pnl = sum(x.get("pnl", 0) for x in h)
        rows.append({
            "Account": acc["nickname"],
            "Holdings": len(h),
            "P&L (₹)": round(pnl, 0),
            "Available Cash (₹)": round(m.get("available_cash", 0), 0),
            "Net Balance (₹)": round(m.get("total_balance", 0), 0),
        })
    df_accounts = pd.DataFrame(rows)
    st.dataframe(df_accounts, use_container_width=True, hide_index=True,
                 column_config={
                     "P&L (₹)": st.column_config.NumberColumn(format="₹%.0f"),
                     "Available Cash (₹)": st.column_config.NumberColumn(format="₹%.0f"),
                     "Net Balance (₹)": st.column_config.NumberColumn(format="₹%.0f"),
                 })
