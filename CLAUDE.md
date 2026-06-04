# Project Brain — Stock Strategy Builder

## Stack
- **Language:** Python 3.11
- **Data:** yfinance (free OHLC), Chittorgarh API (IPO listings)
- **Alerts:** Telegram Bot API via `core/notifier.py`
- **Sheet:** Google Sheets (read via CSV URL, write via gspread + Service Account)
- **State:** `alert_state.json` (committed to repo) or Vercel KV
- **Scheduler:** GitHub Actions cron (Mon–Fri 10:35 UTC = 4:05 PM IST)
- **Deployment:** GitHub Actions (primary) | Vercel serverless (backup)

## Key Files
| File | Purpose |
|---|---|
| `ipo_alert.py` | Main pipeline — fetch → compute → alert → write sheet |
| `strategies/ipo_breakout.py` | 2-Week Breakout strategy engine |
| `core/notifier.py` | Telegram send_message() |
| `scraper.py` | Chittorgarh IPO listings API |
| `alert_state.json` | Per-symbol last alerted status (dedup) |
| `sample_ipos.csv` | Local test data (7 IPOs, no auth needed) |
| `.github/workflows/ipo_alerts.yml` | GitHub Actions cron workflow |
| `api/ipo_check.py` | Vercel serverless handler |

## Commands
```bash
python ipo_alert.py                     # Run full pipeline (needs env vars)
GSHEET_CSV_URL=sample_ipos.csv \
  TELEGRAM_BOT_TOKEN=... \
  TELEGRAM_CHAT_ID=... \
  python ipo_alert.py                   # Local test with sample data
```

## Environment Variables
| Variable | Required | Description |
|---|---|---|
| `GSHEET_CSV_URL` | ✅ | Google Sheet CSV export URL |
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | Your Telegram user ID |
| `GSHEET_SERVICE_ACCOUNT_JSON` | Optional | Base64 or raw JSON for sheet write-back |

## Conventions
- Python type hints on all functions
- No bare `except` — catch specific exceptions
- `[MODULE]` prefix on all print statements: `[SHEET]`, `[OHLC]`, `[TG]`, `[SCAN]`
- Never commit `.streamlit/secrets.toml` or any file with real credentials
- Telegram messages use HTML parse mode only (`<b>`, `<i>`, `<a href>`)
- Alert deduplication via `alert_state.json` — only send on status transition

## Sheet Column Layout
```
A: nse_symbol    B: name         C: listing_date   D: capital_allocated  ← USER FILLS
E: status        F: entry_price  G: sl_price                              ← SCRIPT WRITES
H: t1  I: t1_hit_date  J: t2  K: t2_hit_date  L: t3  M: t3_hit_date
N: current_price  O: qty  P: gain_pct  Q: gain_inr
```

## Agents (`.claude/agents/`)
| Agent | Use when |
|---|---|
| `code-reviewer` | Before any commit touching strategy or alert logic |
| `debugger` | Pipeline fails, unexpected output, wrong status |
| `strategy-analyst` | Changing strategy maths or adding new strategy |
| `sheet-writer` | Google Sheet read/write issues |
| `alert-tester` | End-to-end test of the full pipeline |
| `data-fetcher` | yfinance errors, missing OHLC, Chittorgarh sync issues |

## Custom Commands
| Command | Usage |
|---|---|
| `/test-alert` | Run full pipeline locally and verify Telegram |
| `/fix-issue` | Fix a GitHub issue end-to-end |
| `/add-strategy` | Scaffold a new trading strategy |
| `/check-sheet` | Verify sheet connectivity and column headers |

## graphify
This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents

### 3. Self-Improvement Loop
- After ANY correction from the user: update tasks/lessons.md with the pattern
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Ask yourself: "Would a staff engineer approve this?"

### 5. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them

## Core Principles
- Simplicity First: Make every change as simple as possible. Minimal code impact.
- No Laziness: Find root causes. No temporary fixes. Senior developer standards.
- Minimal Impact: Only touch what's necessary. No side effects.
