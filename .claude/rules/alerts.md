---
paths:
  - "core/notifier.py"
  - "ipo_alert.py"
---

# Alert Rules

## Telegram
- Always use `parse_mode="HTML"` — never Markdown (breaks on special chars)
- Bold: `<b>text</b>` | Italic: `<i>text</i>` | Link: `<a href="url">text</a>`
- Max message length: 4096 chars — truncate if needed
- Always check return value of `send_message()` — log failure, don't raise

## Alert Deduplication
- Load `alert_state.json` at start, save at end
- Only send NEAR alert on transition → NEAR (not on every run)
- Only send FRESH alert on transition → FRESH (not on every run)
- State keys are NSE symbols (uppercase), values are: WATCHING, NEAR, FRESH, PAST

## Message Format
- NEAR: ⚠️ header, obs window closed, 2WH entry, SL, R, T1/T2/T3, chart link
- FRESH: 🚨 header, signal date, entry/SL/R, T1/T2/T3, R:R ratio, capital/qty if set
- EOD summary: ✅ header, run time IST, scanned count, alerts sent, status breakdown, sheet link

## Never
- Send alerts for WATCHING or PAST status
- Send the same alert twice for the same symbol + status
- Use WhatsApp or SMS — Telegram only
