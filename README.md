# IPO Trading Portal

A multi-account IPO breakout trading portal with AI-assisted signal generation.

## What it does
- Tracks recent IPO listings and detects **2-week breakout signals**
- Manages **multiple Zerodha Kite accounts** (own + trusted people)
- **Claude AI Agent** scans IPOs, reasons about quality, and saves the best setups
- Places protected orders with automatic OCO GTT (stop-loss + target)
- Sends **Telegram alerts** on new signals and order placements
- Works locally (SQLite) or in the cloud (Supabase)

## Pages
| Page | Purpose |
|------|---------|
| 🏠 Home | Consolidated portfolio + pending signals |
| 👤 Accounts | Add Zerodha accounts, complete daily OAuth login |
| 💼 Portfolio | Holdings, positions, margins per account |
| 📊 Signals | Run strategy, review signals, place trades |
| 📋 Orders | Order history, GTT management |
| ⚙️ Strategies | Configure strategies, assign to accounts |
| 📈 Backtester | Backtest IPO breakout strategy on historical data |
| 🤖 AI Agent | Chat with Claude to scan IPOs and save signals |

## Setup

### Local Development
```bash
pip install -r requirements.txt
# Fill in .streamlit/secrets.toml (copy from the template below)
streamlit run app.py
```

### Secrets Template (`.streamlit/secrets.toml`)
```toml
DATABASE_MODE = "sqlite"          # "sqlite" local | "supabase" cloud
DATA_SOURCE = "yfinance"          # "yfinance" free | "kite" paid
ENCRYPTION_KEY = "your-32-char-key"
ANTHROPIC_API_KEY = "sk-ant-..."
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
```

### Streamlit Cloud Deployment
1. Push to GitHub
2. Connect repo at [share.streamlit.io](https://share.streamlit.io)
3. Set secrets in the Streamlit Cloud dashboard (same keys as above, plus Supabase credentials)
4. In Supabase SQL Editor, disable RLS on all tables (see `docs/supabase_setup.md`)

## Project Structure
```
├── app.py              Entry point (home dashboard)
├── scraper.py          IPO data scraper (Chittorgarh)
├── charts.py           Plotly chart helpers
├── strategy.py         Legacy backtest engine (used by Backtester page)
├── core/               Business logic
│   ├── db.py           Dual-mode DB (SQLite / Supabase)
│   ├── kite_manager.py Multi-account Kite connection pool
│   ├── order_manager.py Order + GTT placement
│   ├── data_fetcher.py OHLC data (yfinance or Kite)
│   ├── strategy_engine.py Strategy runner
│   ├── claude_agent.py Claude AI agent + tools
│   └── notifier.py     Telegram notifications
├── pages/              Streamlit multi-page UI
├── strategies/         Pluggable strategy implementations
├── tests/              Pytest test suite
└── docs/               Architecture notes, watchlists
```

## Data Sources
- **IPO list**: Chittorgarh (free, no auth)
- **OHLC data**: yfinance (free, default) or Kite API (paid, better quality)
- **Order execution**: Zerodha Kite API (each account = ₹500/month)
