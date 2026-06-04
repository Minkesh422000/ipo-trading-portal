---
name: check-sheet
---

Verify Google Sheet is correctly configured and accessible.

1. Check GSHEET_CSV_URL env var is set
2. Fetch the CSV: `python3 -c "import requests; r=requests.get('$GSHEET_CSV_URL'); print(r.status_code, r.text[:500])"`
3. Verify columns A–Q headers are present (nse_symbol, name, listing_date, capital_allocated, status, ...)
4. Check GSHEET_SERVICE_ACCOUNT_JSON is set for write-back
5. Test gspread connection: try opening the sheet and reading row 1
6. Report: sheet accessible ✅/❌, headers correct ✅/❌, write access ✅/❌
