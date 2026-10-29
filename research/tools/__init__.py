"""
Tools package.
"""

from cryptobot.research.tools.registry import (
    ToolRegistry,
    ToolSpec,
    WriteClass,
    tool_registry,
    tool,
    ToolSpec,
)
from cryptobot.research.tools.market_tools import (
    fetch_candles,
    fetch_orderbook,
    fetch_ticker,
    fetch_funding_rate,
    fetch_recent_trades,
    fetch_market_data,
    screen_symbols,
    calculate_indicators,
    detect_patterns,
    calculate_correlation,
    register_market_tools,
)
from cryptobot.research.models.kronos_wrapper import kronos_forecast

__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "WriteClass",
    "tool_registry",
    "tool",
    "fetch_candles",
    "fetch_orderbook",
    "fetch_ticker",
    "fetch_funding_rate",
    "fetch_recent_trades",
    "fetch_market_data",
    "screen_symbols",
    "calculate_indicators",
    "detect_patterns",
    "calculate_correlation",
    "register_market_tools",
    "kronos_forecast",
]