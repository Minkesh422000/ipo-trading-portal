"""
core/claude_agent.py — Claude AI Agent for IPO Trading Portal.

Claude has 6 tools that map directly to existing core modules:
  scan_ipo_list      → scraper.fetch_ipo_listings()
  get_signal_states  → IPOBreakoutStrategy.compute_scanner_states()
  get_ohlc           → data_fetcher.fetch_ohlc()
  get_holdings       → db.get_holdings()
  get_pending_signals→ db.get_pending_signals()
  save_signal        → db.insert_signal() + notifier.send_signal_alert()

Agentic loop:
  - Non-streaming messages.create() calls
  - Generator yields events: text_delta | tool_start | tool_result | done | error
  - Caller (Streamlit page) renders each event immediately
  - MAX 10 iterations to prevent runaway loops

Prompt caching:
  - System prompt wrapped with cache_control: ephemeral
  - Reduces input token cost ~80% after first request in a session
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Generator, Optional


def is_configured() -> bool:
    """Return True if ANTHROPIC_API_KEY is set in secrets or environment."""
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
    except Exception:
        key = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(key)

# ── Constants ──────────────────────────────────────────────────────────────────

MODEL = "claude-opus-4-5"   # change to claude-opus-4-7 when available
MAX_ITERATIONS = 10

SYSTEM_PROMPT = """You are an expert IPO trading analyst embedded in an IPO Trading Portal for Indian equity markets (NSE).

## Your Role
You help users identify high-quality IPO breakout opportunities. You have access to real-time IPO data, OHLC price data, and the user's portfolio and signals. You reason systematically and explain your thinking clearly in plain language.

## Strategy: IPO 2-Week Breakout
1. **Observation Window**: First 10 trading days after listing.
2. **2-Week High**: Highest closing price in the observation window.
3. **Breakout Signal**: Price closes above the 2-week high after the window ends.
4. **Entry**: Open of the next bar after the signal bar.
5. **Stop-Loss**: Lowest low from listing to signal bar.
6. **Targets**: T1 = entry + 1R, T2 = entry + 2R, T3 = entry + 3R (R = entry − SL).
7. **Fresh Signal**: Breakout within the last 5 bars — highest priority.
8. **NEAR Signal**: Price within 3% of 2-week high — watch these.

## Signal Quality Framework

**Risk:Reward**
- Minimum: 2.5:1 (T3 must be ≥ 2.5× above entry)
- Good: 3.0:1 or higher
- Formula: (T3 − entry) / (entry − SL)

**Volume Quality** (use get_ohlc to verify)
- Breakout bar volume > average of prior 10 bars = strong signal
- Low-volume breakout = weak, likely to fail

**Days Since Listing**
- 30–90 days: ideal — momentum still active, IPO premium fading naturally
- < 30 days: higher volatility risk
- > 90 days: reduced IPO momentum catalyst

**Entry Status Priority**
- "⏳ Entry Tomorrow" → BEST: signal on latest bar, enter at tomorrow's open
- "🟡 In Trade +X%" → VALID: still above entry, check if R:R remains acceptable
- "🔴 Stopped Out" / "🏆 T3 Hit" → SKIP: do not generate new signal

## Workflow for Scanning
When the user asks you to scan and recommend signals:
1. Call get_pending_signals() — avoid duplicates.
2. Call get_signal_states(days_back=90) — get FRESH and NEAR setups.
3. Filter to FRESH only (status == "FRESH").
4. For top 3–5 candidates by R:R, call get_ohlc(symbol, days=20) to verify volume.
5. Score and rank: R:R > volume quality > days since listing.
6. Tell the user your findings with reasoning.
7. Ask before saving — do NOT save automatically unless user explicitly asked.

## Output Style
- Lead with verdict: "FRACTAL looks strong", "PNGSREVA is borderline"
- Always state R:R: "Entry ₹245 | SL ₹231 | T3 ₹287 | R:R 2.9:1"
- Use ₹ for prices, explain reasoning in 2–4 sentences
- When you save a signal, confirm: "✅ Signal saved for FRACTAL (ID: abc123)"

## Indian Market Context
- Prices in INR (₹), trading 9:15 AM – 3:30 PM IST, Mon–Fri
- NSE is primary exchange for IPO breakouts
- Mainboard IPOs (>₹500 Cr issue size) are higher quality than SME IPOs
- Market caps: Large >₹20,000 Cr | Mid ₹5,000–20,000 Cr | Small ₹500–5,000 Cr | Micro <₹500 Cr
- OHLC data from yfinance (NSE suffix), may have 1-day lag
- Holdings data may be stale if portfolio page not refreshed today

## Limitations
- You CANNOT place orders — save the signal and let the user confirm in the order panel
- No Level 2 / intraday data available
- Do not fabricate prices — always verify with get_ohlc() before quoting

## What NOT To Do
- Do not save signals for Stopped Out / T3 Hit / NO_DATA stocks
- Do not generate SELL signals (long-only strategy)
- Do not recommend position sizes without knowing the user's capital/risk settings
- Do not call save_signal more than once for the same symbol in a session"""


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "scan_ipo_list",
        "description": (
            "Fetch recent NSE IPO listings from the Chittorgarh database. "
            "Returns company name, NSE symbol, and listing date. "
            "Use this first to discover which IPOs are in scope."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Calendar days back to look for listings. Default 90, max 365.",
                    "default": 90,
                },
            },
            "required": ["days_back"],
        },
    },
    {
        "name": "get_signal_states",
        "description": (
            "Run the IPO 2-Week Breakout scanner and return current signal states. "
            "Returns FRESH (breakout within 5 bars) and NEAR (within 3% of breakout) signals. "
            "Each result includes entry_price, sl_price, T1/T2/T3, current_price, "
            "pct_to_breakout, entry_status, and bars_available. "
            "This is the primary tool for answering 'which IPOs look good today'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Calendar days back to scan for IPOs. Default 90.",
                    "default": 90,
                },
            },
            "required": ["days_back"],
        },
    },
    {
        "name": "get_ohlc",
        "description": (
            "Return the last N daily OHLC bars for a specific NSE symbol. "
            "Use this to verify breakout volume, check price action, and compute average volume. "
            "Always use the NSE trading symbol (e.g. 'PNGSREVA', not 'PNG Jewellers')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "NSE trading symbol (e.g. 'PNGSREVA').",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of recent trading days to return. Default 20.",
                    "default": 20,
                },
            },
            "required": ["symbol", "days"],
        },
    },
    {
        "name": "get_holdings",
        "description": (
            "Return current equity holdings cached in the DB for a specific account. "
            "Use this to check if an account already holds a symbol before generating a buy signal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "The account UUID from the accounts list.",
                },
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "get_pending_signals",
        "description": (
            "Return all PENDING signals from the signals table. "
            "Use this to avoid creating duplicate signals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "save_signal",
        "description": (
            "Save an AI-generated trading signal to the signals table with PENDING status. "
            "Only call this after reasoning about the trade and confirming it meets criteria. "
            "A Telegram alert is sent automatically after saving. "
            "The reasoning field is critical — write 2-4 sentences explaining "
            "breakout quality, volume, R:R ratio, and days since listing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "NSE trading symbol."},
                "company": {"type": "string", "description": "Human-readable company name."},
                "action": {
                    "type": "string",
                    "enum": ["BUY"],
                    "description": "Trade direction. Only BUY signals supported.",
                },
                "entry_price": {"type": "number", "description": "Entry price in INR."},
                "sl_price": {"type": "number", "description": "Stop-loss price in INR (below entry)."},
                "t1": {"type": "number", "description": "Target 1 (entry + 1R)."},
                "t2": {"type": "number", "description": "Target 2 (entry + 2R)."},
                "t3": {"type": "number", "description": "Target 3 (entry + 3R)."},
                "quantity": {"type": "integer", "description": "Number of shares."},
                "account_id": {"type": "string", "description": "Target account UUID."},
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Your reasoning in 2-4 sentences: breakout quality, volume, "
                        "R:R ratio, days since listing, and why this stands out."
                    ),
                },
            },
            "required": [
                "symbol", "company", "action", "entry_price", "sl_price",
                "t1", "t2", "t3", "quantity", "account_id", "reasoning",
            ],
        },
    },
]


# ── Client singleton ───────────────────────────────────────────────────────────

def _get_client():
    """Return an Anthropic client using the API key from Streamlit secrets or env."""
    try:
        import anthropic
        import streamlit as st
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
    except Exception:
        import anthropic
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return anthropic.Anthropic(api_key=api_key)


def _build_system_with_cache() -> list[dict]:
    """System prompt with cache_control so it's cached after the first request."""
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


# ── Tool implementations ───────────────────────────────────────────────────────

def _tool_scan_ipo_list(days_back: int, conn) -> str:
    try:
        from scraper import fetch_ipo_listings
        today = date.today()
        from_date = today - timedelta(days=int(days_back))
        ipos = fetch_ipo_listings(from_date, today, conn)
        result = [
            {
                "name": ipo.get("name"),
                "nse_symbol": ipo.get("nse_symbol"),
                "listing_date": ipo["listing_date"].isoformat()
                    if hasattr(ipo.get("listing_date"), "isoformat")
                    else str(ipo.get("listing_date")),
                "listing_at": ipo.get("listing_at", ""),
            }
            for ipo in ipos
            if ipo.get("nse_symbol")
        ]
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _tool_get_signal_states(days_back: int, conn) -> str:
    try:
        from scraper import fetch_ipo_listings
        from core.data_fetcher import fetch_all_ohlc
        from strategies.ipo_breakout import IPOBreakoutStrategy

        today = date.today()
        from_date = today - timedelta(days=int(days_back))
        ipo_list = fetch_ipo_listings(from_date, today, conn)
        ohlc_data = fetch_all_ohlc(ipo_list, conn=conn)
        states = IPOBreakoutStrategy.compute_scanner_states(ipo_list, ohlc_data)

        # Return only FRESH and NEAR to keep payload manageable
        filtered = [
            s for s in states
            if s.get("status") in ("FRESH", "NEAR")
        ]
        return json.dumps(filtered, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _tool_get_ohlc(symbol: str, days: int, conn) -> str:
    try:
        from core.data_fetcher import fetch_ohlc
        today = date.today()
        from_date = today - timedelta(days=int(days) * 2)  # extra buffer for weekends
        bars = fetch_ohlc(symbol, from_date, today, conn=conn)
        # Return last N bars
        result = bars[-int(days):]
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _tool_get_holdings(account_id: str, conn) -> str:
    try:
        from core.db import get_holdings
        holdings = get_holdings(conn, account_id)
        return json.dumps([dict(h) for h in holdings], default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _tool_get_pending_signals(conn) -> str:
    try:
        from core.db import get_pending_signals
        signals = get_pending_signals(conn)
        return json.dumps([dict(s) for s in signals], default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _tool_save_signal(
    symbol: str,
    company: str,
    action: str,
    entry_price: float,
    sl_price: float,
    t1: float,
    t2: float,
    t3: float,
    quantity: int,
    account_id: str,
    reasoning: str,
    conn,
) -> str:
    try:
        from core.db import insert_signal
        from core.notifier import send_signal_alert, is_configured

        signal_id = str(uuid.uuid4())
        signal_dict = {
            "id": signal_id,
            "strategy_id": "AI_AGENT",
            "account_id": account_id,
            "symbol": symbol,
            "company": company,
            "signal_type": action,
            "entry_price": float(entry_price),
            "sl_price": float(sl_price),
            "t1": float(t1),
            "t2": float(t2),
            "t3": float(t3),
            "quantity": int(quantity),
            "generated_at": datetime.utcnow().isoformat(),
            "status": "PENDING",
            "order_id": None,
            "notes": reasoning,
        }
        insert_signal(conn, signal_dict)

        # Send Telegram alert
        if is_configured():
            send_signal_alert(signal_dict, source="AI Agent")

        return json.dumps({"signal_id": signal_id, "status": "saved", "symbol": symbol})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Tool dispatch ──────────────────────────────────────────────────────────────

def _execute_tool(tool_name: str, tool_input: dict, conn) -> str:
    """Route tool_use block to the correct function. Never raises."""
    try:
        if tool_name == "scan_ipo_list":
            return _tool_scan_ipo_list(tool_input.get("days_back", 90), conn)
        elif tool_name == "get_signal_states":
            return _tool_get_signal_states(tool_input.get("days_back", 90), conn)
        elif tool_name == "get_ohlc":
            return _tool_get_ohlc(tool_input["symbol"], tool_input.get("days", 20), conn)
        elif tool_name == "get_holdings":
            return _tool_get_holdings(tool_input["account_id"], conn)
        elif tool_name == "get_pending_signals":
            return _tool_get_pending_signals(conn)
        elif tool_name == "save_signal":
            return _tool_save_signal(**tool_input, conn=conn)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        return json.dumps({"error": f"Tool execution error: {e}"})


# ── Agentic loop ───────────────────────────────────────────────────────────────

def run_agent(
    user_message: str,
    conversation_history: list[dict],
    conn,
) -> Generator[dict, None, None]:
    """
    Execute one turn of the agentic loop.

    Yields dicts:
        {"type": "text_delta",   "text": str}
        {"type": "tool_start",   "tool_name": str, "tool_input": dict}
        {"type": "tool_result",  "tool_name": str, "result": str}
        {"type": "done",         "updated_history": list[dict], "saved_signal": dict|None}
        {"type": "error",        "message": str}
    """
    import anthropic
    import os

    client = _get_client()
    messages = conversation_history + [{"role": "user", "content": user_message}]
    last_saved_signal: Optional[dict] = None

    for iteration in range(MAX_ITERATIONS):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=8096,
                system=_build_system_with_cache(),
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            yield {"type": "error", "message": f"API error: {e}"}
            return

        # Yield any text content
        for block in response.content:
            if block.type == "text" and block.text:
                yield {"type": "text_delta", "text": block.text}

        # Done
        if response.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": response.content})
            yield {
                "type": "done",
                "updated_history": messages,
                "saved_signal": last_saved_signal,
            }
            return

        # Tool use
        if response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tb in tool_use_blocks:
                yield {"type": "tool_start", "tool_name": tb.name, "tool_input": tb.input}
                result = _execute_tool(tb.name, tb.input, conn)
                yield {"type": "tool_result", "tool_name": tb.name, "result": result}

                # Track if a signal was just saved
                if tb.name == "save_signal":
                    try:
                        res_data = json.loads(result)
                        if "signal_id" in res_data:
                            last_saved_signal = {**tb.input, "id": res_data["signal_id"]}
                    except Exception:
                        pass

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})
            continue

        yield {"type": "error", "message": f"Unexpected stop_reason: {response.stop_reason}"}
        return

    yield {"type": "error", "message": "Max iterations reached. Try a simpler request."}


def get_ltp(symbol: str) -> Optional[float]:
    """
    Fetch the latest traded price for an NSE symbol via yfinance.
    Returns None if unavailable.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol}.NS")
        price = ticker.fast_info.last_price
        return round(float(price), 2) if price else None
    except Exception:
        return None
