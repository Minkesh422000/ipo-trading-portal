---
name: add-strategy
argument-hint: [strategy-name]
---

Scaffold a new trading strategy: $ARGUMENTS

1. Read `strategies/base.py` to understand the base class interface
2. Read `strategies/ipo_breakout.py` as a reference implementation
3. Create `strategies/$ARGUMENTS.py` implementing the same interface:
   - `compute_scanner_states(ipo_list, ohlc_data)` → list of result dicts
   - Each result must include: symbol, status, entry_price, sl_price, t1, t2, t3
4. Add the strategy to `strategies/__init__.py`
5. Write a basic test in `tests/test_$ARGUMENTS.py` with sample OHLC data
6. Update CLAUDE.md with the new strategy name and brief description
