from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import floor
from statistics import mean
from typing import Literal, Optional


@dataclass
class Trade:
    symbol: str
    name: str
    listing_date: date
    entry_date: Optional[date] = None
    entry_price: Optional[float] = None
    sl_price: Optional[float] = None
    t1: Optional[float] = None
    t2: Optional[float] = None
    t3: Optional[float] = None
    position_size: int = 0
    exit_date: Optional[date] = None
    exit_reason: Optional[Literal["SL", "T1_PARTIAL", "T2_PARTIAL", "T3", "MAX_HOLD", "NO_SIGNAL", "SKIP"]] = None
    r_multiple: Optional[float] = None
    pnl: Optional[float] = None
    t1_hit: bool = False
    t2_hit: bool = False
    t3_hit: bool = False
    sl_moved_to_breakeven: bool = False


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def simulate_trade(
    symbol: str,
    name: str,
    listing_date: date,
    bars: list[dict],
    capital: float,
    risk_pct: float,
) -> Trade:
    base = Trade(symbol=symbol, name=name, listing_date=listing_date)

    if len(bars) < 11:
        base.exit_reason = "NO_SIGNAL"
        return base

    obs_bars = bars[:10]
    two_week_high = max(b["close"] for b in obs_bars)

    signal_bar = None
    signal_idx = None
    for i in range(10, len(bars)):
        if bars[i]["close"] > two_week_high:
            signal_bar = bars[i]
            signal_idx = i
            break

    if signal_bar is None or signal_idx + 1 >= len(bars):
        base.exit_reason = "NO_SIGNAL"
        return base

    entry_bar = bars[signal_idx + 1]
    entry_price = entry_bar["open"]
    entry_date_raw = entry_bar["date"]
    entry_date = (
        date.fromisoformat(entry_date_raw)
        if isinstance(entry_date_raw, str)
        else entry_date_raw
    )

    sl_price = min(b["low"] for b in bars[: signal_idx + 1])
    R = entry_price - sl_price

    if R <= 0:
        base.exit_reason = "SKIP"
        return base

    position_size = floor((capital * risk_pct) / R)
    if position_size <= 0:
        base.exit_reason = "SKIP"
        return base

    t1 = entry_price + R
    t2 = entry_price + 2 * R
    t3 = entry_price + 3 * R

    trade = Trade(
        symbol=symbol,
        name=name,
        listing_date=listing_date,
        entry_date=entry_date,
        entry_price=entry_price,
        sl_price=sl_price,
        t1=t1,
        t2=t2,
        t3=t3,
        position_size=position_size,
    )

    current_sl = sl_price
    remaining = position_size
    t1_units = floor(position_size / 3)
    t2_units = floor(position_size / 3)
    total_pnl = 0.0

    for bar_idx, bar in enumerate(bars[signal_idx + 2 :], start=0):
        bar_date_raw = bar["date"]
        bar_date = (
            date.fromisoformat(bar_date_raw)
            if isinstance(bar_date_raw, str)
            else bar_date_raw
        )

        # Max hold: 60 bars after entry
        if bar_idx >= 60:
            total_pnl += remaining * (bar["close"] - entry_price)
            trade.exit_date = bar_date
            trade.exit_reason = "MAX_HOLD"
            remaining = 0
            break

        # Stop-loss check (worst case for the day)
        if bar["low"] <= current_sl:
            total_pnl += remaining * (current_sl - entry_price)
            trade.exit_date = bar_date
            trade.exit_reason = "SL"
            remaining = 0
            break

        # T1 check
        if not trade.t1_hit and bar["high"] >= t1:
            total_pnl += t1_units * (t1 - entry_price)
            remaining -= t1_units
            trade.t1_hit = True
            trade.sl_moved_to_breakeven = True
            current_sl = entry_price  # trail SL to breakeven

        # T2 check
        if trade.t1_hit and not trade.t2_hit and bar["high"] >= t2:
            total_pnl += t2_units * (t2 - entry_price)
            remaining -= t2_units
            trade.t2_hit = True

        # T3 check — use remaining units to capture rounding remainder
        if trade.t1_hit and trade.t2_hit and not trade.t3_hit and bar["high"] >= t3:
            total_pnl += remaining * (t3 - entry_price)
            remaining = 0
            trade.t3_hit = True
            trade.exit_date = bar_date
            trade.exit_reason = "T3"
            break

    else:
        # Loop exhausted without a full exit
        if remaining > 0:
            last_bar = bars[-1]
            last_date_raw = last_bar["date"]
            last_date = (
                date.fromisoformat(last_date_raw)
                if isinstance(last_date_raw, str)
                else last_date_raw
            )
            total_pnl += remaining * (last_bar["close"] - entry_price)
            trade.exit_date = last_date
            trade.exit_reason = "MAX_HOLD"

    trade.pnl = total_pnl
    trade.r_multiple = total_pnl / (position_size * R) if R > 0 and position_size > 0 else 0.0
    return trade


def run_backtest(
    ipo_list: list[dict],
    ohlc_data: dict[str, list[dict]],
    capital: float,
    risk_pct: float,
) -> BacktestResult:
    result = BacktestResult()

    for ipo in ipo_list:
        sym = ipo["nse_symbol"]
        name = ipo["name"]
        listing_date = ipo["listing_date"]

        if not sym:
            result.skipped.append({"symbol": name, "reason": "No NSE symbol"})
            continue

        bars = ohlc_data.get(sym, [])
        if not bars:
            result.skipped.append({"symbol": sym, "reason": "No historical data"})
            continue

        trade = simulate_trade(sym, name, listing_date, bars, capital, risk_pct)

        if trade.exit_reason == "SKIP":
            result.skipped.append({"symbol": sym, "reason": "Invalid R or position size = 0"})
        else:
            result.trades.append(trade)

    closed = [t for t in result.trades if t.exit_reason not in (None, "NO_SIGNAL")]
    result.equity_curve = compute_equity_curve(closed, capital)
    result.metrics = compute_metrics(result.trades, capital)
    return result


def compute_metrics(trades: list[Trade], capital: float) -> dict:
    closed = [t for t in trades if t.exit_reason not in (None, "NO_SIGNAL", "SKIP")]
    total = len(closed)
    if total == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_r_multiple": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
        }

    wins = [t for t in closed if (t.pnl or 0) > 0]
    win_rate = len(wins) / total
    avg_r = mean(t.r_multiple for t in closed if t.r_multiple is not None)
    total_pnl = sum(t.pnl for t in closed if t.pnl is not None)

    # Max drawdown from equity curve
    eq = capital
    peak = capital
    max_dd = 0.0
    for t in sorted(closed, key=lambda x: x.exit_date or date.min):
        eq += t.pnl or 0
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    metrics = {
        "total_trades": total,
        "no_signal_count": len([t for t in trades if t.exit_reason == "NO_SIGNAL"]),
        "win_rate": win_rate,
        "avg_r_multiple": avg_r,
        "total_pnl": total_pnl,
        "max_drawdown_pct": max_dd,
    }

    # CAGR: needs at least ~1 year span
    dated = [t for t in closed if t.entry_date and t.exit_date]
    if dated:
        all_dates = sorted(t.entry_date for t in dated)
        span_days = (max(t.exit_date for t in dated) - all_dates[0]).days
        if span_days >= 365:
            years = span_days / 365.25
            final_equity = capital + total_pnl
            if final_equity > 0 and capital > 0:
                metrics["cagr"] = (final_equity / capital) ** (1 / years) - 1

    return metrics


def compute_equity_curve(trades: list[Trade], capital: float) -> list[dict]:
    from collections import defaultdict

    pnl_by_date: dict[date, float] = defaultdict(float)
    for t in trades:
        if t.exit_date and t.pnl is not None:
            pnl_by_date[t.exit_date] += t.pnl

    sorted_dates = sorted(pnl_by_date.keys())
    equity = capital
    peak = capital
    curve = []
    for d in sorted_dates:
        equity += pnl_by_date[d]
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        curve.append({"date": d, "equity": equity, "drawdown_pct": dd})

    return curve
