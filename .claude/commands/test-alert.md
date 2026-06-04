---
name: test-alert
argument-hint: [local|live]
---

Test the IPO alert pipeline end-to-end.

If $ARGUMENTS is "live" or empty, use the real Google Sheet URL from env.
If $ARGUMENTS is "local", use sample_ipos.csv.

Steps:
1. Check required env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GSHEET_CSV_URL
2. If local: `GSHEET_CSV_URL=sample_ipos.csv TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID python ipo_alert.py`
3. If live: `python ipo_alert.py`
4. Confirm output: IPOs loaded → OHLC fetched → scan complete → Telegram sent
5. Show last 20 lines of output
6. Report: how many IPOs scanned, any alerts sent, any errors
