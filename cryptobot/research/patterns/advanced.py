"""
Advanced pattern detection: FVG, Order Blocks, Volume Anomalies, Breakouts.
Combines patterns from freqtrade, day-trader-skill, and hummingbot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import talib

from cryptobot.data.models import Candle

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Advanced pattern types."""

    FVG_BULLISH = "fvg_bullish"
    FVG_BEARISH = "fvg_bearish"
    ORDER_BLOCK_BULLISH = "order_block_bullish"
    ORDER_BLOCK_BEARISH = "order_block_bearish"
    BREAKOUT_BULLISH = "breakout_bullish"
    BREAKOUT_BEARISH = "breakout_bearish"
    VOLUME_ANOMALY = "volume_anomaly"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    FAIR_VALUE_GAP = "fair_value_gap"


class MarketRegime(str, Enum):
    """Market regime classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


@dataclass
class AdvancedPattern:
    """Detected advanced pattern."""

    pattern_type: PatternType
    symbol: str
    timestamp: datetime
    price: float
    confidence: float
    metadata: dict[str, Any]
    timeframe: str


@dataclass
class VolumeAnomaly:
    """Volume anomaly detection result."""

    symbol: str
    timestamp: datetime
    volume_ratio: float  # current / average
    price_change: float
    anomaly_type: str  # "spike", "dry_up", "accumulation", "distribution"
    confidence: float


@dataclass
class MissedTrade:
    """Track missed trading opportunities for learning."""

    symbol: str
    timestamp: datetime
    missed_type: str  # "missed_long", "missed_short", "early_exit", "late_entry"
    signal_price: float
    actual_price: float
    potential_pnl_pct: float
    reason: str
    market_context: dict
    lesson: str = ""


class AdvancedPatternDetector:
    """
    Advanced pattern detector combining multiple strategies.

    Detects:
    - Fair Value Gaps (FVG) - Bullish/Bearish
    - Order Blocks - Institutional footprints
    - Breakouts - With volume confirmation
    - Liquidity Sweeps - Stop hunts
    - Volume Anomalies - Unusual activity
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.fvg_lookback = self.config.get("fvg_lookback", 3)
        self.ob_lookback = self.config.get("ob_lookback", 10)
        self.breakout_lookback = self.config.get("breakout_lookback", 20)
        self.volume_ma_period = self.config.get("volume_ma_period", 20)
        self.volume_spike_threshold = self.config.get("volume_spike_threshold", 3.0)
        self.min_fvg_size = self.config.get("min_fvg_size", 0.001)  # 0.1%

    def detect_all(self, candles: list[Candle], timeframe: str = "1h") -> list[AdvancedPattern]:
        """Detect all advanced patterns."""
        if len(candles) < max(self.ob_lookback, self.breakout_lookback) + 5:
            return []

        df = self._to_dataframe(candles)
        patterns = []

        # Detect FVGs
        patterns.extend(self._detect_fvgs(df, timeframe))

        # Detect Order Blocks
        patterns.extend(self._detect_order_blocks(df, timeframe))

        # Detect Breakouts
        patterns.extend(self._detect_breakouts(df, timeframe))

        # Detect Liquidity Sweeps
        patterns.extend(self._detect_liquidity_sweeps(df, timeframe))

        return patterns

    def _to_dataframe(self, candles: list[Candle]) -> pd.DataFrame:
        """Convert candles to DataFrame with technical indicators."""
        data = []
        for c in candles:
            data.append({
                "timestamp": c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
            })

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").sort_index()

        # Add indicators
        df["atr"] = talib.ATR(df["high"].values, df["low"].values, df["close"].values, timeperiod=14)
        df["rsi"] = talib.RSI(df["close"].values, timeperiod=14)
        df["ema_20"] = talib.EMA(df["close"].values, timeperiod=20)
        df["ema_50"] = talib.EMA(df["close"].values, timeperiod=50)
        df["volume_ma"] = df["volume"].rolling(self.volume_ma_period).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]

        # Bollinger Bands
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = talib.BBANDS(
            df["close"].values, timeperiod=20, nbdevup=2, nbdevdn=2
        )

        return df

    def _detect_fvgs(self, df: pd.DataFrame, timeframe: str) -> list[AdvancedPattern]:
        """Detect Fair Value Gaps (3-candle pattern)."""
        patterns = []

        for i in range(2, len(df)):
            c0 = df.iloc[i - 2]  # First candle
            c1 = df.iloc[i - 1]  # Middle candle (gap)
            c2 = df.iloc[i]      # Third candle

            # Bullish FVG: Gap between c0 high and c2 low
            if c0["high"] < c2["low"]:
                gap_size = (c2["low"] - c0["high"]) / c0["high"]
                if gap_size >= self.min_fvg_size:
                    patterns.append(AdvancedPattern(
                        pattern_type=PatternType.FVG_BULLISH,
                        symbol="",  # Set by caller
                        timestamp=df.index[i],
                        price=c2["low"],
                        confidence=min(gap_size * 100, 0.9),
                        metadata={
                            "gap_size_pct": gap_size * 100,
                            "gap_top": c2["low"],
                            "gap_bottom": c0["high"],
                            "candle_1_high": c0["high"],
                            "candle_3_low": c2["low"],
                        },
                        timeframe=timeframe,
                    ))

            # Bearish FVG: Gap between c2 high and c0 low
            if c2["high"] < c0["low"]:
                gap_size = (c0["low"] - c2["high"]) / c0["low"]
                if gap_size >= self.min_fvg_size:
                    patterns.append(AdvancedPattern(
                        pattern_type=PatternType.FVG_BEARISH,
                        symbol="",
                        timestamp=df.index[i],
                        price=c2["high"],
                        confidence=min(gap_size * 100, 0.9),
                        metadata={
                            "gap_size_pct": gap_size * 100,
                            "gap_top": c0["low"],
                            "gap_bottom": c2["high"],
                            "candle_1_low": c0["low"],
                            "candle_3_high": c2["high"],
                        },
                        timeframe=timeframe,
                    ))

        return patterns

    def _detect_order_blocks(self, df: pd.DataFrame, timeframe: str) -> list[AdvancedPattern]:
        """Detect Order Blocks - Institutional footprints before strong moves."""
        patterns = []

        for i in range(self.ob_lookback, len(df) - 3):
            # Look for strong move after consolidation
            move_candles = df.iloc[i:i+3]

            # Calculate move strength
            move_pct = abs(move_candles["close"].iloc[-1] - move_candles["open"].iloc[0]) / move_candles["open"].iloc[0]

            if move_pct < 0.01:  # Need at least 1% move
                continue

            # Look back for order block (last opposite candle before move)
            lookback_start = max(0, i - self.ob_lookback)
            lookback = df.iloc[lookback_start:i]

            if len(lookback) < 3:
                continue

            # Bullish Order Block: Last bearish candle before strong up move
            if move_candles["close"].iloc[-1] > move_candles["open"].iloc[0]:
                bearish_candles = lookback[lookback["close"] < lookback["open"]]
                if len(bearish_candles) > 0:
                    ob = bearish_candles.iloc[-1]  # Last bearish candle
                    # Validate: price should not have returned to OB
                    subsequent_low = df.iloc[i:i+10]["low"].min() if i+10 <= len(df) else df.iloc[i:]["low"].min()
                    if subsequent_low > ob["low"]:
                        patterns.append(AdvancedPattern(
                            pattern_type=PatternType.ORDER_BLOCK_BULLISH,
                            symbol="",
                            timestamp=ob.name,
                            price=ob["low"],
                            confidence=0.75,
                            metadata={
                                "ob_high": ob["high"],
                                "ob_low": ob["low"],
                                "ob_open": ob["open"],
                                "ob_close": ob["close"],
                                "move_pct": move_pct * 100,
                                "mitigated": False,
                            },
                            timeframe=timeframe,
                        ))

            # Bearish Order Block: Last bullish candle before strong down move
            else:
                bullish_candles = lookback[lookback["close"] > lookback["open"]]
                if len(bullish_candles) > 0:
                    ob = bullish_candles.iloc[-1]
                    subsequent_high = df.iloc[i:i+10]["high"].max() if i+10 <= len(df) else df.iloc[i:]["high"].max()
                    if subsequent_high < ob["high"]:
                        patterns.append(AdvancedPattern(
                            pattern_type=PatternType.ORDER_BLOCK_BEARISH,
                            symbol="",
                            timestamp=ob.name,
                            price=ob["high"],
                            confidence=0.75,
                            metadata={
                                "ob_high": ob["high"],
                                "ob_low": ob["low"],
                                "ob_open": ob["open"],
                                "ob_close": ob["close"],
                                "move_pct": move_pct * 100,
                                "mitigated": False,
                            },
                            timeframe=timeframe,
                        ))

        return patterns

    def _detect_breakouts(self, df: pd.DataFrame, timeframe: str) -> list[AdvancedPattern]:
        """Detect Breakouts with volume confirmation."""
        patterns = []

        for i in range(self.breakout_lookback, len(df)):
            # Calculate resistance/support levels
            lookback = df.iloc[i - self.breakout_lookback:i]

            resistance = lookback["high"].max()
            support = lookback["low"].min()
            avg_volume = lookback["volume"].mean()

            current = df.iloc[i]
            current_volume = current["volume"]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            # Need volume confirmation
            if volume_ratio < 1.5:
                continue

            # Bullish breakout
            if current["close"] > resistance and current["open"] <= resistance:
                patterns.append(AdvancedPattern(
                    pattern_type=PatternType.BREAKOUT_BULLISH,
                    symbol="",
                    timestamp=df.index[i],
                    price=current["close"],
                    confidence=min(volume_ratio / 5, 0.85),
                    metadata={
                        "resistance": resistance,
                        "support": support,
                        "volume_ratio": volume_ratio,
                        "breakout_pct": (current["close"] - resistance) / resistance * 100,
                    },
                    timeframe=timeframe,
                ))

            # Bearish breakdown
            elif current["close"] < support and current["open"] >= support:
                patterns.append(AdvancedPattern(
                    pattern_type=PatternType.BREAKOUT_BEARISH,
                    symbol="",
                    timestamp=df.index[i],
                    price=current["close"],
                    confidence=min(volume_ratio / 5, 0.85),
                    metadata={
                        "resistance": resistance,
                        "support": support,
                        "volume_ratio": volume_ratio,
                        "breakdown_pct": (support - current["close"]) / support * 100,
                    },
                    timeframe=timeframe,
                ))

        return patterns

    def _detect_liquidity_sweeps(self, df: pd.DataFrame, timeframe: str) -> list[AdvancedPattern]:
        """Detect Liquidity Sweeps - Price sweeps highs/lows then reverses."""
        patterns = []

        for i in range(5, len(df) - 2):
            current = df.iloc[i]
            prev = df.iloc[i - 1]

            # Look for sweep of recent high
            recent_high = df.iloc[i - 5:i]["high"].max()
            recent_low = df.iloc[i - 5:i]["low"].min()

            # Bullish sweep: Sweep low then close higher
            if current["low"] < recent_low and current["close"] > current["open"]:
                sweep_depth = (recent_low - current["low"]) / recent_low
                if sweep_depth > 0.002:  # At least 0.2% sweep
                    patterns.append(AdvancedPattern(
                        pattern_type=PatternType.LIQUIDITY_SWEEP,
                        symbol="",
                        timestamp=df.index[i],
                        price=current["close"],
                        confidence=min(sweep_depth * 50, 0.8),
                        metadata={
                            "sweep_type": "bullish",
                            "swept_level": recent_low,
                            "sweep_depth_pct": sweep_depth * 100,
                            "reversal_candle": True,
                        },
                        timeframe=timeframe,
                    ))

            # Bearish sweep: Sweep high then close lower
            if current["high"] > recent_high and current["close"] < current["open"]:
                sweep_depth = (current["high"] - recent_high) / recent_high
                if sweep_depth > 0.002:
                    patterns.append(AdvancedPattern(
                        pattern_type=PatternType.LIQUIDITY_SWEEP,
                        symbol="",
                        timestamp=df.index[i],
                        price=current["close"],
                        confidence=min(sweep_depth * 50, 0.8),
                        metadata={
                            "sweep_type": "bearish",
                            "swept_level": recent_high,
                            "sweep_depth_pct": sweep_depth * 100,
                            "reversal_candle": True,
                        },
                        timeframe=timeframe,
                    ))

        return patterns

    def detect_volume_anomalies(self, df: pd.DataFrame) -> list[VolumeAnomaly]:
        """Detect volume anomalies for early signal detection."""
        anomalies = []

        for i in range(self.volume_ma_period, len(df)):
            current = df.iloc[i]
            volume_ratio = current["volume_ratio"]
            price_change = (current["close"] - current["open"]) / current["open"]

            if volume_ratio >= self.volume_spike_threshold:
                # Volume spike
                if price_change > 0.01:
                    anomaly_type = "accumulation"
                elif price_change < -0.01:
                    anomaly_type = "distribution"
                else:
                    anomaly_type = "spike"

                anomalies.append(VolumeAnomaly(
                    symbol="",
                    timestamp=df.index[i],
                    volume_ratio=volume_ratio,
                    price_change=price_change,
                    anomaly_type=anomaly_type,
                    confidence=min(volume_ratio / 10, 0.9),
                ))

            elif volume_ratio < 0.3:
                # Volume dry up
                anomalies.append(VolumeAnomaly(
                    symbol="",
                    timestamp=df.index[i],
                    volume_ratio=volume_ratio,
                    price_change=price_change,
                    anomaly_type="dry_up",
                    confidence=0.6,
                ))

        return anomalies

    def classify_market_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Classify current market regime."""
        if len(df) < 50:
            return MarketRegime.SIDEWAYS

        recent = df.iloc[-20:]
        trend = (recent["close"].iloc[-1] - recent["close"].iloc[0]) / recent["close"].iloc[0]
        volatility = recent["close"].pct_change().std()
        avg_volume = recent["volume"].mean()
        current_volume = df.iloc[-1]["volume"]

        # High volatility regime
        if volatility > 0.03:
            return MarketRegime.HIGH_VOLATILITY

        # Low volatility
        if volatility < 0.01:
            return MarketRegime.LOW_VOLATILITY

        # Strong trend
        if trend > 0.05:
            return MarketRegime.BULLISH
        elif trend < -0.05:
            return MarketRegime.BEARISH

        return MarketRegime.SIDEWAYS


class MissedTradeTracker:
    """
    Tracks missed trading opportunities for continuous learning.

    From user requirements:
    - "didn't bought but graph goes up"
    - "sell fast or missed buying something but later got idea i should have bought"
    - "AI learn this or store this"
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.missed_trades: list[MissedTrade] = []
        self.max_history = self.config.get("max_history", 1000)
        self.signal_threshold = self.config.get("signal_threshold", 0.7)

    def check_missed_opportunities(
        self,
        symbol: str,
        patterns: list[AdvancedPattern],
        current_price: float,
        signal_confidence: float,
        action_taken: str | None,
    ) -> list[MissedTrade]:
        """
        Check for missed opportunities after a signal was generated.

        Args:
            symbol: Trading symbol
            patterns: Detected patterns
            current_price: Current market price
            signal_confidence: Confidence of generated signal
            action_taken: "long", "short", "hold", or None

        Returns:
            List of missed trades detected
        """
        missed = []
        current_time = datetime.utcnow()

        for pattern in patterns:
            if pattern.confidence < self.signal_threshold:
                continue

            # Calculate potential PnL if signal was followed
            potential_pnl = self._calculate_potential_pnl(pattern, current_price)

            # Check if we missed this signal
            if action_taken is None or action_taken == "hold":
                if pattern.pattern_type in (PatternType.FVG_BULLISH, PatternType.ORDER_BLOCK_BULLISH,
                                            PatternType.BREAKOUT_BULLISH):
                    missed.append(MissedTrade(
                        symbol=symbol,
                        timestamp=datetime.utcnow(),
                        missed_type="missed_long",
                        signal_price=pattern.price,
                        actual_price=current_price,
                        potential_pnl_pct=potential_pnl,
                        reason=f"High-confidence {pattern.pattern_type.value} signal ignored",
                        market_context={
                            "pattern": pattern.pattern_type.value,
                            "signal_confidence": signal_confidence,
                            "pattern_confidence": pattern.confidence,
                        },
                        lesson=f"Missed {potential_pnl:.2f}% gain from {pattern.pattern_type.value}. Review why signal was not acted upon.",
                    ))

                elif pattern.pattern_type in (PatternType.FVG_BEARISH, PatternType.ORDER_BLOCK_BEARISH,
                                              PatternType.BREAKOUT_BEARISH):
                    missed.append(MissedTrade(
                        symbol=symbol,
                        timestamp=datetime.utcnow(),
                        missed_type="missed_short",
                        signal_price=pattern.price,
                        actual_price=current_price,
                        potential_pnl_pct=potential_pnl,
                        reason=f"High-confidence {pattern.pattern_type.value} signal ignored",
                        market_context={
                            "pattern": pattern.pattern_type.value,
                            "signal_confidence": signal_confidence,
                            "pattern_confidence": pattern.confidence,
                        },
                        lesson=f"Missed {potential_pnl:.2f}% gain from {pattern.pattern_type.value}. Review why signal was not acted upon.",
                    ))

            # Check for early exit (sold too fast)
            elif action_taken in ("long", "short"):
                # This would need position tracking - simplified here
                pass

        # Store in history
        self.missed_trades.extend(missed)
        if len(self.missed_trades) > self.max_history:
            self.missed_trades = self.missed_trades[-self.max_history:]

        return missed

    def _calculate_potential_pnl(self, pattern: AdvancedPattern, current_price: float) -> float:
        """Calculate potential PnL if pattern was traded."""
        if pattern.pattern_type in (PatternType.FVG_BULLISH, PatternType.ORDER_BLOCK_BULLISH,
                                    PatternType.BREAKOUT_BULLISH):
            return (current_price - pattern.price) / pattern.price * 100
        else:
            return (pattern.price - current_price) / pattern.price * 100

    def get_lessons(self, symbol: str | None = None, limit: int = 10) -> list[str]:
        """Get lessons from missed trades for AI learning."""
        trades = self.missed_trades
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]

        recent = sorted(trades, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [t.lesson for t in recent if t.lesson]

    def get_statistics(self) -> dict[str, Any]:
        """Get missed trade statistics."""
        if not self.missed_trades:
            return {"total": 0}

        total = len(self.missed_trades)
        missed_longs = len([t for t in self.missed_trades if t.missed_type == "missed_long"])
        missed_shorts = len([t for t in self.missed_trades if t.missed_type == "missed_short"])

        avg_potential = np.mean([t.potential_pnl_pct for t in self.missed_trades])
        max_potential = max([t.potential_pnl_pct for t in self.missed_trades]) if self.missed_trades else 0

        return {
            "total_missed": total,
            "missed_longs": missed_longs,
            "missed_shorts": missed_shorts,
            "avg_potential_pnl_pct": avg_potential,
            "max_potential_pnl_pct": max_potential,
            "by_symbol": self._group_by_symbol(),
        }

    def _group_by_symbol(self) -> dict[str, int]:
        groups = {}
        for t in self.missed_trades:
            groups[t.symbol] = groups.get(t.symbol, 0) + 1
        return groups