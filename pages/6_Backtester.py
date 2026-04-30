"""
pages/6_Backtester.py — Historical IPO 2-Week Breakout backtester.
Moved from the original app.py. Logic is unchanged.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from charts import plot_equity_curve, plot_monthly_pnl, plot_trade_distribution
from core.data_fetcher import fetch_all_ohlc
from core.db import get_ohlc, init_db
from scraper import ScraperError, fetch_ipo_listings
from strategy import BacktestResult, Trade, run_backtest

st.set_page_config(
    page_title="Backtester — IPO Portal",
    page_icon="🔬",
    layout="wide",
)
st.title("🔬 IPO 2-Week Breakout — Backtester")
st.markdown(
    "**Strategy:** Wait 2 weeks post-listing → enter on close above 2-week high → "
    "SL at pre-entry lowest low → targets at 1R / 2R / 3R · configurable risk per trade."
)


def _trades_to_df(trades: list[Trade]) -> pd.DataFrame:
    rows = []
    for t in trades:
        rows.append({
            "Symbol": t.symbol,
            "Company": t.name,
            "Listing Date": t.listing_date,
            "Entry Date": t.entry_date,
            "Entry Price": t.entry_price,
            "SL Price": t.sl_price,
            "T1": t.t1,
            "T2": t.t2,
            "T3": t.t3,
            "Qty": t.position_size,
            "T1 Hit": t.t1_hit,
            "T2 Hit": t.t2_hit,
            "T3 Hit": t.t3_hit,
            "Exit Date": t.exit_date,
            "Exit Reason": t.exit_reason,
            "R-Multiple": round(t.r_multiple, 2) if t.r_multiple is not None else None,
            "P&L (₹)": round(t.pnl, 2) if t.pnl is not None else None,
        })
    return pd.DataFrame(rows)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Backtest Config")

    st.subheader("Capital & Risk")
    capital = st.number_input("Capital (₹)", value=1_000_000, step=10_000, min_value=10_000)
    risk_pct_input = st.number_input(
        "Risk per Trade (%)", value=1.0, min_value=0.1, max_value=10.0, step=0.1, format="%.1f"
    )
    risk_pct = risk_pct_input / 100.0

    st.subheader("IPO Date Range")
    col1, col2 = st.columns(2)
    from_date = col1.date_input("From", value=date(2024, 1, 1))
    to_date = col2.date_input("To", value=date.today())

    force_refresh = st.checkbox("Force refresh IPO list cache", value=False)
    run_button = st.button("▶ Run Backtest", type="primary", use_container_width=True)

    st.divider()
    st.caption("Data source: local SQLite cache. Use the Signals page or fetch via MCP to populate.")

# ── Main ───────────────────────────────────────────────────────────────────────
conn = init_db()

if not run_button:
    st.info(
        "**How it works:**\n\n"
        "1. Set your date range & capital in the sidebar\n"
        "2. Click **▶ Run Backtest**\n"
        "3. If OHLC data is missing for any IPOs, go to **📡 Signals** and use **🔭 Live Scanner** "
        "to fetch data via yfinance, or ask Claude Code to fetch via Kite MCP.\n"
        "4. Re-run the backtest — data loads instantly from local cache."
    )
    st.stop()

if from_date >= to_date:
    st.error("'From' date must be before 'To' date.")
    st.stop()

# ── Step 1: Fetch IPO listings ─────────────────────────────────────────────────
with st.status("Fetching IPO listings from Chittorgarh...", expanded=False) as status:
    try:
        ipo_list = fetch_ipo_listings(from_date, to_date, conn, force_refresh)
        status.update(
            label=f"Found **{len(ipo_list)}** IPOs listed between {from_date} and {to_date}",
            state="complete",
        )
    except ScraperError as exc:
        st.error(f"Scraper error: {exc}")
        st.stop()

if not ipo_list:
    st.warning("No IPOs found for the selected date range. Try a wider range.")
    st.stop()

# ── Step 2: Load OHLC from cache ───────────────────────────────────────────────
ohlc_data: dict[str, list[dict]] = {}
missing_symbols: list[dict] = []
skipped: list[dict] = []

for ipo in ipo_list:
    sym = ipo["nse_symbol"]
    if not sym:
        skipped.append({"Symbol": ipo["name"], "Reason": "No NSE symbol (BSE-only IPO)"})
        continue
    listing_date = ipo["listing_date"]
    fetch_to = min(date.today(), listing_date + timedelta(days=365))
    bars = get_ohlc(conn, sym, listing_date.isoformat(), fetch_to.isoformat())
    if bars:
        ohlc_data[sym] = bars
    else:
        missing_symbols.append({"Symbol": sym, "Company": ipo["name"], "Listing Date": str(listing_date)})

if missing_symbols:
    with st.expander(f"⚠️ {len(missing_symbols)} IPO(s) missing OHLC data", expanded=True):
        st.dataframe(pd.DataFrame(missing_symbols), use_container_width=True, hide_index=True)
        st.warning(
            "To fetch missing data:\n"
            "- **Free (yfinance):** Go to **📡 Signals → 🔭 Live Scanner** and click Scan Now\n"
            "- **Kite API:** Ask Claude Code to fetch via MCP, or configure a Kite account"
        )

if not ohlc_data:
    st.error("No OHLC data available. Fetch data first (see above).")
    st.stop()

st.success(f"Loaded OHLC data for **{len(ohlc_data)}** of {len(ipo_list)} IPOs.")

# ── Step 3: Run backtest ───────────────────────────────────────────────────────
try:
    with st.spinner("Running backtest…"):
        result: BacktestResult = run_backtest(ipo_list, ohlc_data, capital, risk_pct)
        for s in skipped:
            result.skipped.append(s)
except Exception as exc:
    st.error(f"Backtest error: {exc}")
    st.stop()

# ── Step 4: Results ────────────────────────────────────────────────────────────
st.divider()
st.header("Results")

m = result.metrics
no_signal = [t for t in result.trades if t.exit_reason == "NO_SIGNAL"]

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Total Trades", m.get("total_trades", 0))
col2.metric("Win Rate", f"{m.get('win_rate', 0):.1%}")
col3.metric("Avg R-Multiple", f"{m.get('avg_r_multiple', 0):.2f}R")
col4.metric("Total P&L", f"₹{m.get('total_pnl', 0):,.0f}")
col5.metric("Max Drawdown", f"{m.get('max_drawdown_pct', 0):.1%}")
if "cagr" in m:
    col6.metric("CAGR", f"{m['cagr']:.1%}")
else:
    col6.metric("No-Signal", m.get("no_signal_count", 0),
                help="IPOs that never triggered a breakout")

st.subheader("Equity Curve")
st.plotly_chart(plot_equity_curve(result.equity_curve), use_container_width=True)

st.subheader("Trade Log")
trades_df = _trades_to_df(result.trades)
if not trades_df.empty:
    st.dataframe(
        trades_df, use_container_width=True, hide_index=True,
        column_config={
            "P&L (₹)": st.column_config.NumberColumn("P&L (₹)", format="₹%.2f"),
            "R-Multiple": st.column_config.NumberColumn("R-Multiple", format="%.2fR"),
            "T1 Hit": st.column_config.CheckboxColumn("T1 ✓"),
            "T2 Hit": st.column_config.CheckboxColumn("T2 ✓"),
            "T3 Hit": st.column_config.CheckboxColumn("T3 ✓"),
            "Entry Price": st.column_config.NumberColumn("Entry ₹", format="₹%.2f"),
            "SL Price": st.column_config.NumberColumn("SL ₹", format="₹%.2f"),
        },
    )
    # Download CSV
    csv = trades_df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Trade Log (CSV)", csv, "trades.csv", "text/csv")
else:
    st.info("No trades generated.")

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.plotly_chart(plot_trade_distribution(result.trades), use_container_width=True)
with chart_col2:
    st.plotly_chart(plot_monthly_pnl(result.trades), use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    if result.skipped:
        with st.expander(f"Skipped Symbols ({len(result.skipped)})", expanded=False):
            st.dataframe(pd.DataFrame(result.skipped), use_container_width=True, hide_index=True)
with col_b:
    if no_signal:
        with st.expander(f"No Breakout Signal ({len(no_signal)})", expanded=False):
            ns_df = pd.DataFrame([
                {"Symbol": t.symbol, "Company": t.name, "Listing Date": t.listing_date}
                for t in no_signal
            ])
            st.dataframe(ns_df, use_container_width=True, hide_index=True)
