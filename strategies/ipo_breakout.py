"""
strategies/ipo_breakout.py — IPO 2-Week Breakout Strategy (live signal generation).

Strategy logic:
1. Observation window: calendar-week based — listing week + the NEXT full calendar week.
   e.g. listed Wednesday → obs window ends the Friday of the following week.
2. 2-week high (2WH) = max(bar high) over observation window
3. 2-week low  (2WL) = min(bar low)  over observation window
4. Signal: price crosses above 2WH after obs window ends
5. Entry: LIMIT order placed at 2WH (executes when price touches that level)
6. SL: 2WL (fixed from obs window, placed as GTT single trigger)
7. Targets: T1 = entry+1R, T2 = entry+2R, T3 = entry+3R  (R = 2WH - 2WL)
"""
from __future__ import annotations

from datetime import date, timedelta
from math import floor
from typing import Optional

from strategies.base import BaseStrategy, Signal


def _obs_window_end(listing_date: date) -> date:
    """
    Return the last date of the observation window.

    Rule: listing week (Mon-Fri containing listing_date) PLUS the next full week.
    'Listing week Friday' = listing_date + (4 - weekday) days.
    Then add 7 more days to reach the following Friday.
    """
    days_to_friday = 4 - listing_date.weekday()  # 0=Mon … 4=Fri
    if days_to_friday < 0:
        days_to_friday += 7  # shouldn't happen for weekday listings, but guard it
    listing_week_friday = listing_date + timedelta(days=days_to_friday)
    return listing_week_friday + timedelta(weeks=1)


class IPOBreakoutStrategy(BaseStrategy):
    name = "IPO 2-Week Breakout"
    type = "IPO_BREAKOUT"
    description = (
        "Waits for the 2-calendar-week consolidation post-listing, then enters "
        "with a LIMIT order at the 2-week high. SL at 2-week low (GTT). "
        "T1/T2/T3 at 1R/2R/3R with automatic partial exits."
    )

    def get_default_params(self) -> dict:
        return {
            "t1_mult": 1.0,
            "t2_mult": 2.0,
            "t3_mult": 3.0,
            "max_days_since_listing": 90,
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
        """Return signals for IPOs whose obs window has closed and 2WH hasn't been entered yet."""
        p = {**self.get_default_params(), **params}
        t1_mult = p["t1_mult"]
        t2_mult = p["t2_mult"]
        t3_mult = p["t3_mult"]
        max_age = p["max_days_since_listing"]

        today = date.today()
        signals = []

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

            days_since_listing = (today - listing_date).days
            if days_since_listing > max_age:
                continue

            if self._already_holding(sym, existing_holdings):
                continue

            bars = ohlc_data.get(sym, [])
            if not bars:
                continue

            obs_end = _obs_window_end(listing_date)

            # Observation bars: all bars on or before obs_end
            obs_bars = [b for b in bars if _bar_date(b) <= obs_end]
            post_bars = [b for b in bars if _bar_date(b) > obs_end]

            if not obs_bars or not post_bars:
                continue  # obs window not yet complete, or no post-window data

            two_week_high = max(b["high"] for b in obs_bars)

            # SL = lowest low from listing date all the way to breakout day
            # (matches Pine Script: preEntryLowest keeps updating until entryLocked)
            # Before breakout: SL = min(low) of ALL bars seen so far post-listing
            # At breakout: SL locked at that day's running low
            all_bars_so_far = obs_bars + post_bars
            two_week_low = min(b["low"] for b in obs_bars)   # baseline from obs window

            # Find first bar where CLOSE crosses above 2WH (Pine Script: ta.crossover close)
            breakout_idx = None
            running_low  = two_week_low
            for i, b in enumerate(post_bars):
                running_low = min(running_low, b["low"])      # keep updating daily
                if b["close"] > two_week_high:                # close crossover — matches Pine
                    breakout_idx = i
                    break

            # Signal: no breakout yet → LIMIT order candidate
            # (if breakout happened, we'd need to track the live trade instead)
            if breakout_idx is not None:
                continue  # already broken out — skip

            sl_price = round(running_low, 2)   # locked at lowest low up to today
            R = two_week_high - sl_price

            if R <= 0:
                continue

            entry_price = round(two_week_high, 2)
            position_size = floor((capital * risk_pct / 100) / R)

            if position_size <= 0:
                continue

            t1 = round(entry_price + t1_mult * R, 2)
            t2 = round(entry_price + t2_mult * R, 2)
            t3 = round(entry_price + t3_mult * R, 2)

            reason = (
                f"2W high: ₹{two_week_high:.2f} | "
                f"2W low: ₹{two_week_low:.2f} | "
                f"R=₹{R:.2f} | obs ended {obs_end.isoformat()}"
            )

            signals.append(Signal(
                symbol=sym,
                company=name,
                action="BUY",
                entry_price=entry_price,
                sl_price=sl_price,
                t1=t1,
                t2=t2,
                t3=t3,
                quantity=position_size,
                strategy_id="",
                account_id="",
                reason=reason,
            ))

        return signals

    # ── Scanner states for the Live Scanner tab ─────────────────────────────────

    @staticmethod
    def compute_scanner_states(
        ipo_list: list[dict],
        ohlc_data: dict[str, list[dict]],
        lookback_bars: int = 10,          # kept for API compat, ignored internally
        market_caps: dict[str, Optional[float]] = None,
    ) -> list[dict]:
        """
        For each IPO compute full signal state for the Live Scanner tab.

        Status values:
            WATCHING  — obs window not yet complete
            NEAR      — obs window done, within 3% of 2WH, no breakout yet
            FRESH     — crossed 2WH within last 5 bars
            PAST      — crossed 2WH more than 5 bars ago
            NO_DATA   — no OHLC data

        Entry status values (FRESH/PAST only):
            ⏳ Entry Pending   — LIMIT not yet filled (price still below 2WH)
            🏆 T3 Hit
            ✅ T2 Hit
            🟢 T1 Hit — SL @ BE
            🔴 Stopped Out
            🟡 In Trade +X%
            ⚠️ Below Entry -X%
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

            if not bars:
                results.append(_no_data_row(sym, name, listing_date, days_since, mc_cr))
                continue

            obs_end = _obs_window_end(listing_date)
            obs_bars  = [b for b in bars if _bar_date(b) <= obs_end]
            post_bars = [b for b in bars if _bar_date(b) > obs_end]
            current_price = bars[-1]["close"]

            # Still in observation window
            if not post_bars:
                two_week_high = max(b["high"] for b in obs_bars) if obs_bars else None
                pct_away = (
                    round((two_week_high - current_price) / two_week_high * 100, 2)
                    if two_week_high else None
                )
                results.append({
                    "symbol": sym, "company": name,
                    "listing_date": listing_date.isoformat(),
                    "days_since_listing": days_since,
                    "obs_window_end": obs_end.isoformat(),
                    "two_week_high": round(two_week_high, 2) if two_week_high else None,
                    "two_week_low": round(min(b["low"] for b in obs_bars), 2) if obs_bars else None,
                    "signal_date": None,
                    "entry_price": None, "sl_price": None,
                    "t1": None, "t2": None, "t3": None,
                    "t1_hit": False, "t2_hit": False, "t3_hit": False,
                    "current_price": round(current_price, 2),
                    "pct_to_breakout": pct_away,
                    "entry_status": "-", "status": "WATCHING",
                    "bars_available": len(bars), "market_cap_cr": mc_cr,
                })
                continue

            # Obs window complete
            two_week_high = max(b["high"] for b in obs_bars)
            two_week_low  = min(b["low"]  for b in obs_bars)
            R = two_week_high - two_week_low

            pct_away = round(
                (two_week_high - current_price) / two_week_high * 100, 2
            ) if two_week_high else 0.0

            # Find first signal bar where CLOSE crosses above 2WH (Pine Script logic)
            # SL tracks running low from listing to that bar — not frozen at obs window
            first_signal_idx = None
            running_low = two_week_low   # starts at obs window low, updates daily
            running_low_at_signal = two_week_low
            for i, b in enumerate(post_bars):
                running_low = min(running_low, b["low"])
                if b["close"] > two_week_high:
                    first_signal_idx = i
                    running_low_at_signal = running_low
                    break

            if first_signal_idx is None:
                status = "NEAR" if abs(pct_away) <= 3.0 else "WATCHING"
                entry_price = round(two_week_high, 2)
                sl_price    = round(running_low, 2)   # running low up to today
                t1 = round(entry_price + R, 2) if R > 0 else None
                t2 = round(entry_price + 2 * R, 2) if R > 0 else None
                t3 = round(entry_price + 3 * R, 2) if R > 0 else None
                results.append({
                    "symbol": sym, "company": name,
                    "listing_date": listing_date.isoformat(),
                    "days_since_listing": days_since,
                    "obs_window_end": obs_end.isoformat(),
                    "two_week_high": round(two_week_high, 2),
                    "two_week_low": round(two_week_low, 2),
                    "signal_date": None,
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "t1": t1, "t2": t2, "t3": t3,
                    "t1_hit": False, "t2_hit": False, "t3_hit": False,
                    "current_price": round(current_price, 2),
                    "pct_to_breakout": pct_away,
                    "entry_status": f"⏳ Limit @ ₹{entry_price}",
                    "status": status,
                    "bars_available": len(bars), "market_cap_cr": mc_cr,
                })
                continue

            # Signal exists
            signal_bar = post_bars[first_signal_idx]
            signal_date = signal_bar["date"]
            bars_since_signal = len(post_bars) - 1 - first_signal_idx
            status = "FRESH" if bars_since_signal <= 5 else "PAST"

            entry_price = round(two_week_high, 2)
            sl_price    = round(running_low_at_signal, 2)   # locked at signal day
            R           = entry_price - sl_price             # recompute from actual SL, not obs window

            if R <= 0:
                entry_status = "⚠️ Invalid R"
                t1 = t2 = t3 = None
                t1_hit = t2_hit = t3_hit = False
            else:
                t1 = round(entry_price + R, 2)
                t2 = round(entry_price + 2 * R, 2)
                t3 = round(entry_price + 3 * R, 2)

                # Check post-entry bars for target/SL hits
                post_entry = post_bars[first_signal_idx + 1:]
                t1_hit = any(b["high"] >= t1 for b in post_entry)
                t2_hit = t1_hit and any(b["high"] >= t2 for b in post_entry)
                t3_hit = t2_hit and any(b["high"] >= t3 for b in post_entry)

                effective_sl = entry_price if t1_hit else sl_price
                stopped_out = any(b["low"] <= effective_sl for b in post_entry)

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
                "symbol": sym, "company": name,
                "listing_date": listing_date.isoformat(),
                "days_since_listing": days_since,
                "obs_window_end": obs_end.isoformat(),
                "two_week_high": round(two_week_high, 2),
                "two_week_low": round(two_week_low, 2),
                "signal_date": signal_date,
                "entry_price": entry_price,
                "sl_price": sl_price,
                "t1": t1, "t2": t2, "t3": t3,
                "t1_hit": t1_hit, "t2_hit": t2_hit, "t3_hit": t3_hit,
                "current_price": round(current_price, 2),
                "pct_to_breakout": pct_away,
                "entry_status": entry_status,
                "status": status,
                "bars_available": len(bars), "market_cap_cr": mc_cr,
            })

        order = {"FRESH": 0, "NEAR": 1, "WATCHING": 2, "PAST": 3, "NO_DATA": 4}
        results.sort(key=lambda x: order.get(x["status"], 5))
        return results

    @staticmethod
    def fetch_market_caps(symbols: list[str]) -> dict[str, Optional[float]]:
        """Fetch market caps (₹ Crores) for NSE symbols via yfinance."""
        result: dict[str, Optional[float]] = {}
        try:
            import yfinance as yf
        except ImportError:
            return {s: None for s in symbols}

        for sym in symbols:
            try:
                fi = yf.Ticker(f"{sym}.NS").fast_info
                mc = getattr(fi, "market_cap", None)
                result[sym] = round(mc / 1e7, 0) if mc else None
            except Exception:
                result[sym] = None

        return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bar_date(bar: dict) -> date:
    """Extract date from a bar dict (date may be str or date object)."""
    d = bar.get("date")
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return date.fromisoformat(d[:10])
    return date.min


def _no_data_row(sym, name, listing_date, days_since, mc_cr) -> dict:
    return {
        "symbol": sym, "company": name,
        "listing_date": listing_date.isoformat(),
        "days_since_listing": days_since,
        "obs_window_end": _obs_window_end(listing_date).isoformat(),
        "two_week_high": None, "two_week_low": None,
        "signal_date": None,
        "entry_price": None, "sl_price": None,
        "t1": None, "t2": None, "t3": None,
        "t1_hit": False, "t2_hit": False, "t3_hit": False,
        "current_price": None, "pct_to_breakout": None,
        "entry_status": "-", "status": "NO_DATA",
        "bars_available": 0, "market_cap_cr": mc_cr,
    }
