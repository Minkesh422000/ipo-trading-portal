"""
pages/5_Strategies.py — Configure strategies and assign them to accounts.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import streamlit as st

from core.db import (
    get_all_accounts, get_all_strategies, get_strategy_assignments,
    init_db, upsert_strategy, upsert_strategy_assignment,
)
from strategies import STRATEGY_REGISTRY

st.set_page_config(page_title="Strategies — IPO Portal", page_icon="⚡", layout="wide")
st.title("⚡ Strategy Management")

conn = init_db()
accounts = get_all_accounts(conn)
acc_map = {a["id"]: a["nickname"] for a in accounts}

# ── Add a new strategy ─────────────────────────────────────────────────────────
with st.expander("➕ Add New Strategy", expanded=False):
    with st.form("add_strategy_form"):
        sc1, sc2 = st.columns(2)
        strat_name = sc1.text_input("Strategy Name", placeholder="e.g. IPO Breakout — Conservative")
        strat_type = sc2.selectbox("Strategy Type", list(STRATEGY_REGISTRY.keys()))
        strat_id_input = st.text_input(
            "Strategy ID (unique, no spaces)",
            placeholder="e.g. ipo_breakout_v1",
        )

        # Show default params for selected type
        default_params = STRATEGY_REGISTRY[strat_type]().get_default_params()
        st.markdown("**Default Parameters** (edit below after saving):")
        st.json(default_params)

        if st.form_submit_button("💾 Save Strategy", type="primary"):
            if not strat_name or not strat_id_input:
                st.error("Name and ID are required.")
            else:
                upsert_strategy(conn, {
                    "id": strat_id_input,
                    "name": strat_name,
                    "type": strat_type,
                    "description": STRATEGY_REGISTRY[strat_type].description,
                    "params_json": json.dumps(default_params),
                    "is_active": 1,
                    "created_at": datetime.utcnow().isoformat(),
                })
                st.success(f"✅ Strategy '{strat_name}' saved. Configure it below.")
                st.rerun()

# ── Existing strategies ────────────────────────────────────────────────────────
strategies = get_all_strategies(conn)

if not strategies:
    st.info("No strategies added yet. Use the form above to add one.")
    st.stop()

st.divider()
for strat in strategies:
    strat_cls = STRATEGY_REGISTRY.get(strat["type"])
    current_params = json.loads(strat.get("params_json") or "{}")
    assignments = get_strategy_assignments(conn, strat["id"])
    assigned_acc_ids = [a["account_id"] for a in assignments]

    with st.container(border=True):
        hc1, hc2, hc3 = st.columns([3, 1, 1])
        hc1.markdown(f"### {strat['name']}")
        hc1.caption(f"Type: `{strat['type']}` · ID: `{strat['id']}`")

        # Active toggle
        is_active = bool(strat.get("is_active", 1))
        new_active = hc2.toggle("Active", value=is_active, key=f"active_{strat['id']}")
        if new_active != is_active:
            strat["is_active"] = int(new_active)
            upsert_strategy(conn, {
                **strat,
                "params_json": json.dumps(current_params),
            })
            st.rerun()

        st.markdown(f"*{strat.get('description', '')}*")
        st.caption(f"Assigned to: {', '.join(acc_map.get(a, a) for a in assigned_acc_ids) or 'No accounts'}")

        # ── Edit parameters ────────────────────────────────────────────────────
        with st.expander("🔧 Edit Parameters"):
            with st.form(f"params_form_{strat['id']}"):
                default_params = strat_cls().get_default_params() if strat_cls else {}
                merged = {**default_params, **current_params}

                new_params = {}
                for key, val in merged.items():
                    if isinstance(val, bool):
                        new_params[key] = st.checkbox(key, value=val)
                    elif isinstance(val, int):
                        new_params[key] = st.number_input(key, value=val, step=1)
                    elif isinstance(val, float):
                        new_params[key] = st.number_input(key, value=val, step=0.1, format="%.2f")
                    else:
                        new_params[key] = st.text_input(key, value=str(val))

                if st.form_submit_button("💾 Save Parameters"):
                    upsert_strategy(conn, {**strat, "params_json": json.dumps(new_params)})
                    st.success("Parameters saved.")
                    st.rerun()

        # ── Account assignment ─────────────────────────────────────────────────
        with st.expander("👤 Assign to Accounts"):
            with st.form(f"assign_form_{strat['id']}"):
                if not accounts:
                    st.warning("No accounts configured yet.")
                else:
                    for acc in accounts:
                        existing = next((a for a in assignments if a["account_id"] == acc["id"]), None)
                        ac1, ac2, ac3 = st.columns([1, 1, 1])
                        assigned = ac1.checkbox(
                            acc["nickname"], value=bool(existing and existing.get("is_active")),
                            key=f"assign_{strat['id']}_{acc['id']}"
                        )
                        risk_val = existing.get("risk_pct", 0.01) if existing else 0.01
                        risk = ac2.number_input(
                            "Risk %", value=risk_val * 100, min_value=0.1, max_value=10.0,
                            step=0.1, format="%.1f", key=f"risk_{strat['id']}_{acc['id']}"
                        )
                        cap_val = existing.get("capital_alloc") or 1_000_000.0
                        capital = ac3.number_input(
                            "Capital (₹)", value=cap_val, min_value=10_000.0,
                            step=10_000.0, key=f"cap_{strat['id']}_{acc['id']}"
                        )

                        # Store for save
                        st.session_state[f"sa_{strat['id']}_{acc['id']}"] = {
                            "assigned": assigned, "risk": risk / 100, "capital": capital
                        }

                    if st.form_submit_button("💾 Save Assignments"):
                        for acc in accounts:
                            sa = st.session_state.get(f"sa_{strat['id']}_{acc['id']}", {})
                            upsert_strategy_assignment(conn, {
                                "strategy_id": strat["id"],
                                "account_id": acc["id"],
                                "risk_pct": sa.get("risk", 0.01),
                                "capital_alloc": sa.get("capital", 1_000_000.0),
                                "is_active": int(sa.get("assigned", False)),
                            })
                        st.success("Assignments saved.")
                        st.rerun()
