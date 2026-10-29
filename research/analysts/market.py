"""
Market Analyst - Technical analysis, order flow, funding rates, basis.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from cryptobot.research.analysts.base import BaseAnalyst, create_analyst_result
from cryptobot.research.tools.registry import ToolRegistry
from cryptobot.data.fetcher import get_fetcher
from cryptobot.data.models import Symbol, MarketType

logger = logging.getLogger(__name__)


class MarketAnalyst(BaseAnalyst):
    """Market analyst for technical and microstructure analysis."""

    def __init__(self, tool_registry: ToolRegistry, config: dict[str, Any] | None = None):
        super().__init__(tool_registry, config)
        self.fetcher = None
        self.default_timeframes = config.get("timeframes", ["1m", "5m", "15m", "1h", "4h"])
        self.lookback_bars = config.get("lookback_bars", 500)

    async def _get_fetcher(self):
        if self.fetcher is None:
            self.fetcher = await get_fetcher()
        return self.fetcher

    async def analyze(
        self,
        symbols: list[str],
        trade_date: str,
        portfolio_context: dict[str, Any] | None = None,
        memory_context: str | None = None,
    ) -> dict[str, Any]:
        """Perform market analysis for symbols."""
        fetcher = await self._get_fetcher()
        results = {}

        for symbol_str in symbols:
            try:
                symbol = Symbol.from_unified(symbol_str) if ":" in symbol_str else Symbol(
                    base=symbol_str.split("/")[0] if "/" in symbol_str else symbol_str,
                    quote="USDT",
                    exchange="binance",
                    market_type=MarketType.LINEAR,
                )

                # Fetch multi-timeframe data
                market_data = await fetcher.fetch_market_data(
                    symbol,
                    timeframe=self.default_timeframes[0],
                    lookback=self.lookback_bars,
                )

                if not market_data.candles:
                    results[symbol_str] = create_analyst_result(
                        symbol=symbol_str,
                        findings={"error": "No candle data available"},
                        confidence=0.0,
                    )
                    continue

                # Analyze
                analysis = await self._analyze_symbol(symbol, market_data)
                results[symbol_str] = analysis

            except Exception as e:
                logger.error(f"Market analysis error for {symbol_str}: {e}")
                results[symbol_str] = create_analyst_result(
                    symbol=symbol_str,
                    findings={"error": str(e)},
                    confidence=0.0,
                )

        return {
            "analyst": "market",
            "date": trade_date,
            "symbols": results,
            "summary": self._generate_summary(results),
        }

    async def _analyze_symbol(self, symbol: Symbol, market_data) -> dict[str, Any]:
        """Analyze a single symbol's market data."""
        from cryptobot.research.patterns.technical import TechnicalAnalyzer

        analyzer = TechnicalAnalyzer(market_data.candles)

        # Technical indicators
        indicators = analyzer.compute_all()

        # Pattern recognition
        patterns = analyzer.detect_patterns()

        # Market microstructure
        microstructure = self._analyze_microstructure(market_data)

        # Funding & basis (for perpetuals)
        funding_basis = None
        if symbol.market_type != MarketType.SPOT and market_data.funding_rates:
            funding_basis = self._analyze_funding_basis(market_data.funding_rates, market_data.candles)

        # Generate signals
        signals = self._generate_signals(indicators, patterns, microstructure, funding_basis)

        # Overall confidence
        confidence = self._calculate_confidence(indicators, patterns, microstructure)

        return create_analyst_result(
            symbol=symbol.unified,
            findings={
                "indicators": indicators,
                "patterns": patterns,
                "microstructure": microstructure,
                "funding_basis": funding_basis,
            },
            confidence=confidence,
            signals=signals,
            risks=self._identify_risks(indicators, patterns, microstructure),
            data_sources=["binance", "bybit", "okx", "hyperliquid"],
        )

    def _analyze_microstructure(self, market_data) -> dict[str, Any]:
        """Analyze order book and trade flow."""
        if not market_data.orderbooks:
            return {}

        ob = market_data.orderbooks[0]
        return {
            "spread_bps": ob.spread_bps,
            "bid_ask_imbalance": self._calculate_imbalance(ob),
            "depth_ratio": self._calculate_depth_ratio(ob),
            "mid_price": float(ob.mid_price) if ob.mid_price else None,
        }

    def _calculate_imbalance(self, ob) -> float:
        """Calculate bid-ask imbalance."""
        bid_vol = sum(b[1] for b in ob.bids[:10])
        ask_vol = sum(a[1] for a in ob.asks[:10])
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total

    def _calculate_depth_ratio(self, ob) -> float:
        """Calculate depth ratio (bid depth / ask depth)."""
        bid_depth = sum(b[1] for b in ob.bids[:20])
        ask_depth = sum(a[1] for a in ob.asks[:20])
        if ask_depth == 0:
            return float('inf')
        return bid_depth / ask_depth

    def _analyze_funding_basis(self, funding_rates, candles) -> dict[str, Any]:
        """Analyze funding rates and basis."""
        if not funding_rates:
            return {}

        latest_funding = funding_rates[0]
        return {
            "current_rate": float(latest_funding.rate),
            "annualized_rate": latest_funding.annualized_rate,
            "next_funding": latest_funding.next_funding_time.isoformat() if latest_funding.next_funding_time else None,
            "basis_analysis": self._calculate_basis(candles, latest_funding),
        }

    def _calculate_basis(self, candles, funding) -> dict[str, Any]:
        """Calculate spot-futures basis."""
        # Simplified - would need spot price
        return {
            "funding_rate": float(funding.rate),
            "predicted_rate": float(funding.predicted_rate) if funding.predicted_rate else None,
        }

    def _generate_signals(
        self,
        indicators: dict,
        patterns: list,
        microstructure: dict,
        funding_basis: dict | None,
    ) -> list[dict[str, Any]]:
        """Generate trading signals from analysis."""
        signals = []

        # Trend signals
        if indicators.get("ema_trend") == "bullish":
            signals.append({
                "type": "trend_follow",
                "direction": "long",
                "strength": indicators.get("trend_strength", 0.5),
                "reason": "EMA alignment bullish",
            })
        elif indicators.get("ema_trend") == "bearish":
            signals.append({
                "type": "trend_follow",
                "direction": "short",
                "strength": indicators.get("trend_strength", 0.5),
                "reason": "EMA alignment bearish",
            })

        # Mean reversion
        if indicators.get("rsi") is not None:
            rsi = indicators["rsi"]
            if rsi < 30:
                signals.append({
                    "type": "mean_reversion",
                    "direction": "long",
                    "strength": (30 - rsi) / 30,
                    "reason": f"RSI oversold at {rsi:.1f}",
                })
            elif rsi > 70:
                signals.append({
                    "type": "mean_reversion",
                    "direction": "short",
                    "strength": (rsi - 70) / 30,
                    "reason": f"RSI overbought at {rsi:.1f}",
                })

        # Microstructure
        if microstructure.get("bid_ask_imbalance", 0) > 0.3:
            signals.append({
                "type": "microstructure",
                "direction": "long",
                "strength": min(microstructure["bid_ask_imbalance"], 0.8),
                "reason": "Strong bid pressure",
            })
        elif microstructure.get("bid_ask_imbalance", 0) < -0.3:
            signals.append({
                "type": "microstructure",
                "direction": "short",
                "strength": min(abs(microstructure["bid_ask_imbalance"]), 0.8),
                "reason": "Strong ask pressure",
            })

        return signals

    def _calculate_confidence(
        self,
        indicators: dict,
        patterns: list,
        microstructure: dict,
    ) -> float:
        """Calculate overall confidence."""
        confidence = 0.5  # Base

        # Trend alignment
        if indicators.get("ema_trend") in ("bullish", "bearish"):
            confidence += 0.15

        # RSI extremes
        rsi = indicators.get("rsi")
        if rsi and (rsi < 25 or rsi > 75):
            confidence += 0.1

        # Pattern confirmation
        if patterns:
            confidence += min(len(patterns) * 0.05, 0.15)

        # Microstructure
        if abs(microstructure.get("bid_ask_imbalance", 0)) > 0.2:
            confidence += 0.1

        return min(confidence, 0.95)

    def _identify_risks(
        self,
        indicators: dict,
        patterns: list,
        microstructure: dict,
    ) -> list[str]:
        """Identify risk factors."""
        risks = []

        if indicators.get("atr_percentile", 0) > 90:
            risks.append("Extremely high volatility")

        if microstructure.get("spread_bps", 0) > 50:
            risks.append("Wide spreads - low liquidity")

        if indicators.get("volume_trend") == "decreasing":
            risks.append("Declining volume")

        return risks

    def _generate_summary(self, results: dict) -> str:
        """Generate summary across all symbols."""
        bullish = sum(1 for r in results.values() if any(s["direction"] == "long" for s in r.get("signals", [])))
        bearish = sum(1 for r in results.values() if any(s["direction"] == "short" for s in r.get("signals", [])))
        return f"Market Analyst: {bullish} bullish, {bearish} bearish signals across {len(results)} symbols"