"""
pages/1_Accounts.py — Manage Kite trading accounts.

Add multiple Zerodha accounts (each needs its own Kite API key).
Complete the daily OAuth login per account.
View token status and portfolio snapshot.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import streamlit as st

from core.db import (
    delete_account, get_account, get_all_accounts,
    init_db, upsert_account,
)
from core.kite_manager import KiteManager, _decrypt, _encrypt

st.set_page_config(page_title="Accounts — IPO Portal", page_icon="👤", layout="wide")
st.title("👤 Account Management")
st.caption("Each Zerodha account needs its own Kite API key (₹500/month). Credentials are encrypted at rest.")

conn = init_db()

# Track which account card has the edit form open
if "editing_account" not in st.session_state:
    st.session_state["editing_account"] = None

# ── Add new account ────────────────────────────────────────────────────────────
with st.expander("➕ Add New Account", expanded=False):
    with st.form("add_account_form"):
        col1, col2 = st.columns(2)
        nickname = col1.text_input("Nickname", placeholder="e.g. Minkesh Personal")
        acc_id = col2.text_input("Account ID (short, no spaces)", placeholder="e.g. minkesh")
        api_key = st.text_input("Kite API Key", type="password")
        api_secret = st.text_input("Kite API Secret", type="password")
        submitted = st.form_submit_button("💾 Save Account", type="primary")

        if submitted:
            if not all([nickname, acc_id, api_key, api_secret]):
                st.error("All fields are required.")
            elif " " in acc_id:
                st.error("Account ID must not contain spaces.")
            elif get_account(conn, acc_id):
                st.error(f"Account ID '{acc_id}' already exists.")
            else:
                try:
                    upsert_account(conn, {
                        "id": acc_id,
                        "nickname": nickname,
                        "kite_api_key": _encrypt(api_key),
                        "kite_api_secret": _encrypt(api_secret),
                        "kite_user_id": None,
                        "access_token": None,
                        "token_generated_at": None,
                        "is_active": 1,
                        "created_at": datetime.utcnow().isoformat(),
                    })
                    st.success(f"✅ Account '{nickname}' saved. Now log in below.")
                    st.rerun()
                except Exception as e:
                    err_str = str(e)
                    if "APIError" in err_str or "RLS" in err_str.upper() or "row-level" in err_str.lower():
                        st.error(
                            "❌ Supabase permission error. "
                            "Run this SQL in your Supabase dashboard → SQL Editor:\n\n"
                            "```sql\nALTER TABLE accounts DISABLE ROW LEVEL SECURITY;\n```\n\n"
                            f"Full error: {e}"
                        )
                    else:
                        st.error(f"❌ Failed to save account: {e}")

# ── Account cards ──────────────────────────────────────────────────────────────
accounts = get_all_accounts(conn)

if not accounts:
    st.info("No accounts added yet. Use the form above to add your first Kite account.")
    st.stop()

st.divider()
st.subheader(f"Connected Accounts ({len(accounts)})")

for acc in accounts:
    is_valid = KiteManager.is_token_valid(acc)
    token_badge = "✅ Token valid" if is_valid else "❌ Token expired"
    color = "green" if is_valid else "red"

    with st.container(border=True):
        h_col1, h_col2, h_col3 = st.columns([3, 2, 1])
        h_col1.markdown(f"### {acc['nickname']}")
        h_col1.caption(f"ID: `{acc['id']}` · Kite User: `{acc.get('kite_user_id') or 'Unknown'}`")
        h_col2.markdown(f":{color}[{token_badge}]")
        if acc.get("token_generated_at"):
            h_col2.caption(f"Last login: {acc['token_generated_at'][:19]} UTC")

        # Edit / Remove buttons
        btn_col1, btn_col2 = h_col3.columns(2)
        if btn_col1.button("✏️", key=f"edit_btn_{acc['id']}", help="Edit account"):
            st.session_state["editing_account"] = (
                None if st.session_state["editing_account"] == acc["id"] else acc["id"]
            )
            st.rerun()
        if btn_col2.button("🗑️", key=f"del_{acc['id']}", help="Remove account"):
            delete_account(conn, acc["id"])
            st.success(f"Account '{acc['nickname']}' removed.")
            st.session_state["editing_account"] = None
            st.rerun()

        # ── Inline edit form ───────────────────────────────────────────────────
        if st.session_state["editing_account"] == acc["id"]:
            with st.form(f"edit_form_{acc['id']}"):
                st.markdown("**✏️ Edit Account**")
                new_nickname = st.text_input("Nickname", value=acc["nickname"])
                new_api_key = st.text_input(
                    "Kite API Key", type="password",
                    placeholder="Leave blank to keep existing"
                )
                new_api_secret = st.text_input(
                    "Kite API Secret", type="password",
                    placeholder="Leave blank to keep existing"
                )
                save_col, cancel_col = st.columns(2)
                saved = save_col.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                cancelled = cancel_col.form_submit_button("✖ Cancel", use_container_width=True)

                if saved:
                    if not new_nickname.strip():
                        st.error("Nickname cannot be empty.")
                    else:
                        updated = {
                            "id": acc["id"],
                            "nickname": new_nickname.strip(),
                            "kite_api_key": _encrypt(new_api_key) if new_api_key else acc["kite_api_key"],
                            "kite_api_secret": _encrypt(new_api_secret) if new_api_secret else acc["kite_api_secret"],
                            "kite_user_id": acc.get("kite_user_id"),
                            "access_token": acc.get("access_token"),
                            "token_generated_at": acc.get("token_generated_at"),
                            "is_active": acc.get("is_active", 1),
                            "created_at": acc.get("created_at", datetime.utcnow().isoformat()),
                        }
                        try:
                            upsert_account(conn, updated)
                            st.success("✅ Account updated.")
                            st.session_state["editing_account"] = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Failed to update: {e}")

                if cancelled:
                    st.session_state["editing_account"] = None
                    st.rerun()

        # ── Login flow ─────────────────────────────────────────────────────────
        st.divider()
        login_col, token_col = st.columns([1, 2])

        with login_col:
            api_key_plain = _decrypt(acc["kite_api_key"])
            login_url = KiteManager.generate_login_url(api_key_plain)
            st.markdown(f"**Step 1:** [🔐 Login to Zerodha]({login_url})")
            st.caption("Opens Zerodha login in a new tab. After login you'll be redirected — copy the `request_token` from the URL.")

        with token_col:
            with st.form(f"login_form_{acc['id']}"):
                request_token = st.text_input(
                    "Step 2: Paste request_token from redirect URL",
                    placeholder="abc123xyz...",
                    key=f"rt_{acc['id']}",
                )
                if st.form_submit_button("✅ Complete Login", type="primary"):
                    if not request_token.strip():
                        st.error("Please paste the request_token.")
                    else:
                        with st.spinner("Exchanging token with Kite..."):
                            success, err = KiteManager.complete_login(
                                acc["id"], request_token.strip(), conn
                            )
                        if success:
                            st.success("🎉 Login successful! Token is now active.")
                            st.rerun()
                        else:
                            st.error(f"Login failed: {err}")

        # ── Quick portfolio snapshot ────────────────────────────────────────────
        if is_valid:
            if st.button("🔄 Refresh Portfolio", key=f"refresh_{acc['id']}"):
                with st.spinner(f"Fetching portfolio for {acc['nickname']}..."):
                    portfolio = KiteManager.refresh_portfolio(acc["id"], conn)
                if portfolio.get("error"):
                    st.warning(portfolio["error"])
                else:
                    m = portfolio.get("margins", {})
                    h_count = len(portfolio.get("holdings", []))
                    st.success(
                        f"✅ {h_count} holdings · "
                        f"Available: ₹{m.get('available_cash', 0):,.0f} · "
                        f"Balance: ₹{m.get('total_balance', 0):,.0f}"
                    )
