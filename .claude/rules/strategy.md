---
paths:
  - "strategies/**/*.py"
  - "ipo_alert.py"
---

# Strategy Rules

## IPO 2-Week Breakout — Core Rules
- Observation window = listing week + next FULL calendar week (not 14 days flat)
- 2WH = max(high) during obs window → entry trigger price
- 2WL = min(low) during obs window → initial stop loss
- R = 2WH − 2WL — must always be > 0, guard with `if R <= 0`
- T1 = Entry + R | T2 = Entry + 2R | T3 = Entry + 3R
- SL locks at signal day's running low (not obs window low)
- After T1 hit: effective SL moves to entry (breakeven)

## Status Priority (never skip steps)
FRESH → NEAR → WATCHING → PAST → NO_DATA

## compute_scanner_states() Contract
- Input: ipo_list (list of dicts), ohlc_data (dict of symbol → bars)
- Output: list of result dicts with REQUIRED keys:
  symbol, company, status, entry_price, sl_price, t1, t2, t3,
  current_price, signal_date, entry_status, pct_to_breakout
- Sort output: FRESH first, then NEAR, WATCHING, PAST, NO_DATA

## Never
- Use look-ahead data (don't use bars after the current evaluation date)
- Hard-code number of observation days (derive from listing_date + calendar weeks)
