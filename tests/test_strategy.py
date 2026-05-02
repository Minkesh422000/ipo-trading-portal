"""
tests/test_strategy.py — Tests for strategies/ipo_breakout.py

Run with: python -m pytest tests/test_strategy.py -v
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ["DATABASE_MODE"] = "sqlite"


def _make_ohlc_bar(date_str: str, open_: float, high: float, low: float, close: float, vol: int = 100_000):
    return {"date": date_str, "open": open_, "high": high, "low": low, "close": close, "volume": vol}


def _make_ipo(symbol: str = "TESTCO", listing_date: str = None):
    if listing_date is None:
        listing_date = (date.today() - timedelta(days=20)).isoformat()
    return {
        "symbol": symbol,
        "company": "Test Company Ltd",
        "listing_date": listing_date,
        "issue_price": 100.0,
    }


# ── IPO Breakout Strategy ─────────────────────────────────────────────────────

class TestIPOBreakoutStrategy:

    def _make_strategy(self):
        from strategies.ipo_breakout import IPOBreakoutStrategy
        return IPOBreakoutStrategy()

    def test_no_signals_with_empty_data(self):
        strategy = self._make_strategy()
        signals = strategy.generate_signals(
            ipo_list=[], ohlc_data={}, params={},
            capital=1_000_000, risk_pct=0.01, existing_holdings=[],
        )
        assert signals == []

    def test_no_signals_when_already_holding(self):
        """Should skip symbols already in portfolio."""
        strategy = self._make_strategy()

        ipo = _make_ipo("HELDCO")
        # Build 14 bars then a breakout bar
        bars = []
        for i in range(14):
            bars.append(_make_ohlc_bar(
                (date.today() - timedelta(days=14 - i)).isoformat(),
                100, 105, 95, 102,
            ))
        # Breakout bar
        bars.append(_make_ohlc_bar(date.today().isoformat(), 103, 130, 103, 128))

        signals = strategy.generate_signals(
            ipo_list=[ipo],
            ohlc_data={"HELDCO": bars},
            params={},
            capital=1_000_000,
            risk_pct=0.01,
            existing_holdings=[{"symbol": "HELDCO"}],
        )
        assert signals == []

    def test_quantity_respects_risk_pct(self):
        """Quantity should be sized so risk = capital * risk_pct."""
        from strategies.ipo_breakout import IPOBreakoutStrategy
        strategy = IPOBreakoutStrategy()

        ipo = _make_ipo("RISKCO")
        bars = []
        for i in range(14):
            bars.append(_make_ohlc_bar(
                (date.today() - timedelta(days=14 - i)).isoformat(),
                100, 110, 90, 105,
            ))
        # Strong breakout: close well above 2-week high
        bars.append(_make_ohlc_bar(date.today().isoformat(), 106, 135, 106, 132))

        signals = strategy.generate_signals(
            ipo_list=[ipo],
            ohlc_data={"RISKCO": bars},
            params={},
            capital=1_000_000,
            risk_pct=0.01,
            existing_holdings=[],
        )

        if signals:
            sig = signals[0]
            risk_per_share = sig.entry_price - sig.sl_price
            actual_risk = risk_per_share * sig.quantity
            max_allowed_risk = 1_000_000 * 0.01
            assert actual_risk <= max_allowed_risk * 1.05  # within 5% tolerance


# ── Base Strategy ─────────────────────────────────────────────────────────────

def test_strategy_registry_contains_ipo_breakout():
    from strategies import STRATEGY_REGISTRY
    assert "IPO_BREAKOUT" in STRATEGY_REGISTRY


def test_signal_dataclass_fields():
    from strategies.base import Signal
    sig = Signal(
        symbol="TEST", company="Test Co", action="BUY",
        entry_price=100.0, sl_price=90.0, t1=110.0, t2=120.0, t3=130.0,
        quantity=100, strategy_id="TEST_STRAT", account_id="acc_test",
        reason="Test reason",
    )
    assert sig.symbol == "TEST"
    assert sig.action == "BUY"
    assert sig.quantity == 100
