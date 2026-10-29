"""
News Analyst - Crypto news, macro events, regulatory updates.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from cryptobot.research.analysts.base import BaseAnalyst, create_analyst_result
from cryptobot.research.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class NewsAnalyst(BaseAnalyst):
    """News analyst for crypto news and events."""

    def __init__(self, tool_registry: ToolRegistry, config: dict[str, Any] | None = None):
        super().__init__(tool_registry, config)
        self.news_sources = config.get("sources", [
            "coindesk", "theblock", "cointelegraph", "decrypt", "twitter",
        ])
        self.lookback_hours = config.get("lookback_hours", 24)
        self.min_relevance = config.get("min_relevance", 0.5)

    async def analyze(
        self,
        symbols: list[str],
        trade_date: str,
        portfolio_context: dict[str, Any] | None = None,
        memory_context: str | None = None,
    ) -> dict[str, Any]:
        """Analyze news for symbols."""
        results = {}

        # Fetch news for all symbols in parallel
        tasks = [self._analyze_symbol_news(symbol, trade_date) for symbol in symbols]
        symbol_results = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(symbols, symbol_results):
            if isinstance(result, Exception):
                logger.error(f"News analysis error for {symbol}: {result}")
                results[symbol] = create_analyst_result(
                    symbol=symbol,
                    findings={"error": str(result)},
                    confidence=0.0,
                )
            else:
                results[symbol] = result

        return {
            "analyst": "news",
            "date": trade_date,
            "symbols": results,
            "summary": self._generate_summary(results),
            "macro_events": await self._fetch_macro_events(trade_date),
        }

    async def _analyze_symbol_news(self, symbol: str, trade_date: str) -> dict[str, Any]:
        """Analyze news for a single symbol."""
        # Fetch from multiple sources
        articles = await self._fetch_crypto_news(symbol, trade_date)

        if not articles:
            return create_analyst_result(
                symbol=symbol,
                findings={"message": "No relevant news found"},
                confidence=0.3,
            )

        # Filter and score
        relevant = self._filter_relevant(articles, symbol)

        # Categorize
        categories = self._categorize_news(relevant)

        # Generate signals
        signals = self._generate_signals(categories, relevant)

        # Sentiment
        sentiment = self._calculate_sentiment(relevant)

        return create_analyst_result(
            symbol=symbol,
            findings={
                "total_articles": len(articles),
                "relevant_articles": len(relevant),
                "categories": categories,
                "sentiment": sentiment,
                "top_headlines": [a["title"] for a in relevant[:5]],
            },
            confidence=min(0.5 + len(relevant) * 0.05, 0.85),
            signals=signals,
            risks=self._identify_risks(categories),
            data_sources=self.news_sources,
        )

    async def _fetch_crypto_news(self, symbol: str, trade_date: str) -> list[dict[str, Any]]:
        """Fetch news from multiple sources."""
        articles = []
        base_symbol = symbol.split("/")[0].split(":")[0].upper()

        # CoinDesk API (would need API key)
        # The Block API
        # CryptoPanic API
        # Twitter/X API

        # For now, return mock structure - replace with real API calls
        # This is where you'd integrate with actual news APIs
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Example: CryptoPanic
                # resp = await client.get("https://cryptopanic.com/api/v1/posts/", params={...})
                pass
        except Exception as e:
            logger.debug(f"News fetch error: {e}")

        # Return empty for now - implement with real API keys
        return []

    def _filter_relevant(self, articles: list[dict], symbol: str) -> list[dict]:
        """Filter articles by relevance to symbol."""
        base = symbol.split("/")[0].split(":")[0].upper()
        relevant = []
        for article in articles:
            title = article.get("title", "").lower()
            content = article.get("content", "").lower()
            if base.lower() in title or base.lower() in content:
                article["relevance"] = 1.0
            elif any(term in title for term in ["btc", "eth", "crypto", "bitcoin", "ethereum"]):
                article["relevance"] = 0.5
            else:
                article["relevance"] = 0.1
            if article["relevance"] >= self.min_relevance:
                relevant.append(article)
        return sorted(relevant, key=lambda x: x["relevance"], reverse=True)

    def _categorize_news(self, articles: list[dict]) -> dict[str, int]:
        """Categorize news articles."""
        categories = {
            "regulatory": 0,
            "adoption": 0,
            "technical": 0,
            "market": 0,
            "hack": 0,
            "partnership": 0,
            "macro": 0,
        }
        keywords = {
            "regulatory": ["sec", "regulation", "law", "compliance", "etf", "approval"],
            "adoption": ["adoption", "integration", "partnership", "launch", "mainnet"],
            "technical": ["upgrade", "fork", "hard fork", "testnet", "mainnet", "eip"],
            "market": ["price", "rally", "crash", "volatility", "volume", "liquidation"],
            "hack": ["hack", "exploit", "vulnerability", "stolen", "drain"],
            "partnership": ["partners", "collaboration", "integration", "alliance"],
            "macro": ["fed", "interest rate", "inflation", "cpi", "macro", "dollar"],
        }
        for article in articles:
            text = (article.get("title", "") + " " + article.get("content", "")).lower()
            for cat, kws in keywords.items():
                if any(kw in text for kw in kws):
                    categories[cat] += 1
        return categories

    def _generate_signals(self, categories: dict, articles: list) -> list[dict]:
        """Generate signals from news categories."""
        signals = []

        # Positive signals
        if categories.get("adoption", 0) > 2:
            signals.append({
                "type": "news_positive",
                "direction": "long",
                "strength": min(categories["adoption"] * 0.1, 0.5),
                "reason": f"High adoption news ({categories['adoption']} articles)",
            })

        if categories.get("partnership", 0) > 1:
            signals.append({
                "type": "news_positive",
                "direction": "long",
                "strength": 0.3,
                "reason": "Partnership announcements",
            })

        # Negative signals
        if categories.get("hack", 0) > 0:
            signals.append({
                "type": "news_negative",
                "direction": "short",
                "strength": min(categories["hack"] * 0.2, 0.6),
                "reason": "Security incident reported",
            })

        if categories.get("regulatory", 0) > 2:
            signals.append({
                "type": "news_negative",
                "direction": "short",
                "strength": 0.4,
                "reason": "Regulatory uncertainty",
            })

        return signals

    def _calculate_sentiment(self, articles: list) -> dict[str, float]:
        """Calculate sentiment from articles."""
        # Simplified - would use NLP/sentiment model
        positive_kws = ["bullish", "surge", "rally", "gain", "adoption", "launch", "partnership", "approval"]
        negative_kws = ["bearish", "crash", "drop", "loss", "hack", "exploit", "ban", "regulation", "delay"]

        pos = 0
        neg = 0
        for article in articles:
            text = (article.get("title", "") + " " + article.get("content", "")).lower()
            pos += sum(1 for kw in positive_kws if kw in text)
            neg += sum(1 for kw in negative_kws if kw in text)

        total = pos + neg
        if total == 0:
            return {"positive": 0.5, "negative": 0.5, "neutral": 1.0}
        return {
            "positive": pos / total,
            "negative": neg / total,
            "neutral": 1 - (pos + neg) / max(len(articles), 1),
        }

    def _identify_risks(self, categories: dict) -> list[str]:
        risks = []
        if categories.get("hack", 0) > 0:
            risks.append("Security incident risk")
        if categories.get("regulatory", 0) > 3:
            risks.append("High regulatory uncertainty")
        return risks

    async def _fetch_macro_events(self, trade_date: str) -> list[dict]:
        """Fetch macro economic events."""
        # FRED, economic calendar APIs
        return []

    def _generate_summary(self, results: dict) -> str:
        total_news = sum(r.get("findings", {}).get("relevant_articles", 0) for r in results.values())
        return f"News Analyst: {total_news} relevant articles across {len(results)} symbols"