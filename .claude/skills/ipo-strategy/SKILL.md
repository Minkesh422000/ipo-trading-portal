---
name: ipo-strategy
description: Deep knowledge of the IPO 2-Week Breakout strategy — apply when discussing strategy logic, signals, or trade management.
user-invocable: true
---

# IPO 2-Week Breakout Strategy

## Entry Setup
- After NSE listing, observe first 2 weeks (listing week + next full week)
- 2WH = highest high of obs window = entry trigger
- 2WL = lowest low of obs window = initial stop loss
- R = 2WH - 2WL (risk per share)
- Enter when CLOSE crosses above 2WH on any day post obs window

## Targets
- T1 = Entry + 1R (take partial profit, move SL to breakeven)
- T2 = Entry + 2R (take more profit)
- T3 = Entry + 3R (final target, full exit)

## Trade Management
- SL = 2WL initially, locks at running_low on signal day
- After T1 hit → SL moves to Entry (breakeven, zero risk)
- Position size = floor(capital_allocated / entry_price)
- Gain uses best achieved target for realised trades, current price for open

## Scanner Status Values
| Status | Meaning |
|---|---|
| Watching | In observation window, not ready |
| Near Breakout | Obs window closed, within 3% of 2WH |
| Entry Trigger | Close crossed 2WH (FRESH — within 5 bars) |
| In Trade | Live position, no target hit yet |
| Entry Pending | Signal fired but price pulled back below entry |
| T1/T2/T3 Hit | Target achieved |
| SL Hit | Stopped out |
| Past | Signal older than 5 bars with no open alert |

## Key Files
- Strategy engine: `strategies/ipo_breakout.py` → `compute_scanner_states()`
- Alert pipeline: `ipo_alert.py` → `main()`
- Sheet columns: A–D user-managed, E–Q script-computed
- State tracking: `alert_state.json` (per-symbol last alerted status)
