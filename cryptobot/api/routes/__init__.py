"""
API routes package.
"""

from cryptobot.api.routes import strategies, positions, orders, backtest, research, settings

__all__ = [
    "strategies",
    "positions",
    "orders",
    "backtest",
    "research",
    "settings",
]