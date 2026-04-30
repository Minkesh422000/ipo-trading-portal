"""
strategies/__init__.py — Strategy registry.

To add a new strategy:
1. Create a new file in this folder (e.g. momentum.py) implementing BaseStrategy
2. Import it here and add to STRATEGY_REGISTRY
"""
from strategies.ipo_breakout import IPOBreakoutStrategy

STRATEGY_REGISTRY = {
    "IPO_BREAKOUT": IPOBreakoutStrategy,
    # "MOMENTUM": MomentumStrategy,  # add later
}

__all__ = ["STRATEGY_REGISTRY", "IPOBreakoutStrategy"]
