"""
pages/4_Orders.py — Order history and manual order placement.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from core.db import get_all_accounts, get_orders, get_gtts, init_db
from core.order_manager import (
    OrderError, cancel_gtt, cancel_order,
    get_live_orders, get_live_gtts, place_order,
)

st.set_page_config(page_title="Orders — IPO Portal", page_icon="📋", layout="wide")
st.title("📋 Orders")

conn = init_db()
accounts = get_all_accounts(conn)

if not accounts:
    st.warning("No accounts configured. Go to **👤 Accounts** first.")
    st.stop()

acc_map = {a["id"]: a["nickname"] for a in accounts}
acc_options = {f"{a['nickname']} ({a['id']})": a["id"] for a in accounts}

tab_live, tab_gtt, tab_history, tab_manual = st.tabs(
    ["⚡ Live Orders", "📌 GTT Orders", "📜 History", "➕ Place Manual Order"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Live Orders
# ══════════════════════════════════════════════════════════════════════════════
with tab_live:
    selected_acc_label = st.selectbox("Account", list(acc_options.keys()), key="live_acc")
    selected_acc_id = acc_options[selected_acc_label]

    if st.button("🔄 Refresh from Kite", key="refresh_orders"):
        live = get_live_orders(selected_acc_id, conn)
        st.session_state["live_orders"] = live

    live_orders = st.session_state.get("live_orders", [])
    if not live_orders:
        st.info("Click **🔄 Refresh from Kite** to load today's orders.")
    else:
        df_live = pd.DataFrame(live_orders)
        show_cols = [c for c in [
            "order_id", "tradingsymbol", "transaction_type", "quantity",
            "price", "order_type", "status", "filled_quantity",
        ] if c in df_live.columns]
        st.dataframe(df_live[show_cols], use_container_width=True, hide_index=True)

        st.subheader("Cancel an Order")
        cancel_order_id = st.text_input("Enter Kite Order ID to cancel:")
        if st.button("❌ Cancel Order", type="primary") and cancel_order_id:
            with st.spinner("Cancelling..."):
                ok = cancel_order(selected_acc_id, cancel_order_id.strip(), conn)
            if ok:
                st.success("Order cancelled.")
            else:
                st.error("Failed to cancel. Check if order is already filled or expired.")

# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: GTT Orders
# ══════════════════════════════════════════════════════════════════════════════
with tab_gtt:
    selected_acc_label_gtt = st.selectbox("Account", list(acc_options.keys()), key="gtt_acc")
    selected_acc_id_gtt = acc_options[selected_acc_label_gtt]

    if st.button("🔄 Refresh GTTs from Kite"):
        live_gtts = get_live_gtts(selected_acc_id_gtt, conn)
        st.session_state["live_gtts"] = live_gtts

    live_gtts = st.session_state.get("live_gtts", [])
    if not live_gtts:
        st.info("Click **🔄 Refresh GTTs** to load active GTT orders.")
    else:
        st.dataframe(pd.DataFrame(live_gtts), use_container_width=True, hide_index=True)

        st.subheader("Cancel a GTT")
        cancel_gtt_id = st.number_input("Enter GTT ID to cancel:", min_value=0, step=1)
        if st.button("❌ Cancel GTT") and cancel_gtt_id:
            ok = cancel_gtt(selected_acc_id_gtt, int(cancel_gtt_id), conn)
            if ok:
                st.success("GTT cancelled.")
            else:
                st.error("Failed to cancel GTT.")

# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Order History (from local DB)
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    selected_acc_label_hist = st.selectbox("Account", list(acc_options.keys()), key="hist_acc")
    selected_acc_id_hist = acc_options[selected_acc_label_hist]

    orders = get_orders(conn, selected_acc_id_hist, limit=100)
    if orders:
        df_orders = pd.DataFrame(orders)
        df_orders["account_id"] = df_orders["account_id"].map(acc_map).fillna(df_orders["account_id"])
        st.dataframe(df_orders, use_container_width=True, hide_index=True)
    else:
        st.info("No order history in local DB for this account.")

    gtt_rows = get_gtts(conn, selected_acc_id_hist)
    if gtt_rows:
        st.subheader("GTT History (local DB)")
        st.dataframe(pd.DataFrame(gtt_rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 4: Place Manual Order
# ══════════════════════════════════════════════════════════════════════════════
with tab_manual:
    st.markdown("Place a one-off order outside of any strategy signal.")

    with st.form("manual_order_form"):
        mc1, mc2 = st.columns(2)
        manual_acc = mc1.selectbox("Account", list(acc_options.keys()))
        manual_symbol = mc2.text_input("Symbol (NSE)", placeholder="e.g. RELIANCE")

        mc3, mc4, mc5 = st.columns(3)
        tx_type = mc3.selectbox("Transaction", ["BUY", "SELL"])
        order_type = mc4.selectbox("Order Type", ["LIMIT", "MARKET", "SL", "SL-M"])
        product = mc5.selectbox("Product", ["CNC", "MIS", "NRML"])

        mc6, mc7, mc8 = st.columns(3)
        qty = mc6.number_input("Quantity", min_value=1, step=1, value=1)
        price = mc7.number_input("Price (₹)", min_value=0.0, step=0.05, value=0.0)
        trigger = mc8.number_input("Trigger Price (₹, for SL orders)", min_value=0.0, step=0.05, value=0.0)

        submitted = st.form_submit_button("📤 Place Order", type="primary")
        if submitted:
            if not manual_symbol.strip():
                st.error("Symbol is required.")
            else:
                acc_id_manual = acc_options[manual_acc]
                try:
                    kite_order_id = place_order(
                        account_id=acc_id_manual,
                        symbol=manual_symbol.strip().upper(),
                        transaction_type=tx_type,
                        quantity=int(qty),
                        order_type=order_type,
                        price=float(price),
                        trigger_price=float(trigger),
                        product=product,
                        conn=conn,
                    )
                    st.success(f"✅ Order placed successfully. Kite Order ID: **{kite_order_id}**")
                except OrderError as e:
                    st.error(f"Order failed: {e}")
