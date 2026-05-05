# Bug & Fix Log — IPO Trading Portal

Running log of all bugs found and fixed. Newest first.

---

## 2026-05-05

### BUG-004 — Strategies page: form crashes on new strategy (no prior assignment)
**File:** `pages/5_Strategies.py` line 130
**Error:** `AttributeError` — `cap_val = existing.get("capital_alloc")` called when `existing = None`
**Root cause:** When creating a brand new strategy, no assignment record exists. `existing` is `None` but `.get()` was called on it without a None guard.
**Fix:** `cap_val = (existing.get("capital_alloc") if existing else None) or 1_000_000.0`

### BUG-005 — Strategies page: `st.session_state` writes inside `st.form` (Streamlit anti-pattern)
**File:** `pages/5_Strategies.py`
**Error:** "Missing Submit Button" warning + form not saving
**Root cause:** Writing to `st.session_state` directly inside a `st.form` block is not allowed in Streamlit. Widget values must be read from their return values, not via session state.
**Fix:** Rewrote the entire assignment form — widgets captured into a local `rows = []` list inside the loop. Values used directly in the `st.form_submit_button` handler. No session_state writes inside form.

### BUG-006 — `upsert_strategy_assignment` silently dropping `auto_execute` column
**File:** `core/db.py`
**Error:** Auto-execute toggle saved in UI but never persisted to DB
**Root cause:** The SQL `INSERT OR REPLACE` explicitly listed only 5 columns `(strategy_id, account_id, risk_pct, capital_alloc, is_active)` — `auto_execute` was passed in the dict but ignored by SQLite named params when column not listed.
**Fix:** Added `auto_execute` to the column list and VALUES clause.

---

## 2026-05-04 — IPO Swing Bot Implementation

### CHANGE-001 — Strategy: observation window changed to calendar-week based
**File:** `strategies/ipo_breakout.py`
**Before:** Fixed 10 trading bars (`lookback_bars=10`)
**After:** Calendar-week logic — listing week + next full week. e.g. listed Wednesday → obs ends following Friday. Implemented via `_obs_window_end(listing_date)`.

### CHANGE-002 — Strategy: 2WH/2WL now uses bar highs/lows (not closes)
**File:** `strategies/ipo_breakout.py`
**Before:** `two_week_high = max(b["close"] for b in obs_bars)`
**After:** `two_week_high = max(b["high"] for b in obs_bars)` / `two_week_low = min(b["low"] for b in obs_bars)`
**Reason:** Standard swing trading definition uses bar highs/lows, not closes.

### CHANGE-003 — Strategy: SL fixed to obs window low (not pre-signal low)
**File:** `strategies/ipo_breakout.py`
**Before:** `sl_price = min(b["low"] for b in bars[:signal_bar_idx + 1])` — kept expanding as signal moved forward
**After:** `sl_price = min(b["low"] for b in obs_bars)` — fixed to the 2-week observation window only

### CHANGE-004 — Strategy: entry changed from market order to LIMIT at 2WH
**File:** `strategies/ipo_breakout.py`
**Before:** `entry_price = bars[signal_bar_idx + 1]["open"]` — next day's open (market order)
**After:** `entry_price = two_week_high` — LIMIT order placed at the breakout level

### BUG-001 — Telegram: `send_bot_startup_alert` crashed without `pytz`
**File:** `core/notifier.py`
**Error:** `ModuleNotFoundError: No module named 'pytz'`
**Fix:** Added `pytz>=2024.1` to `requirements.txt`

### BUG-002 — `is_token_valid()` called with wrong arguments in scheduler
**File:** `core/scheduler.py`
**Error:** `TypeError: is_token_valid() takes 1 positional argument but 2 were given`
**Fix:** Corrected call signature — `KiteManager.is_token_valid(account_id)` not `(account_id, conn)`

### BUG-003 — DB: `get_active_signals` tuple unpacking error with SQLite named params
**File:** `core/db.py`
**Error:** SQLite `IN (?)` with tuple of status values
**Fix:** Used `placeholders = ",".join("?" for _ in active_statuses)` and unpacked tuple correctly with `(*active_statuses, account_id)`

---

## Known Limitations / Future Work

| # | Item | Priority |
|---|------|----------|
| 1 | Kite token auto-refresh — currently requires manual re-login every morning via Streamlit UI | High |
| 2 | NSE holiday calendar hardcoded — needs update each year | Medium |
| 3 | T3 exit is a MARKET SELL (may get bad fill in illiquid IPOs) — consider LIMIT with buffer | Medium |
| 4 | No partial quantity management if SL GTT fires while T1/T2 GTTs also partially filled | Low |
| 5 | `DATA_SOURCE=yfinance` has 15-min lag — switch to `kite` for real-time signal accuracy | Low |
