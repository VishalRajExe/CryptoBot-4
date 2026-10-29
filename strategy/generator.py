"""
Strategy signal generator combining multiple signal sources.
Adapted from Vibe-Trading's SignalEngine and Kronos integration.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
import yaml

from cryptobot.research.tools import tool_registry
from cryptobot.research.patterns import TechnicalAnalyzer, compute_signals
from cryptobot.data.models import Symbol, MarketType
from cryptobot.data.fetcher import get_fetcher
from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    """Unified strategy signal."""

    symbol: str
    timestamp: datetime
    direction: str  # long, short, neutral
    strength: float  # 0-1
    signal_type: str
    source: str
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SignalEngine:
    """
    Signal engine that combines multiple signal sources.

    Sources:
    - Technical indicators (EMA, RSI, MACD, etc.)
    - Chart patterns (ORB, flags, RSI div, etc.)
    - Kronos forecasts
    - Funding/basis signals
    - Onchain signals
    - Sentiment signals
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.fetcher = None
        self.strategy_configs = self._load_strategy_configs()

    def _load_strategy_configs(self) -> dict[str, Any]:
        """Load strategy configurations from YAML."""
        config_path = settings.data_dir / "config" / "strategies.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}

    async def _get_fetcher(self):
        if self.fetcher is None:
            self.fetcher = await get_fetcher()
        return self.fetcher

    async def generate(
        self,
        symbols: list[str],
        timeframe: str = "1h",
        lookback: int = 500,
        enabled_strategies: list[str] | None = None,
    ) -> dict[str, list[StrategySignal]]:
        """
        Generate signals for multiple symbols.

        Args:
            symbols: List of unified symbols
            timeframe: Candle timeframe
            lookback: Number of bars to analyze
            enabled_strategies: List of strategy names to run (None = all enabled)

        Returns:
            Dict of symbol -> list of StrategySignal
        """
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

                # Fetch market data
                market_data = await fetcher.fetch_market_data(symbol, timeframe, lookback)

                if not market_data.candles:
                    logger.warning(f"No data for {symbol_str}")
                    results[symbol_str] = []
                    continue

                # Convert to DataFrame for analysis
                candles_df = pd.DataFrame([c.to_dict() for c in market_data.candles])

                # Generate signals from all sources
                all_signals = []

                # 1. Technical indicators
                tech_signals = await self._generate_technical_signals(candles_df, symbol_str)
                all_signals.extend(tech_signals)

                # 2. Pattern detection
                pattern_signals = await self._generate_pattern_signals(candles_df, symbol_str)
                all_signals.extend(pattern_signals)

                # 3. Kronos forecast (if enabled)
                if self.config.get("use_kronos", True):
                    kronos_signals = await self._generate_kronos_signals(market_data.candles, symbol_str)
                    all_signals.extend(kronos_signals)

                # 4. Funding/basis signals
                if symbol.market_type != MarketType.SPOT:
                    funding_signals = await self._generate_funding_signals(market_data, symbol_str)
                    all_signals.extend(funding_signals)

                # 5. Strategy-specific signals
                strategy_signals = await self._generate_strategy_signals(
                    candles_df, symbol_str, enabled_strategies
                )
                all_signals.extend(strategy_signals)

                results[symbol_str] = all_signals

            except Exception as e:
                logger.error(f"Signal generation error for {symbol_str}: {e}")
                results[symbol_str] = []

        return results

    async def _generate_technical_signals(
        self,
        candles_df: pd.DataFrame,
        symbol: str,
    ) -> list[StrategySignal]:
        """Generate signals from technical indicators."""
        analyzer = TechnicalAnalyzer(candles_df.to_dict(orient="records"))
        indicators = analyzer.compute_all()

        signals = compute_signals(indicators, [])

        return [
            StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction=s["direction"],
                strength=s["strength"],
                signal_type=s["type"],
                source="technical",
                metadata={"indicators": indicators, "reason": s.get("reason")},
            )
            for s in signals
        ]

    async def _generate_pattern_signals(
        self,
        candles_df: pd.DataFrame,
        symbol: str,
    ) -> list[StrategySignal]:
        """Generate signals from chart patterns."""
        analyzer = TechnicalAnalyzer(candles_df.to_dict(orient="records"))
        patterns = analyzer.detect_patterns()

        signals = compute_signals({}, patterns)

        return [
            StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction=s["direction"],
                strength=s["strength"],
                signal_type=s["type"],
                source="pattern",
                metadata={"pattern": s.get("type"), "reason": s.get("reason")},
            )
            for s in signals
        ]

    async def _generate_kronos_signals(
        self,
        candles: list,
        symbol: str,
    ) -> list[StrategySignal]:
        """Generate signals from Kronos forecast."""
        try:
            from cryptobot.research.models import get_kronos_tool

            kronos = await get_kronos_tool()
            pred_df = await kronos.predictor.predict(candles, pred_len=48)

            if pred_df.empty:
                return []

            # Calculate predicted return
            current_price = float(candles[-1].close)
            predicted_price = float(pred_df["close"].iloc[-1])
            pred_return = (predicted_price - current_price) / current_price

            signals = []
            if pred_return > 0.002:  # 0.2% threshold
                signals.append(StrategySignal(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    direction="long",
                    strength=min(abs(pred_return) * 100, 0.8),
                    signal_type="kronos_forecast",
                    source="model",
                    metadata={
                        "pred_return": pred_return,
                        "pred_price": predicted_price,
                        "horizon_bars": 48,
                    },
                ))
            elif pred_return < -0.002:
                signals.append(StrategySignal(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    direction="short",
                    strength=min(abs(pred_return) * 100, 0.8),
                    signal_type="kronos_forecast",
                    source="model",
                    metadata={
                        "pred_return": pred_return,
                        "pred_price": predicted_price,
                        "horizon_bars": 48,
                    },
                ))

            return signals

        except Exception as e:
            logger.debug(f"Kronos signal error: {e}")
            return []

    async def _generate_funding_signals(
        self,
        market_data,
        symbol: str,
    ) -> list[StrategySignal]:
        """Generate signals from funding rates and basis."""
        if not market_data.funding_rates:
            return []

        funding = market_data.funding_rates[0]
        rate = float(funding.rate)

        signals = []
        if rate > 0.0005:  # High positive funding - longs pay
            signals.append(StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction="short",
                strength=min(rate * 1000, 0.7),
                signal_type="funding_extreme",
                source="funding",
                metadata={"funding_rate": rate, "annualized": funding.annualized_rate},
            ))
        elif rate < -0.0005:  # Negative funding - shorts pay
            signals.append(StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction="long",
                strength=min(abs(rate) * 1000, 0.7),
                signal_type="funding_extreme",
                source="funding",
                metadata={"funding_rate": rate, "annualized": funding.annualized_rate},
            ))

        return signals

    async def _generate_strategy_signals(
        self,
        candles_df: pd.DataFrame,
        symbol: str,
        enabled_strategies: list[str] | None,
    ) -> list[StrategySignal]:
        """Generate signals from configured strategies."""
        signals = []

        for name, config in self.strategy_configs.items():
            if not config.get("enabled", False):
                continue

            if enabled_strategies and name not in enabled_strategies:
                continue

            # This would instantiate specific strategy classes
            # For now, we'll use a generic approach
            try:
                strategy_signals = await self._run_strategy(name, config, candles_df, symbol)
                signals.extend(strategy_signals)
            except Exception as e:
                logger.debug(f"Strategy {name} error: {e}")

        return signals

    async def _run_strategy(
        self,
        name: str,
        config: dict[str, Any],
        candles_df: pd.DataFrame,
        symbol: str,
    ) -> list[StrategySignal]:
        """Run a specific strategy."""
        params = config.get("parameters", {})

        if name == "trend_follow":
            return await self._trend_follow_strategy(candles_df, symbol, params)
        elif name == "mean_reversion":
            return await self._mean_reversion_strategy(candles_df, symbol, params)
        elif name == "funding_arbitrage":
            return await self._funding_arb_strategy(candles_df, symbol, params)
        elif name == "kronos_forecast":
            return await self._kronos_strategy(candles_df, symbol, params)

        return []

    async def _trend_follow_strategy(
        self,
        candles_df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> list[StrategySignal]:
        """Trend following strategy."""
        analyzer = TechnicalAnalyzer(candles_df.to_dict(orient="records"))
        indicators = analyzer.compute_all()

        signals = []
        if indicators.get("ema_trend") == "bullish":
            signals.append(StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction="long",
                strength=indicators.get("trend_strength", 0.5),
                signal_type="strategy_trend_follow",
                source="strategy",
                metadata={"strategy": "trend_follow", "params": params},
            ))
        elif indicators.get("ema_trend") == "bearish":
            signals.append(StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction="short",
                strength=indicators.get("trend_strength", 0.5),
                signal_type="strategy_trend_follow",
                source="strategy",
                metadata={"strategy": "trend_follow", "params": params},
            ))

        return signals

    async def _mean_reversion_strategy(
        self,
        candles_df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> list[StrategySignal]:
        """Mean reversion strategy."""
        analyzer = TechnicalAnalyzer(candles_df.to_dict(orient="records"))
        indicators = analyzer.compute_all()

        signals = []
        rsi = indicators.get("rsi")
        bb = indicators.get("bb")

        if rsi and rsi < params.get("rsi_oversold", 30):
            signals.append(StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction="long",
                strength=(params.get("rsi_oversold", 30) - rsi) / params.get("rsi_oversold", 30) * 0.6,
                signal_type="strategy_mean_reversion",
                source="strategy",
                metadata={"strategy": "mean_reversion", "rsi": rsi, "params": params},
            ))
        elif rsi and rsi > params.get("rsi_overbought", 70):
            signals.append(StrategySignal(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                direction="short",
                strength=(rsi - params.get("rsi_overbought", 70)) / (100 - params.get("rsi_overbought", 70)) * 0.6,
                signal_type="strategy_mean_reversion",
                source="strategy",
                metadata={"strategy": "mean_reversion", "rsi": rsi, "params": params},
            ))

        return signals

    async def _funding_arb_strategy(
        self,
        candles_df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> list[StrategySignal]:
        """Funding arbitrage strategy."""
        # Would need multi-exchange funding data
        return []

    async def _kronos_strategy(
        self,
        candles_df: pd.DataFrame,
        symbol: str,
        params: dict,
    ) -> list[StrategySignal]:
        """Kronos-based strategy."""
        # Handled by _generate_kronos_signals
        return []

    def combine_signals(
        self,
        signals: list[StrategySignal],
        method: str = "weighted_vote",
        weights: dict[str, float] | None = None,
    ) -> StrategySignal | None:
        """
        Combine multiple signals into a single consensus signal.

        Methods:
        - weighted_vote: Weight by source reliability
        - strongest: Take strongest signal
        - average: Average direction and strength
        """
        if not signals:
            return None

        # Default weights by source
        default_weights = {
            "model": 0.3,
            "technical": 0.2,
            "pattern": 0.15,
            "strategy": 0.2,
            "funding": 0.1,
            "sentiment": 0.05,
        }
        weights = weights or default_weights

        if method == "weighted_vote":
            long_score = 0.0
            short_score = 0.0
            total_weight = 0.0

            for s in signals:
                w = weights.get(s.source, 0.1) * s.strength
                if s.direction == "long":
                    long_score += w
                elif s.direction == "short":
                    short_score += w
                total_weight += w

            if long_score > short_score and long_score > 0.3:
                return StrategySignal(
                    symbol=signals[0].symbol,
                    timestamp=datetime.utcnow(),
                    direction="long",
                    strength=min(long_score / total_weight, 1.0) if total_weight else 0,
                    signal_type="consensus",
                    source="ensemble",
                    metadata={"long_score": long_score, "short_score": short_score},
                )
            elif short_score > long_score and short_score > 0.3:
                return StrategySignal(
                    symbol=signals[0].symbol,
                    timestamp=datetime.utcnow(),
                    direction="short",
                    strength=min(short_score / total_weight, 1.0) if total_weight else 0,
                    signal_type="consensus",
                    source="ensemble",
                    metadata={"long_score": long_score, "short_score": short_score},
                )

        elif method == "strongest":
            return max(signals, key=lambda s: s.strength)

        return None