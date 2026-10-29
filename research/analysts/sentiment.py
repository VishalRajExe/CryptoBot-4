"""
Sentiment Analyst - Fear & Greed, funding rates, open interest, social sentiment.
"""

from __future__ import annotations

import logging
from typing import Any

from cryptobot.research.analysts.base import BaseAnalyst, create_analyst_result
from cryptobot.data.fetcher import get_fetcher
from cryptobot.data.models import Symbol, MarketType

logger = logging.getLogger(__name__)


class SentimentAnalyst(BaseAnalyst):
    """Sentiment analyst for market sentiment indicators."""

    def __init__(self, tool_registry, config: dict[str, Any] | None = None):
        super().__init__(tool_registry, config)
        self.fetcher = None
        self.social_sources = config.get("social_sources", ["twitter", "reddit", "telegram", "discord"])

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
        """Analyze sentiment for symbols."""
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

                # Fetch market data for sentiment indicators
                market_data = await fetcher.fetch_market_data(symbol, lookback=200)

                # Analyze sentiment components
                funding_sentiment = self._analyze_funding_sentiment(market_data)
                oi_sentiment = self._analyze_oi_sentiment(market_data)
                liquidation_sentiment = self._analyze_liquidation_sentiment(market_data)
                social_sentiment = await self._fetch_social_sentiment(symbol.base)
                fear_greed = await self._fetch_fear_greed()

                # Generate signals
                signals = self._generate_signals(
                    funding_sentiment, oi_sentiment, liquidation_sentiment,
                    social_sentiment, fear_greed
                )

                results[symbol_str] = create_analyst_result(
                    symbol=symbol_str,
                    findings={
                        "funding_sentiment": funding_sentiment,
                        "oi_sentiment": oi_sentiment,
                        "liquidation_sentiment": liquidation_sentiment,
                        "social_sentiment": social_sentiment,
                        "fear_greed": fear_greed,
                    },
                    confidence=0.55,
                    signals=signals,
                    risks=self._identify_risks(funding_sentiment, oi_sentiment, fear_greed),
                    data_sources=["exchange_funding", "exchange_oi", "liquidation_data", "social_apis", "fear_greed_index"],
                )

            except Exception as e:
                logger.error(f"Sentiment analysis error for {symbol_str}: {e}")
                results[symbol_str] = create_analyst_result(
                    symbol=symbol_str,
                    findings={"error": str(e)},
                    confidence=0.0,
                )

        return {
            "analyst": "sentiment",
            "date": trade_date,
            "symbols": results,
            "summary": self._generate_summary(results),
        }

    def _analyze_funding_sentiment(self, market_data) -> dict[str, Any]:
        """Analyze funding rate sentiment."""
        if not market_data.funding_rates:
            return {"signal": "neutral", "strength": 0.0}

        latest = market_data.funding_rates[0]
        rate = float(latest.rate)

        if rate > 0.0005:  # 0.05% = very bullish (longs pay shorts)
            return {"signal": "bearish", "strength": min(rate * 1000, 1.0), "rate": rate}
        elif rate < -0.0005:  # Negative = shorts pay longs
            return {"signal": "bullish", "strength": min(abs(rate) * 1000, 1.0), "rate": rate}
        return {"signal": "neutral", "strength": 0.0, "rate": rate}

    def _analyze_oi_sentiment(self, market_data) -> dict[str, Any]:
        """Analyze open interest sentiment."""
        # Would need OI data from exchange
        return {"signal": "neutral", "strength": 0.0, "oi_change_24h": 0}

    def _analyze_liquidation_sentiment(self, market_data) -> dict[str, Any]:
        """Analyze liquidation data."""
        # Would need liquidation data
        return {"signal": "neutral", "strength": 0.0, "long_liqs": 0, "short_liqs": 0}

    async def _fetch_social_sentiment(self, symbol: str) -> dict[str, Any]:
        """Fetch social media sentiment."""
        # Twitter API, Reddit API, LunarCrush, etc.
        return {
            "twitter_sentiment": 0.5,
            "reddit_sentiment": 0.5,
            "mention_count": 0,
            "trending": False,
        }

    async def _fetch_fear_greed(self) -> dict[str, Any]:
        """Fetch Fear & Greed Index."""
        # Alternative.me API
        return {
            "value": 50,
            "classification": "Neutral",
            "timestamp": None,
        }

    def _generate_signals(
        self,
        funding: dict,
        oi: dict,
        liquidation: dict,
        social: dict,
        fear_greed: dict,
    ) -> list[dict]:
        signals = []

        # Funding rate signals
        if funding["signal"] == "bearish" and funding["strength"] > 0.5:
            signals.append({
                "type": "funding_extreme",
                "direction": "short",
                "strength": funding["strength"],
                "reason": f"Funding rate extremely positive ({funding['rate']:.4f}) - longs overextended",
            })
        elif funding["signal"] == "bullish" and funding["strength"] > 0.5:
            signals.append({
                "type": "funding_extreme",
                "direction": "long",
                "strength": funding["strength"],
                "reason": f"Funding rate negative ({funding['rate']:.4f}) - shorts overextended",
            })

        # Fear & Greed
        fg_value = fear_greed.get("value", 50)
        if fg_value <= 20:
            signals.append({
                "type": "fear_greed",
                "direction": "long",
                "strength": (20 - fg_value) / 20 * 0.5,
                "reason": f"Extreme fear ({fg_value}) - contrarian buy",
            })
        elif fg_value >= 80:
            signals.append({
                "type": "fear_greed",
                "direction": "short",
                "strength": (fg_value - 80) / 20 * 0.5,
                "reason": f"Extreme greed ({fg_value}) - contrarian sell",
            })

        return signals

    def _identify_risks(self, funding: dict, oi: dict, fear_greed: dict) -> list[str]:
        risks = []
        if funding["signal"] == "bearish" and funding["strength"] > 0.8:
            risks.append("Extreme positive funding - squeeze risk")
        if fear_greed.get("value", 50) > 80:
            risks.append("Extreme greed - correction risk")
        return risks

    def _generate_summary(self, results: dict) -> str:
        bullish = sum(1 for r in results.values() if any(s["direction"] == "long" for s in r.get("signals", [])))
        bearish = sum(1 for r in results.values() if any(s["direction"] == "short" for s in r.get("signals", [])))
        return f"Sentiment Analyst: {bullish} bullish, {bearish} bearish sentiment signals"