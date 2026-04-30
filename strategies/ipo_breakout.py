"""
strategies/ipo_breakout.py — IPO 2-Week Breakout Strategy (live signal generation).

Strategy logic:
1. Observation window: first `lookback_bars` trading days post-listing
2. 2-week high = max(close) over observation window
3. Signal: close > 2-week high (first occurrence AFTER observation window)
4. Entry: next bar's open price
5. SL: lowest low from listing to signal bar
6. Targets: T1 = entry + 1R, T2 = entry + 2R, T3 = entry + 3R

This class generates LIVE signals — i.e., setups that are actionable TODAY,
not historical backtest trades. The backtester in strategy.py (legacy) is kept
for the Backtester page.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import floor
from typing import Optional

from strategies.base import BaseStrategy, Signal


class IPOBreakoutStrategy(BaseStrategy):
    name = "IPO 2-Week Breakout"
    type = "IPO_BREAKOUT"
    description = (
        "Waits for the 2-week (10-bar) consolidation post-listing, then enters "
        "when price closes above the 2-week high. SL at pre-entry lowest low. "
        "Targets at 1R / 2R / 3R with partial exits."
    )

    def get_default_params(self) -> dict:
        return {
            "lookback_bars": 10,       # observation window in trading days
            "t1_mult": 1.0,            # T1 R-multiple
            "t2_mult": 2.0,            # T2 R-multiple
            "t3_mult": 3.0,            # T3 R-multiple
            "max_days_since_listing": 90,  # ignore IPOs older than this
            "min_bars_required": 11,   # skip if fewer bars available
            "fresh_signal_window": 5,  # signal must have triggered within last N bars
        }

    def generate_signals(
        self,
        ipo_list: list[dict],
        ohlc_data: dict[str, list[dict]],
        params: dict,
        capital: float,
        risk_pct: float,
        existing_holdings: list[dict],
    ) -> list[Signal]:
        """Return signals for IPOs that have JUST crossed their 2-week high."""
        p = {**self.get_default_params(), **params}
        lookback = p["lookback_bars"]
        t1_mult = p["t1_mult"]
        t2_mult = p["t2_mult"]
        t3_mult = p["t3_mult"]
        max_age = p["max_days_since_listing"]
        min_bars = p["min_bars_required"]
        fresh_window = p["fresh_signal_window"]

        today = date.today()
        signals = []

        for ipo in ipo_list:
            sym = ipo.get("nse_symbol", "")
            name = ipo.get("name", sym)
            listing_date = ipo.get("listing_date")

            if not sym or not listing_date:
                continue

            # Convert listing_date to date object
            if isinstance(listing_date, str):
                try:
                    listing_date = date.fromisoformat(listing_date)
                except ValueError:
                    continue

            # Skip if IPO is too old
            days_since_listing = (today - listing_date).days
            if days_since_listing > max_age:
                continue

            # Skip if already holding
            if self._already_holding(sym, existing_holdings):
                continue

            bars = ohlc_data.get(sym, [])
            if len(bars) < min_bars:
                continue

            # Observation window
            obs_bars = bars[:lookback]
            two_week_high = max(b["close"] for b in obs_bars)

            # Find the most recent signal bar (close > 2-week high, after observation window)
            signal_bar_idx = None
            for i in range(lookback, len(bars)):
                if bars[i]["close"] > two_week_high:
                    signal_bar_idx = i

            if signal_bar_idx is None:
                continue  # no breakout ever

            # Check if the signal is "fresh" — triggered within last fresh_window bars
            bars_since_signal = len(bars) - 1 - signal_bar_idx
            if bars_since_signal > fresh_window:
                continue  # signal is too old

            # Entry: next bar's open (if available) or current bar's close as estimate
            if signal_bar_idx + 1 < len(bars):
                entry_bar = bars[signal_bar_idx + 1]
                entry_price = entry_bar["open"]
            else:
                # Signal was on the LAST bar — entry would be at tomorrow's open
                entry_bar = bars[signal_bar_idx]
                entry_price = entry_bar["close"]  # estimate with last close

            sl_price = min(b["low"] for b in bars[:signal_bar_idx + 1])
            R = entry_price - sl_price

            if R <= 0:
                continue

            position_size = floor((capital * risk_pct) / R)
            if position_size <= 0:
                continue

            t1 = round(entry_price + t1_mult * R, 2)
            t2 = round(entry_price + t2_mult * R, 2)
            t3 = round(entry_price + t3_mult * R, 2)

            # Build reason string for UI display
            reason = (
                f"2W high: ₹{two_week_high:.2f} | "
                f"Signal {bars_since_signal} bar(s) ago | "
                f"R=₹{R:.2f}"
            )

            signals.append(Signal(
                symbol=sym,
                company=name,
                action="BUY",
                entry_price=round(entry_price, 2),
                sl_price=round(sl_price, 2),
                t1=t1,
                t2=t2,
                t3=t3,
                quantity=position_size,
                strategy_id="",    # filled in by strategy_engine
                account_id="",     # filled in by strategy_engine
                reason=reason,
            ))

        return signals

    # ── Helper: compute current signal state for the Live Scanner tab ──────────

    @staticmethod
    def compute_scanner_states(
        ipo_list: list[dict],
        ohlc_data: dict[str, list[dict]],
        lookback_bars: int = 10,
        market_caps: dict[str, Optional[float]] = None,
    ) -> list[dict]:
        """
        For each IPO, compute full signal state for the Live Scanner tab.

        Returns list of dicts with:
            symbol, company, listing_date, days_since_listing,
            two_week_high, signal_date, entry_price, sl_price, t1, t2, t3,
            t1_hit, t2_hit, t3_hit, current_price, pct_to_breakout,
            entry_status, status, bars_available, market_cap_cr

        Status values:
            WATCHING  — still in observation window (< lookback_bars days)
            NEAR      — past window, within 3% of 2-week high, no breakout yet
            FRESH     — crossed 2-week high within last 5 bars
            PAST      — crossed 2-week high more than 5 bars ago
            NO_DATA   — no OHLC data available

        Entry Status values (only for FRESH/PAST):
            ⏳ Entry Tomorrow  — signal on latest bar, entry next session
            🏆 T3 Hit          — all targets achieved
            ✅ T2 Hit          — T2 achieved, holding remainder
            🟢 T1 Hit          — T1 achieved, SL at breakeven
            🔴 Stopped Out     — SL was hit after entry
            🟡 In Trade        — above entry, T1 not yet hit
            ⚠️ Below Entry     — price dipped below entry (still above SL)
        """
        today = date.today()
        market_caps = market_caps or {}
        results = []

        for ipo in ipo_list:
            sym = ipo.get("nse_symbol", "")
            name = ipo.get("name", sym)
            listing_date = ipo.get("listing_date")

            if not sym or not listing_date:
                continue

            if isinstance(listing_date, str):
                try:
                    listing_date = date.fromisoformat(listing_date)
                except ValueError:
                    continue

            days_since = (today - listing_date).days
            bars = ohlc_data.get(sym, [])
            mc_cr = market_caps.get(sym)

            # ── No data ────────────────────────────────────────────────────────
            if not bars:
                results.append({
                    "symbol": sym, "company": name,
                    "listing_date": listing_date.isoformat(),
                    "days_since_listing": days_since,
                    "two_week_high": None, "signal_date": None,
                    "entry_price": None, "sl_price": None,
                    "t1": None, "t2": None, "t3": None,
                    "t1_hit": False, "t2_hit": False, "t3_hit": False,
                    "current_price": None, "pct_to_breakout": None,
                    "entry_status": "-", "status": "NO_DATA",
                    "bars_available": 0, "market_cap_cr": mc_cr,
                })
                continue

            current_price = bars[-1]["close"]
            n_bars = len(bars)

            # ── Still in observation window ────────────────────────────────────
            if n_bars <= lookback_bars:
                two_week_high = max(b["close"] for b in bars)
                results.append({
                    "symbol": sym, "company": name,
                    "listing_date": listing_date.isoformat(),
                    "days_since_listing": days_since,
                    "two_week_high": round(two_week_high, 2),
                    "signal_date": None,
                    "entry_price": None, "sl_price": None,
                    "t1": None, "t2": None, "t3": None,
                    "t1_hit": False, "t2_hit": False, "t3_hit": False,
                    "current_price": round(current_price, 2),
                    "pct_to_breakout": round(
                        (two_week_high - current_price) / two_week_high * 100, 2
                    ) if two_week_high else None,
                    "entry_status": "-", "status": "WATCHING",
                    "bars_available": n_bars, "market_cap_cr": mc_cr,
                })
                continue

            # ── Past observation window ────────────────────────────────────────
            obs_bars = bars[:lookback_bars]
            two_week_high = max(b["close"] for b in obs_bars)

            # Find FIRST signal bar (first close > 2W high after obs window)
            first_signal_idx = None
            for i in range(lookback_bars, n_bars):
                if bars[i]["close"] > two_week_high:
                    first_signal_idx = i
                    break

            pct_away = round(
                (two_week_high - current_price) / two_week_high * 100, 2
            ) if two_week_high else 0.0

            # ── No signal ever ─────────────────────────────────────────────────
            if first_signal_idx is None:
                status = "NEAR" if abs(pct_away) <= 3.0 else "WATCHING"
                results.append({
                    "symbol": sym, "company": name,
                    "listing_date": listing_date.isoformat(),
                    "days_since_listing": days_since,
                    "two_week_high": round(two_week_high, 2),
                    "signal_date": None,
                    "entry_price": None, "sl_price": None,
                    "t1": None, "t2": None, "t3": None,
                    "t1_hit": False, "t2_hit": False, "t3_hit": False,
                    "current_price": round(current_price, 2),
                    "pct_to_breakout": pct_away,
                    "entry_status": "-", "status": status,
                    "bars_available": n_bars, "market_cap_cr": mc_cr,
                })
                continue

            # ── Signal exists — compute full trade details ─────────────────────
            signal_bar = bars[first_signal_idx]
            signal_date = signal_bar["date"]
            bars_since_signal = n_bars - 1 - first_signal_idx
            status = "FRESH" if bars_since_signal <= 5 else "PAST"

            # Entry: next bar's open after signal
            if first_signal_idx + 1 < n_bars:
                entry_bar = bars[first_signal_idx + 1]
                entry_price = round(entry_bar["open"], 2)
                entry_pending = False
            else:
                # Signal on the very last bar — entry tomorrow
                entry_price = round(signal_bar["close"], 2)
                entry_pending = True

            sl_price = round(min(b["low"] for b in bars[:first_signal_idx + 1]), 2)
            R = entry_price - sl_price

            if R <= 0:
                entry_status = "⚠️ Invalid R"
                t1 = t2 = t3 = None
                t1_hit = t2_hit = t3_hit = False
            else:
                t1 = round(entry_price + R, 2)
                t2 = round(entry_price + 2 * R, 2)
                t3 = round(entry_price + 3 * R, 2)

                if entry_pending:
                    entry_status = "⏳ Entry Tomorrow"
                    t1_hit = t2_hit = t3_hit = False
                else:
                    # Check post-entry bars for target/SL hits
                    post_entry = bars[first_signal_idx + 2:]

                    t1_hit = any(b["high"] >= t1 for b in post_entry)
                    t2_hit = t1_hit and any(b["high"] >= t2 for b in post_entry)
                    t3_hit = t2_hit and any(b["high"] >= t3 for b in post_entry)

                    # After T1, SL moves to entry (breakeven)
                    effective_sl = entry_price if t1_hit else sl_price
                    stopped_out = any(b["low"] <= effective_sl for b in post_entry)

                    # Current entry status
                    if t3_hit:
                        entry_status = "🏆 T3 Hit"
                    elif t2_hit:
                        entry_status = "✅ T2 Hit — Holding"
                    elif t1_hit:
                        entry_status = "🟢 T1 Hit — SL @ BE"
                    elif stopped_out:
                        entry_status = "🔴 Stopped Out"
                    elif current_price >= entry_price:
                        pct_up = (current_price - entry_price) / entry_price * 100
                        entry_status = f"🟡 In Trade +{pct_up:.1f}%"
                    else:
                        pct_dn = (entry_price - current_price) / entry_price * 100
                        entry_status = f"⚠️ Below Entry -{pct_dn:.1f}%"

            results.append({
                "symbol": sym,
                "company": name,
                "listing_date": listing_date.isoformat(),
                "days_since_listing": days_since,
                "two_week_high": round(two_week_high, 2),
                "signal_date": signal_date,
                "entry_price": entry_price,
                "sl_price": sl_price,
                "t1": t1, "t2": t2, "t3": t3,
                "t1_hit": t1_hit, "t2_hit": t2_hit, "t3_hit": t3_hit,
                "current_price": round(current_price, 2),
                "pct_to_breakout": pct_away,
                "entry_status": entry_status,
                "status": status,
                "bars_available": n_bars,
                "market_cap_cr": mc_cr,
            })

        # Sort: FRESH → NEAR → WATCHING → PAST → NO_DATA
        order = {"FRESH": 0, "NEAR": 1, "WATCHING": 2, "PAST": 3, "NO_DATA": 4}
        results.sort(key=lambda x: order.get(x["status"], 5))
        return results

    @staticmethod
    def fetch_market_caps(symbols: list[str]) -> dict[str, Optional[float]]:
        """
        Fetch market caps (in ₹ Crores) for a list of NSE symbols via yfinance.
        Returns {symbol: market_cap_cr} — None if unavailable.
        """
        result: dict[str, Optional[float]] = {}
        try:
            import yfinance as yf
        except ImportError:
            return {s: None for s in symbols}

        for sym in symbols:
            try:
                fi = yf.Ticker(f"{sym}.NS").fast_info
                mc = getattr(fi, "market_cap", None)
                result[sym] = round(mc / 1e7, 0) if mc else None  # convert ₹ → Crores
            except Exception:
                result[sym] = None

        return result
