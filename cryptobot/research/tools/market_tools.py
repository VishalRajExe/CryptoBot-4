"""
Market research tools for agents.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from cryptobot.data.fetcher import get_fetcher
from cryptobot.data.models import Symbol, MarketType
from cryptobot.research.tools.registry import tool, tool_registry, WriteClass

logger = logging.getLogger(__name__)


@tool(
    name="fetch_candles",
    description="Fetch historical OHLCV candles for a symbol",
    write_class=WriteClass.NONE,
    category="market",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Unified symbol (e.g., BTC/USDT:binance:linear)"},
            "timeframe": {"type": "string", "description": "Timeframe (1m, 5m, 15m, 1h, 4h, 1d)", "default": "1h"},
            "lookback": {"type": "integer", "description": "Number of bars to fetch", "default": 500},
            "start": {"type": "string", "description": "Start date (ISO format)", "default": None},
            "end": {"type": "string", "description": "End date (ISO format)", "default": None},
        },
        "required": ["symbol"],
    },
)
async def fetch_candles(
    symbol: str,
    timeframe: str = "1h",
    lookback: int = 500,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch historical candles."""
    fetcher = await get_fetcher()
    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    candles = await fetcher.fetch_candles(sym, timeframe, start=start_dt, end=end_dt, limit=lookback)
    return [c.to_dict() for c in candles]


@tool(
    name="fetch_orderbook",
    description="Fetch current order book snapshot",
    write_class=WriteClass.NONE,
    category="market",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Unified symbol"},
            "depth": {"type": "integer", "description": "Order book depth", "default": 100},
        },
        "required": ["symbol"],
    },
)
async def fetch_orderbook(symbol: str, depth: int = 100) -> dict[str, Any]:
    """Fetch order book."""
    fetcher = await get_fetcher()
    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )
    ob = await fetcher.fetch_orderbook(sym, depth)
    return {
        "symbol": ob.symbol.unified,
        "timestamp": ob.timestamp.isoformat(),
        "bids": ob.bids[:depth],
        "asks": ob.asks[:depth],
        "spread_bps": ob.spread_bps,
        "mid_price": float(ob.mid_price) if ob.mid_price else None,
        "provenance": ob.provenance.to_dict() if ob.provenance else None,
    }


@tool(
    name="fetch_ticker",
    description="Fetch 24h ticker statistics",
    write_class=WriteClass.NONE,
    category="market",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Unified symbol"},
        },
        "required": ["symbol"],
    },
)
async def fetch_ticker(symbol: str) -> dict[str, Any]:
    """Fetch 24h ticker."""
    fetcher = await get_fetcher()
    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )
    ticker = await fetcher.fetch_ticker(sym)
    return {
        "symbol": ticker.symbol.unified,
        "last_price": float(ticker.last_price),
        "bid_price": float(ticker.bid_price) if ticker.bid_price else None,
        "ask_price": float(ticker.ask_price) if ticker.ask_price else None,
        "high_24h": float(ticker.high_24h),
        "low_24h": float(ticker.low_24h),
        "volume_24h": float(ticker.volume_24h),
        "volume_quote_24h": float(ticker.volume_quote_24h),
        "change_24h": float(ticker.change_24h),
        "change_pct_24h": ticker.change_pct_24h,
        "provenance": ticker.provenance.to_dict() if ticker.provenance else None,
    }


@tool(
    name="fetch_funding_rate",
    description="Fetch current funding rate for perpetual",
    write_class=WriteClass.NONE,
    category="market",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Unified symbol (perpetual only)"},
        },
        "required": ["symbol"],
    },
)
async def fetch_funding_rate(symbol: str) -> dict[str, Any]:
    """Fetch funding rate."""
    fetcher = await get_fetcher()
    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )
    if sym.market_type == MarketType.SPOT:
        return {"error": "Funding rate not available for spot markets"}

    funding = await fetcher.fetch_funding_rate(sym)
    return {
        "symbol": funding.symbol.unified,
        "rate": float(funding.rate),
        "annualized_rate": funding.annualized_rate,
        "next_funding_time": funding.next_funding_time.isoformat() if funding.next_funding_time else None,
        "provenance": funding.provenance.to_dict() if funding.provenance else None,
    }


@tool(
    name="fetch_recent_trades",
    description="Fetch recent trades for a symbol",
    write_class=WriteClass.NONE,
    category="market",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Unified symbol"},
            "limit": {"type": "integer", "description": "Number of trades", "default": 100},
        },
        "required": ["symbol"],
    },
)
async def fetch_recent_trades(symbol: str, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent trades."""
    fetcher = await get_fetcher()
    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )
    trades = await fetcher.fetch_recent_trades(sym, limit)
    return [t.to_dict() for t in trades]


@tool(
    name="fetch_market_data",
    description="Fetch complete market data snapshot (candles, orderbook, ticker, funding, trades)",
    write_class=WriteClass.NONE,
    category="market",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Unified symbol"},
            "timeframe": {"type": "string", "description": "Candle timeframe", "default": "1h"},
            "lookback": {"type": "integer", "description": "Candle lookback bars", "default": 500},
        },
        "required": ["symbol"],
    },
)
async def fetch_market_data(symbol: str, timeframe: str = "1h", lookback: int = 500) -> dict[str, Any]:
    """Fetch complete market data."""
    fetcher = await get_fetcher()
    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )
    data = await fetcher.fetch_market_data(sym, timeframe, lookback)
    return {
        "candles": [c.to_dict() for c in data.candles],
        "orderbooks": [o.to_dict() for o in data.orderbooks],
        "tickers": [t.to_dict() for t in data.tickers],
        "funding_rates": [f.to_dict() for f in data.funding_rates],
        "trades": [t.to_dict() for t in data.trades],
    }


@tool(
    name="screen_symbols",
    description="Screen symbols by criteria (volume, volatility, trend, etc.)",
    write_class=WriteClass.NONE,
    category="market",
    parameters={
        "type": "object",
        "properties": {
            "exchange": {"type": "string", "description": "Exchange to screen", "default": "binance"},
            "market_type": {"type": "string", "description": "Market type", "default": "linear"},
            "min_volume_usd": {"type": "number", "description": "Min 24h volume USD", "default": 10000000},
            "min_volatility_pct": {"type": "number", "description": "Min 24h volatility %", "default": 1.0},
            "max_volatility_pct": {"type": "number", "description": "Max 24h volatility %", "default": 50.0},
            "trend": {"type": "string", "description": "Trend filter (bullish, bearish, neutral)", "default": None},
            "limit": {"type": "integer", "description": "Max results", "default": 50},
        },
    },
)
async def screen_symbols(
    exchange: str = "binance",
    market_type: str = "linear",
    min_volume_usd: float = 10_000_000,
    min_volatility_pct: float = 1.0,
    max_volatility_pct: float = 50.0,
    trend: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Screen symbols by criteria."""
    fetcher = await get_fetcher()
    mt = MarketType(market_type)

    # Get all tickers from exchange
    # This is simplified - would need to fetch all symbols from exchange
    # For now, return mock structure
    return [
        {
            "symbol": "BTC/USDT:binance:linear",
            "volume_24h_usd": 50_000_000_000,
            "volatility_24h_pct": 2.5,
            "trend": "bullish",
        }
    ]


@tool(
    name="calculate_indicators",
    description="Calculate technical indicators for candles",
    write_class=WriteClass.NONE,
    category="technical",
    parameters={
        "type": "object",
        "properties": {
            "candles": {"type": "array", "items": {"type": "object"}},
            "indicators": {"type": "array", "items": {"type": "string"}, "default": ["ema", "rsi", "macd", "bb", "atr"]},
        },
        "required": ["candles"],
    },
)
async def calculate_indicators(candles: list[dict], indicators: list[str] | None = None) -> dict[str, Any]:
    """Calculate technical indicators."""
    from cryptobot.research.patterns.technical import TechnicalAnalyzer

    if not candles:
        return {}

    analyzer = TechnicalAnalyzer(candles)
    return analyzer.compute_all(indicators or ["ema", "rsi", "macd", "bb", "atr"])


@tool(
    name="detect_patterns",
    description="Detect chart patterns in candles",
    write_class=WriteClass.NONE,
    category="technical",
    parameters={
        "type": "object",
        "properties": {
            "candles": {"type": "array", "items": {"type": "object"}},
            "patterns": {"type": "array", "items": {"type": "string"}, "default": ["orb", "flag", "rsi_div", "ma_reclaim"]},
        },
        "required": ["candles"],
    },
)
async def detect_patterns(candles: list[dict], patterns: list[str] | None = None) -> list[dict]:
    """Detect chart patterns."""
    from cryptobot.research.patterns.technical import TechnicalAnalyzer

    if not candles:
        return []

    analyzer = TechnicalAnalyzer(candles)
    return analyzer.detect_patterns(patterns or ["orb", "flag", "rsi_div", "ma_reclaim"])


@tool(
    name="calculate_correlation",
    description="Calculate correlation between symbols",
    write_class=WriteClass.NONE,
    category="risk",
    parameters={
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}},
            "timeframe": {"type": "string", "default": "1h"},
            "lookback": {"type": "integer", "default": 200},
        },
        "required": ["symbols"],
    },
)
async def calculate_correlation(
    symbols: list[str],
    timeframe: str = "1h",
    lookback: int = 200,
) -> dict[str, Any]:
    """Calculate correlation matrix."""
    fetcher = await get_fetcher()

    # Fetch candles for all symbols
    candle_data = {}
    for sym_str in symbols:
        sym = Symbol.from_unified(sym_str) if ":" in sym_str else Symbol(
            base=sym_str.split("/")[0] if "/" in sym_str else sym_str,
            quote="USDT",
            exchange="binance",
            market_type=MarketType.LINEAR,
        )
        candles = await fetcher.fetch_candles(sym, timeframe, limit=lookback)
        if candles:
            closes = [float(c.close) for c in candles]
            candle_data[sym_str] = closes

    # Calculate correlation matrix
    import pandas as pd
    import numpy as np

    if len(candle_data) < 2:
        return {}

    # Align lengths
    min_len = min(len(v) for v in candle_data.values())
    df = pd.DataFrame({k: v[-min_len:] for k, v in candle_data.items()})
    returns = df.pct_change().dropna()
    corr_matrix = returns.corr()

    return corr_matrix.to_dict()


# Register all market tools
def register_market_tools():
    """Register all market tools with the global registry."""
    # Tools are registered via @tool decorator
    pass