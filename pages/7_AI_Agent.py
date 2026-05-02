"""
pages/7_AI_Agent.py — Claude AI Trading Agent chat interface.

Claude autonomously scans IPOs, reasons about signal quality,
and saves high-quality signals to the DB.
After Claude saves a signal, an inline order panel lets the user
place the trade directly from this page.
"""
from __future__ import annotations

import json
from math import floor

import streamlit as st

st.set_page_config(
    page_title="AI Agent — IPO Portal",
    page_icon="🤖",
    layout="wide",
)

from core.db import init_db, get_all_accounts
from core.claude_agent import run_agent, get_ltp, is_configured as _api_key_set
from core.notifier import is_configured as _telegram_set


# ── DB connection ──────────────────────────────────────────────────────────────
conn = init_db()


# ── Session state init ─────────────────────────────────────────────────────────
if "ai_messages" not in st.session_state:
    st.session_state["ai_messages"] = []        # display messages
if "ai_history" not in st.session_state:
    st.session_state["ai_history"] = []         # raw API history
if "ai_last_signal" not in st.session_state:
    st.session_state["ai_last_signal"] = None   # last signal Claude saved
if "ai_order_type" not in st.session_state:
    st.session_state["ai_order_type"] = "LIMIT"
if "ai_ltp" not in st.session_state:
    st.session_state["ai_ltp"] = None


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🤖 AI Agent Settings")

    accounts = get_all_accounts(conn)
    if accounts:
        account_options = {a["nickname"]: a["id"] for a in accounts}
        selected_nick = st.selectbox("Default Account", list(account_options.keys()))
        st.session_state["ai_selected_account"] = account_options[selected_nick]
    else:
        st.warning("No accounts configured. Add one in Accounts page.")
        st.session_state["ai_selected_account"] = ""

    st.divider()
    capital = st.number_input("Capital (₹)", value=1_000_000, step=50_000, min_value=10_000)
    risk_pct = st.slider("Risk per trade (%)", 0.5, 3.0, 1.0, 0.25) / 100.0
    st.session_state["ai_capital"] = capital
    st.session_state["ai_risk_pct"] = risk_pct

    st.divider()

    # Status indicators
    api_ok = _api_key_set()
    tg_ok = _telegram_set()
    st.markdown(
        f"{'🟢' if api_ok else '🔴'} Claude API  \n"
        f"{'🟢' if tg_ok else '🟡'} Telegram alerts"
    )
    if not api_ok:
        st.error("Add ANTHROPIC_API_KEY to secrets.")

    st.divider()
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state["ai_messages"] = []
        st.session_state["ai_history"] = []
        st.session_state["ai_last_signal"] = None
        st.rerun()


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🤖 Claude AI Trading Agent")
st.caption(
    "Claude scans IPOs, reasons about signal quality, and saves the best setups. "
    "You confirm and place the trade."
)


# ── Order panel (shown after Claude saves a signal) ────────────────────────────
def _order_panel(signal: dict):
    """Render the inline order placement panel for a saved signal."""
    from core.order_manager import place_protected_order, OrderError
    from core.db import update_signal_status
    from core.notifier import send_order_placed_alert, is_configured

    sym = signal.get("symbol", "")
    company = signal.get("company", sym)
    entry = float(signal.get("entry_price", 0))
    sl = float(signal.get("sl_price", 0))
    t1 = float(signal.get("t1", 0))
    t2 = float(signal.get("t2", 0))
    t3 = float(signal.get("t3", 0))
    qty = int(signal.get("quantity", 1))
    sig_id = signal.get("id", "")
    account_id = signal.get("account_id") or st.session_state.get("ai_selected_account", "")

    st.divider()
    with st.container(border=True):
        st.subheader(f"🛡️ Place Trade — {sym}")

        col_type, col_space = st.columns([2, 3])
        with col_type:
            order_type = st.radio(
                "Order type",
                ["LIMIT", "MARKET"],
                horizontal=True,
                key=f"ot_{sig_id}",
            )

        # Live price area
        col_price, col_refresh = st.columns([3, 1])
        with col_price:
            if order_type == "MARKET":
                ltp = get_ltp(sym)
                if ltp:
                    st.info(f"📡 Live LTP: **₹{ltp:,.2f}** (auto-fetched)")
                    use_price = ltp
                else:
                    st.warning("Could not fetch live price. Using entry price.")
                    use_price = entry
                entry_input = use_price
            else:
                # LIMIT — editable field
                entry_input = st.number_input(
                    "Entry price (₹)",
                    value=float(entry),
                    step=0.05,
                    format="%.2f",
                    key=f"ep_{sig_id}",
                )

        with col_refresh:
            if order_type == "LIMIT":
                st.write("")  # spacing
                st.write("")
                if st.button("🔄 Refresh LTP", key=f"ref_{sig_id}"):
                    ltp = get_ltp(sym)
                    if ltp:
                        st.success(f"LTP: ₹{ltp:,.2f}")
                    else:
                        st.warning("Unavailable")

        # Recalculate targets based on current entry input
        R = entry_input - sl
        if R > 0:
            t1_disp = round(entry_input + R, 2)
            t2_disp = round(entry_input + 2 * R, 2)
            t3_disp = round(entry_input + 3 * R, 2)
            rr = round((t3_disp - entry_input) / R, 1)
            risk_amt = round(R * qty, 0)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("SL", f"₹{sl:,.2f}")
            c2.metric("T1", f"₹{t1_disp:,.2f}")
            c3.metric("T2", f"₹{t2_disp:,.2f}")
            c4.metric("T3", f"₹{t3_disp:,.2f}")

            qty_input = st.number_input("Quantity", value=qty, min_value=1, step=1, key=f"qty_{sig_id}")

            st.info(
                f"Risk: ₹{round(R * qty_input):,}  |  "
                f"Max profit: ₹{round((t3_disp - entry_input) * qty_input):,}  |  "
                f"R:R 1:{rr}"
            )

            st.warning(
                "⚠️ Clicking **Confirm** will place a live order via Kite. "
                "An OCO GTT (SL + T3) will be set automatically."
            )

            if st.button(
                f"✅ Confirm & Place Trade — {order_type}",
                type="primary",
                key=f"place_{sig_id}",
                use_container_width=True,
            ):
                if not account_id:
                    st.error("No account selected.")
                else:
                    with st.spinner("Placing order..."):
                        try:
                            result = place_protected_order(
                                account_id=account_id,
                                symbol=sym,
                                quantity=int(qty_input),
                                entry_price=round(entry_input, 2),
                                sl_price=sl,
                                t1_price=t1_disp,
                                t2_price=t2_disp,
                                t3_price=t3_disp,
                                order_type=order_type,
                                conn=conn,
                                strategy_id="AI_AGENT",
                                signal_id=sig_id,
                            )
                            update_signal_status(conn, sig_id, "EXECUTED", result.get("order_id"))

                            st.success(
                                f"✅ Order placed!  \n"
                                f"Order ID: `{result['order_id']}`  \n"
                                f"GTT ID: `{result.get('gtt_id', 'N/A')}`"
                            )

                            if result.get("gtt_error"):
                                st.warning(f"GTT warning: {result['gtt_error']}")

                            # Telegram alert
                            if is_configured():
                                send_order_placed_alert(
                                    symbol=sym,
                                    order_id=str(result["order_id"]),
                                    order_type=order_type,
                                    quantity=int(qty_input),
                                    price=round(entry_input, 2),
                                    gtt_id=result.get("gtt_id"),
                                )

                            st.session_state["ai_last_signal"] = None
                            st.rerun()

                        except Exception as e:
                            st.error(f"Order failed: {e}")
        else:
            st.error("Invalid R — entry price must be above SL.")

        if st.button("✖ Dismiss", key=f"dismiss_{sig_id}"):
            st.session_state["ai_last_signal"] = None
            st.rerun()


# ── Main layout ────────────────────────────────────────────────────────────────
col_chat, col_actions = st.columns([3, 1])

with col_actions:
    st.subheader("⚡ Quick Actions")
    quick_prompts = {
        "🔭 Scan IPOs (90 days)": "Scan all IPOs from the last 90 days and tell me which ones have FRESH breakout signals.",
        "💎 Best setups now": "What are the best IPO breakout setups right now? Show me FRESH signals with R:R above 2.5.",
        "📋 Review pending signals": "Show me all pending signals in the DB and tell me if any should be acted on today.",
        "💼 Check my portfolio": f"Check the holdings for account {st.session_state.get('ai_selected_account', '')} and tell me what IPOs I'm currently holding.",
    }
    for label, prompt in quick_prompts.items():
        if st.button(label, use_container_width=True):
            st.session_state["_quick_prompt"] = prompt
            st.rerun()

    st.divider()
    st.caption(
        "💡 **Tips**\n"
        "- Claude will call tools and show you what it's doing\n"
        "- Ask it to **save a signal** to add it to the Signals page\n"
        "- Place orders from the panel that appears after saving\n"
        "- Telegram alerts fire automatically on save"
    )


with col_chat:
    # Render existing chat history
    for msg in st.session_state["ai_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Render tool call expanders stored with the message
            for tc in msg.get("tool_calls", []):
                with st.expander(f"🔧 `{tc['tool_name']}`", expanded=False):
                    st.write("**Input:**")
                    st.json(tc["tool_input"])
                    st.write("**Result (preview):**")
                    preview = tc["result"][:600] + ("..." if len(tc["result"]) > 600 else "")
                    st.code(preview, language="json")

    # Show order panel if Claude just saved a signal
    if st.session_state.get("ai_last_signal"):
        _order_panel(st.session_state["ai_last_signal"])

    # Handle quick prompt injection
    injected = st.session_state.pop("_quick_prompt", None)

    # Chat input
    user_input = st.chat_input("Ask Claude about IPOs...") or injected

    if user_input and _api_key_set():
        # Show user message
        st.session_state["ai_messages"].append({
            "role": "user",
            "content": user_input,
            "tool_calls": [],
        })

        with st.chat_message("user"):
            st.markdown(user_input)

        # Run agent
        full_text = ""
        tool_calls_this_turn = []
        saved_signal = None

        with st.chat_message("assistant"):
            text_placeholder = st.empty()

            with st.status("Claude is thinking...", expanded=True) as status:
                for event in run_agent(
                    user_message=user_input,
                    conversation_history=st.session_state["ai_history"],
                    conn=conn,
                ):
                    etype = event["type"]

                    if etype == "text_delta":
                        full_text += event["text"]
                        text_placeholder.markdown(full_text + "▌")

                    elif etype == "tool_start":
                        status.write(f"🔧 Calling `{event['tool_name']}`...")

                    elif etype == "tool_result":
                        tool_calls_this_turn.append({
                            "tool_name": event["tool_name"],
                            "tool_input": {},  # input captured at tool_start
                            "result": event["result"],
                        })
                        status.write(f"✅ `{event['tool_name']}` done")

                    elif etype == "tool_start":
                        # Capture input alongside result (merge on name match)
                        for tc in tool_calls_this_turn:
                            if tc["tool_name"] == event["tool_name"] and not tc["tool_input"]:
                                tc["tool_input"] = event.get("tool_input", {})
                                break

                    elif etype == "done":
                        st.session_state["ai_history"] = event["updated_history"]
                        saved_signal = event.get("saved_signal")
                        status.update(label="Done ✓", state="complete", expanded=False)

                    elif etype == "error":
                        st.error(event["message"])
                        status.update(label="Error", state="error")

            # Final text render (remove cursor)
            text_placeholder.markdown(full_text)

            # Render tool call expanders inline
            for tc in tool_calls_this_turn:
                with st.expander(f"🔧 `{tc['tool_name']}`", expanded=False):
                    if tc.get("tool_input"):
                        st.write("**Input:**")
                        st.json(tc["tool_input"])
                    st.write("**Result (preview):**")
                    preview = tc["result"][:600] + ("..." if len(tc["result"]) > 600 else "")
                    st.code(preview, language="json")

        # Store assistant message for history rendering
        st.session_state["ai_messages"].append({
            "role": "assistant",
            "content": full_text,
            "tool_calls": tool_calls_this_turn,
        })

        # If Claude saved a signal, show the order panel
        if saved_signal:
            st.session_state["ai_last_signal"] = saved_signal

        st.rerun()

    elif user_input and not _api_key_set():
        st.error("Add ANTHROPIC_API_KEY to .streamlit/secrets.toml to use the AI Agent.")
