"""
pages/3_Signals.py — Live strategy signals + risk-managed order execution.

Every trade placed here includes:
  1. BUY order  (LIMIT or MARKET)
  2. OCO GTT    (SL lower leg + T3 upper leg — both active immediately)

This ensures your capital is always protected even if the app is closed.
T1 / T2 partial exits are shown as prompts when price hits those levels.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import floor

import pandas as pd
import streamlit as st

from core.db import (
    get_all_accounts, get_pending_signals, get_signal_history,
    get_active_signals, init_db, update_signal_status,
)
from core.order_manager import (
    OrderError, cancel_gtt, modify_gtt_sl_to_breakeven,
    place_protected_order, place_order,
)
from core.strategy_engine import run_all_strategies

st.set_page_config(page_title="Signals — IPO Portal", page_icon="📡", layout="wide")
st.title("📡 Strategy Signals")

conn = init_db()
accounts = get_all_accounts(conn)
acc_map  = {a["id"]: a["nickname"] for a in accounts}

tab_signals, tab_active, tab_scanner, tab_history = st.tabs(
    ["🔔 Pending Signals", "🤖 Bot Positions", "🔭 Live Scanner", "📋 Signal History"]
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared: trade panel rendered as a Streamlit dialog-style container
# ─────────────────────────────────────────────────────────────────────────────
def _trade_panel(
    *,
    panel_key: str,
    symbol: str,
    company: str,
    entry_price: float,
    sl_price: float,
    t1: float,
    t2: float,
    t3: float,
    suggested_qty: int,
    signal_id: str = "",
    strategy_id: str = "",
):
    """
    Renders a risk-managed trade confirmation panel.
    Places BUY order + OCO GTT on confirm.
    """
    if not accounts:
        st.error("No accounts configured. Go to 👤 Accounts first.")
        return

    R = entry_price - sl_price

    with st.container(border=True):
        st.markdown(f"### 🛡️ Place Protected Trade — **{symbol}**")
        st.caption(company)

        # Account + order type
        tc1, tc2, tc3 = st.columns(3)
        acc_options = {a["nickname"]: a["id"] for a in accounts}
        chosen_acc_name = tc1.selectbox("Account", list(acc_options.keys()), key=f"acc_{panel_key}")
        chosen_acc_id   = acc_options[chosen_acc_name]
        order_type      = tc2.selectbox("Order Type", ["LIMIT", "MARKET"], key=f"ot_{panel_key}")
        product         = tc3.selectbox("Product", ["CNC", "MIS"], key=f"prod_{panel_key}",
                                        help="CNC = delivery (hold overnight), MIS = intraday")

        # Editable entry / SL / qty
        pc1, pc2, pc3 = st.columns(3)
        final_entry = pc1.number_input("Entry Price (₹)", value=float(entry_price),
                                       step=0.05, format="%.2f", key=f"ep_{panel_key}")
        final_sl    = pc2.number_input("Stop Loss (₹)", value=float(sl_price),
                                       step=0.05, format="%.2f", key=f"sl_{panel_key}")
        final_qty   = pc3.number_input("Quantity", value=int(suggested_qty),
                                       min_value=1, step=1, key=f"qty_{panel_key}")

        final_R = final_entry - final_sl

        # Recompute targets from edited entry/SL
        if final_R > 0:
            final_t1 = round(final_entry + final_R, 2)
            final_t2 = round(final_entry + 2 * final_R, 2)
            final_t3 = round(final_entry + 3 * final_R, 2)
        else:
            final_t1, final_t2, final_t3 = t1, t2, t3

        # Risk summary
        risk_amt   = round(final_R * final_qty, 2) if final_R > 0 else 0
        max_profit = round((final_t3 - final_entry) * final_qty, 2) if final_R > 0 else 0

        rc1, rc2, rc3, rc4, rc5 = st.columns(5)
        rc1.metric("T1", f"₹{final_t1:.2f}")
        rc2.metric("T2", f"₹{final_t2:.2f}")
        rc3.metric("T3", f"₹{final_t3:.2f}")
        rc4.metric("Max Risk", f"₹{risk_amt:,.0f}", delta="1R loss", delta_color="inverse")
        rc5.metric("Max Profit", f"₹{max_profit:,.0f}", delta="3R gain")

        if final_R <= 0:
            st.error("⚠️ Entry price must be above Stop Loss.")
            return

        # GTT explanation
        st.info(
            f"**What will be placed:**\n"
            f"1. **BUY {final_qty} × {symbol}** at ₹{final_entry:.2f} ({order_type})\n"
            f"2. **OCO GTT — SL leg:** SELL {final_qty} if price drops to ₹{final_sl:.2f} "
            f"→ Loss capped at ₹{risk_amt:,.0f}\n"
            f"3. **OCO GTT — T3 leg:** SELL {final_qty} if price rises to ₹{final_t3:.2f} "
            f"→ Profit ₹{max_profit:,.0f}\n\n"
            f"⚡ **T1 / T2 exits are manual** — go to Orders page when targets are hit. "
            f"After T1 hit, use 'Move SL to Breakeven' to protect profit.",
            icon="🛡️",
        )

        btn_col1, btn_col2 = st.columns(2)
        confirm_key = f"confirmed_{panel_key}"

        if btn_col1.button("✅ Confirm & Place Trade", type="primary",
                           use_container_width=True, key=f"confirm_{panel_key}"):
            st.session_state[confirm_key] = True

        if btn_col2.button("✖️ Cancel", use_container_width=True, key=f"cancel_{panel_key}"):
            st.session_state.pop(confirm_key, None)
            st.session_state.pop(f"show_trade_{panel_key}", None)
            st.rerun()

        if st.session_state.get(confirm_key):
            with st.spinner("Placing BUY order + OCO GTT..."):
                try:
                    result = place_protected_order(
                        account_id=chosen_acc_id,
                        symbol=symbol,
                        quantity=int(final_qty),
                        entry_price=final_entry,
                        sl_price=final_sl,
                        t1_price=final_t1,
                        t2_price=final_t2,
                        t3_price=final_t3,
                        order_type=order_type,
                        conn=conn,
                        strategy_id=strategy_id,
                        signal_id=signal_id,
                    )
                    st.session_state.pop(confirm_key, None)

                    # BUY placed
                    st.success(
                        f"✅ **BUY order placed!** Kite Order ID: `{result['order_id']}`\n\n"
                        f"Risk: ₹{result['risk_amount']:,.0f} | Max Profit: ₹{result['max_profit']:,.0f}"
                    )

                    # GTT placed or failed
                    if result["gtt_id"]:
                        st.success(
                            f"🛡️ **OCO GTT active!** GTT ID: `{result['gtt_id']}`\n\n"
                            f"SL @ ₹{final_sl:.2f} | T3 @ ₹{final_t3:.2f} — "
                            f"persists even after logout."
                        )
                    elif result.get("gtt_error"):
                        st.warning(
                            f"⚠️ BUY placed but GTT failed: {result['gtt_error']}\n\n"
                            f"**Action needed:** Go to 📋 Orders → Place GTT manually "
                            f"to protect your position."
                        )

                    # Update signal status
                    if signal_id:
                        update_signal_status(conn, signal_id, "EXECUTED",
                                             result["order_id"])

                except OrderError as e:
                    st.session_state.pop(confirm_key, None)
                    st.error(f"❌ Order failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: Pending Signals
# ══════════════════════════════════════════════════════════════════════════════
with tab_signals:
    run_col, _ = st.columns([1, 3])
    if run_col.button("▶ Run All Strategy Signals", type="primary", use_container_width=True):
        prog = st.empty()
        def _prog(done, total, name=""):
            prog.progress(done / max(total, 1), text=f"Running: {name}")
        with st.spinner("Scanning for signals..."):
            new_signals = run_all_strategies(conn, progress_cb=_prog)
        prog.empty()
        if new_signals:
            st.success(f"✅ {len(new_signals)} new signal(s) generated.")
        else:
            st.info("No new signals found right now.")
        st.rerun()

    st.divider()
    pending = get_pending_signals(conn)

    if not pending:
        st.info("No pending signals. Click **▶ Run All Strategy Signals** to scan.")
    else:
        st.markdown(f"**{len(pending)} pending signal(s):**")

        for sig in pending:
            account_name = acc_map.get(sig["account_id"], sig["account_id"])
            entry = sig.get("entry_price") or 0.0
            sl    = sig.get("sl_price") or 0.0
            t1    = sig.get("t1") or 0.0
            t2    = sig.get("t2") or 0.0
            t3    = sig.get("t3") or 0.0
            qty   = sig.get("quantity") or 0
            R     = entry - sl

            with st.container(border=True):
                hc1, hc2 = st.columns([3, 1])
                auto_badge = " 🤖 Auto-Ordered" if sig.get("kite_order_id") else ""
                hc1.markdown(
                    f"### 🟢 {sig['symbol']} — {sig.get('company', '')} `BUY`{auto_badge}"
                )
                gtt_info = ""
                if sig.get("gtt_sl_id"):
                    gtt_info = (
                        f" · GTT-SL #{sig['gtt_sl_id']}"
                        + (f" | T1 #{sig['gtt_t1_id']}" if sig.get("gtt_t1_id") else "")
                        + (f" | T2 #{sig['gtt_t2_id']}" if sig.get("gtt_t2_id") else "")
                    )
                hc1.caption(
                    f"Account: **{account_name}** · Strategy: `{sig.get('strategy_id','')}` · "
                    f"{sig['generated_at'][:16]} UTC{gtt_info}"
                )

                dc1, dc2, dc3, dc4, dc5, dc6 = st.columns(6)
                dc1.metric("Entry",  f"₹{entry:.2f}")
                dc2.metric("SL",     f"₹{sl:.2f}")
                dc3.metric("T1",     f"₹{t1:.2f}")
                dc4.metric("T2",     f"₹{t2:.2f}")
                dc5.metric("T3",     f"₹{t3:.2f}")
                dc6.metric("Qty",    str(qty))

                risk_amt = R * qty
                st.caption(
                    f"R = ₹{R:.2f} | Risk = ₹{risk_amt:,.0f} | "
                    f"R:R = 1:{(t3-entry)/R:.1f} | {sig.get('notes','')}"
                )

                btn1, btn2 = st.columns(2)
                trade_key = f"show_trade_sig_{sig['id']}"

                if btn1.button("🛡️ Buy + Auto GTT", type="primary",
                               key=f"trade_{sig['id']}", use_container_width=True,
                               help="Places BUY order + OCO GTT (SL + T3) simultaneously"):
                    st.session_state[trade_key] = not st.session_state.get(trade_key, False)

                if btn2.button("❌ Dismiss", key=f"dismiss_{sig['id']}",
                               use_container_width=True):
                    update_signal_status(conn, sig["id"], "DISMISSED")
                    st.rerun()

                if st.session_state.get(trade_key, False):
                    _trade_panel(
                        panel_key=sig["id"],
                        symbol=sig["symbol"],
                        company=sig.get("company", ""),
                        entry_price=entry,
                        sl_price=sl,
                        t1=t1, t2=t2, t3=t3,
                        suggested_qty=qty,
                        signal_id=sig["id"],
                        strategy_id=sig.get("strategy_id", ""),
                    )

        # ── After T1 hit: Move SL to Breakeven ────────────────────────────────
        with st.expander("🔁 Move SL to Breakeven (after T1 hit)", expanded=False):
            st.markdown(
                "When T1 is hit, manually sell 1/3 position and then move the GTT "
                "stop-loss to your entry price so the trade cannot lose money."
            )
            with st.form("be_form"):
                be1, be2, be3 = st.columns(3)
                be_acc   = be1.selectbox("Account", [a["nickname"] for a in accounts])
                be_gtt   = be2.number_input("Kite GTT ID to replace", min_value=0, step=1)
                be_sym   = be3.text_input("Symbol", placeholder="e.g. FRACTAL")
                be4, be5, be6 = st.columns(3)
                be_qty   = be4.number_input("Remaining Qty", min_value=1, step=1, value=100)
                be_entry = be5.number_input("Entry Price ₹", min_value=0.01, step=0.05,
                                            format="%.2f", value=100.0)
                be_t3    = be6.number_input("T3 Price ₹", min_value=0.01, step=0.05,
                                            format="%.2f", value=130.0)
                if st.form_submit_button("🔁 Move SL to Breakeven", type="primary"):
                    acc_id = next(a["id"] for a in accounts if a["nickname"] == be_acc)
                    try:
                        modify_gtt_sl_to_breakeven(
                            account_id=acc_id,
                            kite_gtt_id=int(be_gtt),
                            symbol=be_sym.strip().upper(),
                            quantity=int(be_qty),
                            entry_price=float(be_entry),
                            t3_price=float(be_t3),
                            conn=conn,
                        )
                        st.success("✅ GTT updated — SL now at breakeven (entry price).")
                    except OrderError as e:
                        st.error(f"Failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: Bot Positions (auto-ordered + actively tracked)
# ══════════════════════════════════════════════════════════════════════════════
_STATUS_ICON = {
    "PENDING_FILL": "⏳",
    "EXECUTED":     "🟡",
    "T1_HIT":       "🟢",
    "T2_HIT":       "✅",
    "T3_HIT":       "🏆",
    "STOPPED_OUT":  "🔴",
}

with tab_active:
    st.markdown(
        "Live view of positions placed by the **IPO Swing Bot** — "
        "automatically updated each time you refresh this page."
    )
    active_sigs = get_active_signals(conn)

    if not active_sigs:
        st.info(
            "No active bot positions. Run `python run_bot.py` to start the bot, "
            "or use **▶ Run All Strategy Signals** and enable Auto-Execute in ⚡ Strategies."
        )
    else:
        st.markdown(f"**{len(active_sigs)} active position(s):**")
        for sig in active_sigs:
            account_name = acc_map.get(sig["account_id"], sig["account_id"])
            status = sig.get("status", "EXECUTED")
            icon   = _STATUS_ICON.get(status, "🟡")
            entry  = sig.get("entry_price") or 0.0
            sl     = sig.get("sl_price") or 0.0
            t1, t2, t3 = sig.get("t1") or 0, sig.get("t2") or 0, sig.get("t3") or 0
            qty    = sig.get("quantity") or 0
            R      = entry - sl

            with st.container(border=True):
                sc1, sc2 = st.columns([4, 1])
                sc1.markdown(f"### {icon} {sig['symbol']} — {sig.get('company', '')}")
                sc2.markdown(f"**`{status}`**")
                sc1.caption(
                    f"Account: **{account_name}** · "
                    f"Order: `{sig.get('kite_order_id', '-')}` · "
                    f"GTT-SL: `{sig.get('gtt_sl_id', '-')}` · "
                    f"GTT-T1: `{sig.get('gtt_t1_id', '-')}` · "
                    f"GTT-T2: `{sig.get('gtt_t2_id', '-')}`"
                )
                mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
                mc1.metric("Entry", f"₹{entry:.2f}")
                mc2.metric("SL",    f"₹{sl:.2f}")
                mc3.metric("T1",    f"₹{t1:.2f}", delta="1R" if not sig.get("t1_hit_at") else "✓ Hit")
                mc4.metric("T2",    f"₹{t2:.2f}", delta="2R" if not sig.get("t2_hit_at") else "✓ Hit")
                mc5.metric("T3",    f"₹{t3:.2f}", delta="3R" if not sig.get("t3_hit_at") else "✓ Hit")
                mc6.metric("Qty",   str(qty))
                if R > 0:
                    st.caption(f"R = ₹{R:.2f} | Risk = ₹{R * qty:,.0f} | R:R = 1:3")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Live Scanner
# ══════════════════════════════════════════════════════════════════════════════
with tab_scanner:
    st.markdown(
        "Scan IPOs for breakout signals. Click **🛡️ Trade** on any row to place "
        "a risk-managed order (BUY + OCO GTT) directly from here."
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns(4)
    lookback    = fc1.slider("Observation window (bars)", 5, 20, 10)
    max_age     = fc2.slider("Max IPO age (days)", 30, 365, 180)
    fetch_mcap  = fc3.checkbox("Fetch Market Cap", value=True)
    mcap_filter = fc4.selectbox(
        "Market Cap Filter",
        ["All", "Large Cap (>₹20,000 Cr)", "Mid Cap (₹5,000–20,000 Cr)",
         "Small Cap (₹500–5,000 Cr)", "Micro Cap (<₹500 Cr)"],
    )

    # Risk settings for trade panel
    rf1, rf2 = st.columns(2)
    scan_capital  = rf1.number_input("Capital for sizing (₹)", value=1_000_000,
                                     step=10_000, min_value=10_000)
    scan_risk_pct = rf2.number_input("Risk per trade (%)", value=1.0, min_value=0.1,
                                     max_value=10.0, step=0.1, format="%.1f") / 100

    status_filter = st.multiselect(
        "Show Signal Status",
        ["🟢 FRESH", "🟡 NEAR", "🔵 WATCHING", "⚪ PAST", "❌ NO_DATA"],
        default=["🟢 FRESH", "🟡 NEAR", "🔵 WATCHING"],
    )

    if st.button("🔭 Scan Now", type="primary"):
        from scraper import fetch_ipo_listings
        from core.data_fetcher import fetch_all_ohlc
        from strategies.ipo_breakout import IPOBreakoutStrategy

        today     = date.today()
        from_date = today - timedelta(days=max_age)

        with st.spinner("Fetching IPO list..."):
            try:
                ipo_list = fetch_ipo_listings(from_date, today, conn)
            except Exception as e:
                st.error(f"Scraper error: {e}")
                ipo_list = []

        if not ipo_list:
            st.warning("No IPOs found for the selected date range.")
        else:
            with st.spinner(f"Loading OHLC for {len(ipo_list)} IPOs..."):
                ohlc_data = fetch_all_ohlc(ipo_list, conn=conn)

            market_caps = {}
            if fetch_mcap:
                symbols = [i["nse_symbol"] for i in ipo_list if i.get("nse_symbol")]
                with st.spinner(f"Fetching market caps for {len(symbols)} symbols..."):
                    market_caps = IPOBreakoutStrategy.fetch_market_caps(symbols)

            states = IPOBreakoutStrategy.compute_scanner_states(
                ipo_list, ohlc_data, lookback, market_caps
            )
            st.session_state["scanner_states"] = states
            st.success(f"✅ Scanned {len(states)} IPOs.")

    states = st.session_state.get("scanner_states", [])
    if not states:
        st.info("Configure filters above and click **🔭 Scan Now**.")
    else:
        from strategies.ipo_breakout import IPOBreakoutStrategy

        STATUS_LABEL = {
            "FRESH": "🟢 Fresh Signal", "NEAR": "🟡 Near Breakout",
            "WATCHING": "🔵 Watching",  "PAST": "⚪ Past Signal",
            "NO_DATA": "❌ No Data",
        }

        df = pd.DataFrame(states)

        # Apply status filter
        selected_raw = [s.split()[1] for s in status_filter]
        df = df[df["status"].isin(selected_raw)]

        # Apply market cap filter
        if mcap_filter != "All" and "market_cap_cr" in df.columns:
            if "Large"  in mcap_filter: df = df[df["market_cap_cr"] > 20_000]
            elif "Mid"  in mcap_filter: df = df[(df["market_cap_cr"] >= 5_000) & (df["market_cap_cr"] <= 20_000)]
            elif "Small" in mcap_filter: df = df[(df["market_cap_cr"] >= 500) & (df["market_cap_cr"] < 5_000)]
            elif "Micro" in mcap_filter: df = df[df["market_cap_cr"] < 500]

        if df.empty:
            st.info("No IPOs match the selected filters.")
        else:
            # Summary
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Total", len(df))
            mc2.metric("🟢 Fresh",  int((df["status"] == "FRESH").sum()))
            mc3.metric("🟡 Near",   int((df["status"] == "NEAR").sum()))
            mc4.metric("T1 Hit",    int(df.get("t1_hit", pd.Series(dtype=bool)).sum()))
            mc5.metric("T3 Hit",    int(df.get("t3_hit", pd.Series(dtype=bool)).sum()))

            st.divider()

            # ── Results table ──────────────────────────────────────────────────
            display_df = df.copy()
            display_df["Signal Status"] = display_df["status"].map(STATUS_LABEL)
            rename_map = {
                "symbol": "Symbol", "company": "Company",
                "listing_date": "Listing Date", "days_since_listing": "Days Listed",
                "signal_date": "Signal Date",
                "two_week_high": "2W High (₹)",
                "entry_price": "Entry (₹)", "sl_price": "SL (₹)",
                "t1": "T1 (₹)", "t2": "T2 (₹)", "t3": "T3 (₹)",
                "t1_hit": "T1 ✓", "t2_hit": "T2 ✓", "t3_hit": "T3 ✓",
                "current_price": "Current (₹)",
                "entry_status": "Trade Status",
                "market_cap_cr": "Mkt Cap (₹Cr)",
            }
            display_df = display_df.rename(columns=rename_map)
            show_cols = [c for c in [
                "Symbol", "Company", "Listing Date", "Signal Date",
                "2W High (₹)", "Entry (₹)", "SL (₹)",
                "T1 (₹)", "T2 (₹)", "T3 (₹)",
                "T1 ✓", "T2 ✓", "T3 ✓",
                "Current (₹)", "Trade Status", "Signal Status", "Mkt Cap (₹Cr)",
            ] if c in display_df.columns]

            st.dataframe(
                display_df[show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Entry (₹)":     st.column_config.NumberColumn(format="₹%.2f"),
                    "SL (₹)":        st.column_config.NumberColumn(format="₹%.2f"),
                    "2W High (₹)":   st.column_config.NumberColumn(format="₹%.2f"),
                    "T1 (₹)":        st.column_config.NumberColumn(format="₹%.2f"),
                    "T2 (₹)":        st.column_config.NumberColumn(format="₹%.2f"),
                    "T3 (₹)":        st.column_config.NumberColumn(format="₹%.2f"),
                    "Current (₹)":   st.column_config.NumberColumn(format="₹%.2f"),
                    "T1 ✓":          st.column_config.CheckboxColumn(),
                    "T2 ✓":          st.column_config.CheckboxColumn(),
                    "T3 ✓":          st.column_config.CheckboxColumn(),
                    "Mkt Cap (₹Cr)": st.column_config.NumberColumn(format="₹%.0f Cr"),
                },
            )

            csv = display_df[show_cols].to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", csv, "ipo_scanner.csv", "text/csv")

            # ── Per-row Trade Panel ────────────────────────────────────────────
            st.divider()
            st.subheader("🛡️ Place Protected Trade")

            # Only show tradeable symbols (those with entry price computed)
            tradeable = df[df["entry_price"].notna() & df["sl_price"].notna()]
            if tradeable.empty:
                st.info("No tradeable signals (need FRESH or PAST status with entry/SL computed).")
            else:
                sym_options = tradeable["symbol"].tolist()
                selected_sym = st.selectbox(
                    "Select symbol to trade",
                    sym_options,
                    format_func=lambda s: f"{s} — {tradeable[tradeable['symbol']==s]['company'].values[0] if len(tradeable[tradeable['symbol']==s]) else ''}",
                )

                row = tradeable[tradeable["symbol"] == selected_sym].iloc[0]
                entry_p = float(row["entry_price"])
                sl_p    = float(row["sl_price"])
                t1_p    = float(row["t1"]) if pd.notna(row.get("t1")) else round(entry_p + (entry_p - sl_p), 2)
                t2_p    = float(row["t2"]) if pd.notna(row.get("t2")) else round(entry_p + 2*(entry_p - sl_p), 2)
                t3_p    = float(row["t3"]) if pd.notna(row.get("t3")) else round(entry_p + 3*(entry_p - sl_p), 2)
                R_val   = entry_p - sl_p
                auto_qty = floor((scan_capital * scan_risk_pct) / R_val) if R_val > 0 else 1

                _trade_panel(
                    panel_key=f"scanner_{selected_sym}",
                    symbol=selected_sym,
                    company=str(row.get("company", "")),
                    entry_price=entry_p,
                    sl_price=sl_p,
                    t1=t1_p, t2=t2_p, t3=t3_p,
                    suggested_qty=max(1, auto_qty),
                )


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: Signal History
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("Recent Signals (last 50)")
    history = get_signal_history(conn, limit=50)
    if history:
        df_h = pd.DataFrame(history)
        df_h["account_id"] = df_h["account_id"].map(acc_map).fillna(df_h["account_id"])
        st.dataframe(df_h, use_container_width=True, hide_index=True)
    else:
        st.info("No signal history yet.")
