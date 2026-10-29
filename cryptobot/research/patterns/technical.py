"""
Technical analysis patterns and indicators.
Adapted from freqtrade's strategy indicators, day-trader-skill scanner, and Vibe-Trading's signal engine.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import talib

from cryptobot.data.models import Candle

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    Technical analysis engine for candles.

    Provides:
    - Standard indicators (EMA, RSI, MACD, BB, ATR, ADX, etc.)
    - Pattern detection (ORB, flags, RSI divergence, MA reclaim, etc.)
    - Signal generation
    """

    def __init__(self, candles: list[Candle | dict]):
        """Initialize with candles."""
        self.candles = candles
        self.df = self._to_dataframe(candles)
        self._indicators_cache: dict[str, Any] = {}

    def _to_dataframe(self, candles: list[Candle | dict]) -> pd.DataFrame:
        """Convert candles to DataFrame."""
        if not candles:
            return pd.DataFrame()

        if isinstance(candles[0], dict):
            df = pd.DataFrame(candles)
        else:
            df = pd.DataFrame([c.to_dict() for c in candles])

        # Ensure timestamp is datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").sort_index()

        # Ensure numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def compute_all(self, indicators: list[str] | None = None) -> dict[str, Any]:
        """Compute all requested indicators."""
        if self.df.empty:
            return {}

        if indicators is None:
            indicators = [
                "ema", "sma", "rsi", "macd", "bb", "atr", "adx",
                "stoch", "cci", "obv", "vwap", "supertrend",
            ]

        results = {}
        for ind in indicators:
            try:
                method = getattr(self, f"_compute_{ind}", None)
                if method:
                    results[ind] = method()
            except Exception as e:
                logger.debug(f"Indicator {ind} failed: {e}")
                results[ind] = None

        return results

    # ===== Trend Indicators =====
    def _compute_ema(self, periods: list[int] = None) -> dict[str, Any]:
        """Exponential Moving Averages."""
        periods = periods or [9, 21, 50, 200]
        result = {}
        for p in periods:
            if len(self.df) >= p:
                ema = talib.EMA(self.df["close"].values, timeperiod=p)
                result[f"ema_{p}"] = ema[-1] if not np.isnan(ema[-1]) else None

        # Trend determination
        if all(k in result for k in ["ema_9", "ema_21", "ema_50"]):
            if result["ema_9"] > result["ema_21"] > result["ema_50"]:
                result["ema_trend"] = "bullish"
                result["trend_strength"] = min(
                    (result["ema_9"] - result["ema_50"]) / result["ema_50"] * 100, 1.0
                )
            elif result["ema_9"] < result["ema_21"] < result["ema_50"]:
                result["ema_trend"] = "bearish"
                result["trend_strength"] = min(
                    (result["ema_50"] - result["ema_9"]) / result["ema_50"] * 100, 1.0
                )
            else:
                result["ema_trend"] = "neutral"
                result["trend_strength"] = 0.0

        return result

    def _compute_sma(self, periods: list[int] = None) -> dict[str, Any]:
        """Simple Moving Averages."""
        periods = periods or [20, 50, 200]
        result = {}
        for p in periods:
            if len(self.df) >= p:
                sma = talib.SMA(self.df["close"].values, timeperiod=p)
                result[f"sma_{p}"] = sma[-1] if not np.isnan(sma[-1]) else None
        return result

    def _compute_adx(self, period: int = 14) -> dict[str, Any]:
        """Average Directional Index."""
        if len(self.df) < period + 1:
            return {}

        adx = talib.ADX(self.df["high"].values, self.df["low"].values, self.df["close"].values, timeperiod=period)
        plus_di = talib.PLUS_DI(self.df["high"].values, self.df["low"].values, self.df["close"].values, timeperiod=period)
        minus_di = talib.MINUS_DI(self.df["high"].values, self.df["low"].values, self.df["close"].values, timeperiod=period)

        return {
            "adx": adx[-1] if not np.isnan(adx[-1]) else None,
            "plus_di": plus_di[-1] if not np.isnan(plus_di[-1]) else None,
            "minus_di": minus_di[-1] if not np.isnan(minus_di[-1]) else None,
            "trend_strength": "strong" if adx[-1] > 25 else "weak" if not np.isnan(adx[-1]) else None,
        }

    def _compute_supertrend(self, period: int = 10, multiplier: float = 3.0) -> dict[str, Any]:
        """SuperTrend indicator."""
        if len(self.df) < period:
            return {}

        # Calculate ATR
        atr = talib.ATR(self.df["high"].values, self.df["low"].values, self.df["close"].values, timeperiod=period)

        hl2 = (self.df["high"] + self.df["low"]) / 2
        upper = hl2 + multiplier * atr
        lower = hl2 - multiplier * atr

        supertrend = np.zeros(len(self.df))
        direction = np.zeros(len(self.df))

        for i in range(1, len(self.df)):
            if self.df["close"].iloc[i] > upper.iloc[i - 1]:
                direction[i] = 1
            elif self.df["close"].iloc[i] < lower.iloc[i - 1]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]
                if direction[i] == 1 and lower.iloc[i] < lower.iloc[i - 1]:
                    lower.iloc[i] = lower.iloc[i - 1]
                if direction[i] == -1 and upper.iloc[i] > upper.iloc[i - 1]:
                    upper.iloc[i] = upper.iloc[i - 1]

            supertrend[i] = lower.iloc[i] if direction[i] == 1 else upper.iloc[i]

        return {
            "supertrend": supertrend[-1] if not np.isnan(supertrend[-1]) else None,
            "direction": int(direction[-1]) if not np.isnan(direction[-1]) else 0,
            "upper": upper.iloc[-1] if not np.isnan(upper.iloc[-1]) else None,
            "lower": lower.iloc[-1] if not np.isnan(lower.iloc[-1]) else None,
        }

    # ===== Momentum Indicators =====
    def _compute_rsi(self, period: int = 14) -> dict[str, Any]:
        """Relative Strength Index."""
        if len(self.df) < period + 1:
            return {}

        rsi = talib.RSI(self.df["close"].values, timeperiod=period)
        return {
            "rsi": rsi[-1] if not np.isnan(rsi[-1]) else None,
            "rsi_signal": "oversold" if rsi[-1] < 30 else "overbought" if rsi[-1] > 70 else "neutral",
        }

    def _compute_macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> dict[str, Any]:
        """MACD."""
        if len(self.df) < slow + signal:
            return {}

        macd, macd_signal, macd_hist = talib.MACD(
            self.df["close"].values,
            fastperiod=fast,
            slowperiod=slow,
            signalperiod=signal,
        )

        return {
            "macd": macd[-1] if not np.isnan(macd[-1]) else None,
            "signal": macd_signal[-1] if not np.isnan(macd_signal[-1]) else None,
            "histogram": macd_hist[-1] if not np.isnan(macd_hist[-1]) else None,
            "signal_cross": "bullish" if macd_hist[-1] > 0 and macd_hist[-2] <= 0 else
                           "bearish" if macd_hist[-1] < 0 and macd_hist[-2] >= 0 else "none",
        }

    def _compute_stoch(self, period: int = 14) -> dict[str, Any]:
        """Stochastic Oscillator."""
        if len(self.df) < period:
            return {}

        slowk, slowd = talib.STOCH(
            self.df["high"].values,
            self.df["low"].values,
            self.df["close"].values,
            fastk_period=period,
            slowk_period=3,
            slowd_period=3,
        )

        return {
            "stoch_k": slowk[-1] if not np.isnan(slowk[-1]) else None,
            "stoch_d": slowd[-1] if not np.isnan(slowd[-1]) else None,
        }

    def _compute_cci(self, period: int = 20) -> dict[str, Any]:
        """Commodity Channel Index."""
        if len(self.df) < period:
            return {}

        cci = talib.CCI(
            self.df["high"].values,
            self.df["low"].values,
            self.df["close"].values,
            timeperiod=period,
        )

        return {
            "cci": cci[-1] if not np.isnan(cci[-1]) else None,
        }

    # ===== Volatility Indicators =====
    def _compute_atr(self, period: int = 14) -> dict[str, Any]:
        """Average True Range."""
        if len(self.df) < period + 1:
            return {}

        atr = talib.ATR(
            self.df["high"].values,
            self.df["low"].values,
            self.df["close"].values,
            timeperiod=period,
        )

        # ATR percentile (relative to last 100 bars)
        atr_series = talib.ATR(
            self.df["high"].values,
            self.df["low"].values,
            self.df["close"].values,
            timeperiod=period,
        )
        atr_percentile = None
        if len(atr_series) >= 100:
            atr_percentile = np.searchsorted(np.sort(atr_series[-100:]), atr[-1]) / 100 * 100

        return {
            "atr": atr[-1] if not np.isnan(atr[-1]) else None,
            "atr_percentile": atr_percentile,
            "atr_pct": (atr[-1] / self.df["close"].iloc[-1] * 100) if not np.isnan(atr[-1]) else None,
        }

    def _compute_bb(self, period: int = 20, std: float = 2.0) -> dict[str, Any]:
        """Bollinger Bands."""
        if len(self.df) < period:
            return {}

        upper, middle, lower = talib.BBANDS(
            self.df["close"].values,
            timeperiod=period,
            nbdevup=std,
            nbdevdn=std,
        )

        # Band width and %B
        bb_width = (upper[-1] - lower[-1]) / middle[-1] * 100 if middle[-1] != 0 else 0
        percent_b = (self.df["close"].iloc[-1] - lower[-1]) / (upper[-1] - lower[-1]) if upper[-1] != lower[-1] else 0.5

        return {
            "bb_upper": upper[-1] if not np.isnan(upper[-1]) else None,
            "bb_middle": middle[-1] if not np.isnan(middle[-1]) else None,
            "bb_lower": lower[-1] if not np.isnan(lower[-1]) else None,
            "bb_width_pct": bb_width,
            "bb_percent_b": percent_b,
            "bb_squeeze": bb_width < 5,  # Squeeze threshold
        }

    # ===== Volume Indicators =====
    def _compute_obv(self) -> dict[str, Any]:
        """On-Balance Volume."""
        if len(self.df) < 2:
            return {}

        obv = talib.OBV(self.df["close"].values, self.df["volume"].values)
        obv_sma = talib.SMA(obv, timeperiod=20)

        return {
            "obv": obv[-1] if not np.isnan(obv[-1]) else None,
            "obv_trend": "rising" if obv[-1] > obv_sma[-1] else "falling" if not np.isnan(obv_sma[-1]) else "neutral",
        }

    def _compute_vwap(self) -> dict[str, Any]:
        """Volume Weighted Average Price (session VWAP)."""
        if len(self.df) < 2:
            return {}

        # Simple VWAP for the dataset
        typical_price = (self.df["high"] + self.df["low"] + self.df["close"]) / 3
        vwap = (typical_price * self.df["volume"]).cumsum() / self.df["volume"].cumsum()

        return {
            "vwap": vwap.iloc[-1] if not np.isnan(vwap.iloc[-1]) else None,
            "price_vs_vwap": "above" if self.df["close"].iloc[-1] > vwap.iloc[-1] else "below",
        }

    # ===== Pattern Detection =====
    def detect_patterns(self, patterns: list[str] | None = None) -> list[dict[str, Any]]:
        """Detect chart patterns."""
        if self.df.empty:
            return []

        patterns = patterns or [
            "orb", "flag", "rsi_div", "ma_reclaim",
            "bb_squeeze", "volume_spike", "gap",
        ]

        detected = []
        for pattern in patterns:
            try:
                method = getattr(self, f"_detect_{pattern}", None)
                if method:
                    result = method()
                    if result:
                        detected.append(result)
            except Exception as e:
                logger.debug(f"Pattern {pattern} detection failed: {e}")

        return detected

    def _detect_orb(self) -> dict[str, Any] | None:
        """Opening Range Breakout (adapted from day-trader-skill)."""
        # Need 15min candles for ORB
        if len(self.df) < 30:
            return None

        # Check first 15min range (first 3 5m bars or first 15m bar)
        # Simplified: use first 15min of day
        # In practice, would resample to 15min and check first bar of day
        return {
            "pattern": "orb",
            "direction": "long",  # Would determine from actual breakout
            "confidence": 0.6,
            "details": "ORB detection requires intraday session data",
        }

    def _detect_flag(self) -> dict[str, Any] | None:
        """Bull/Bear flag pattern."""
        if len(self.df) < 20:
            return None

        # Simplified: look for sharp move followed by consolidation
        close = self.df["close"].values
        returns = np.diff(np.log(close))

        # Look for large move (>2% in 3 bars) followed by small range
        for i in range(3, len(returns) - 5):
            move = returns[i - 3:i].sum()
            if abs(move) > 0.02:
                consolidation_range = returns[i:i + 5].max() - returns[i:i + 5].min()
                if consolidation_range < abs(move) * 0.5:
                    return {
                        "pattern": "flag",
                        "direction": "long" if move > 0 else "short",
                        "confidence": 0.65,
                        "pole_size_pct": move * 100,
                        "consolidation_pct": consolidation_range * 100,
                    }

        return None

    def _detect_rsi_div(self) -> dict[str, Any] | None:
        """RSI Divergence."""
        if len(self.df) < 30:
            return None

        # Get RSI
        rsi = talib.RSI(self.df["close"].values, timeperiod=14)
        if np.isnan(rsi[-1]):
            return None

        close = self.df["close"].values

        # Look for divergence in last 20 bars
        # Bullish: price lower low, RSI higher low
        # Bearish: price higher high, RSI lower high
        lookback = min(20, len(rsi) - 1)
        recent_rsi = rsi[-lookback:]
        recent_close = close[-lookback:]

        price_low_idx = np.argmin(recent_close)
        price_high_idx = np.argmax(recent_close)
        rsi_low_idx = np.argmin(recent_rsi)
        rsi_high_idx = np.argmax(recent_rsi)

        # Bullish divergence
        if price_low_idx != rsi_low_idx and price_low_idx < rsi_low_idx:
            return {
                "pattern": "rsi_divergence",
                "type": "bullish",
                "direction": "long",
                "confidence": 0.7,
                "price_low": recent_close[price_low_idx],
                "rsi_at_price_low": recent_rsi[price_low_idx],
                "rsi_low": recent_rsi[rsi_low_idx],
            }

        # Bearish divergence
        if price_high_idx != rsi_high_idx and price_high_idx < rsi_high_idx:
            return {
                "pattern": "rsi_divergence",
                "type": "bearish",
                "direction": "short",
                "confidence": 0.7,
                "price_high": recent_close[price_high_idx],
                "rsi_at_price_high": recent_rsi[price_high_idx],
                "rsi_high": recent_rsi[rsi_high_idx],
            }

        return None

    def _detect_ma_reclaim(self) -> dict[str, Any] | None:
        """Moving Average Reclaim (adapted from day-trader-skill)."""
        if len(self.df) < 50:
            return None

        # Check reclaim of 20 and 50 EMA
        ema_20 = talib.EMA(self.df["close"].values, timeperiod=20)
        ema_50 = talib.EMA(self.df["close"].values, timeperiod=50)

        if np.isnan(ema_20[-1]) or np.isnan(ema_50[-1]):
            return None

        close = self.df["close"].iloc[-1]
        prev_close = self.df["close"].iloc[-2]

        # Reclaim 20 EMA
        if prev_close < ema_20[-2] and close > ema_20[-1]:
            return {
                "pattern": "ma_reclaim",
                "ma": "ema_20",
                "direction": "long",
                "confidence": 0.7,
                "price": close,
                "ma_value": ema_20[-1],
            }

        # Reclaim 50 EMA
        if prev_close < ema_50[-2] and close > ema_50[-1]:
            return {
                "pattern": "ma_reclaim",
                "ma": "ema_50",
                "direction": "long",
                "confidence": 0.75,
                "price": close,
                "ma_value": ema_50[-1],
            }

        return None

    def _detect_bb_squeeze(self) -> dict[str, Any] | None:
        """Bollinger Band Squeeze."""
        if len(self.df) < 20:
            return None

        upper, middle, lower = talib.BBANDS(self.df["close"].values, timeperiod=20, nbdevup=2, nbdevdn=2)
        bb_width = (upper - lower) / middle * 100

        # Check if width is at 6-month low
        if len(bb_width) >= 100:
            min_width = np.nanmin(bb_width[-100:])
            current_width = bb_width[-1]

            if current_width <= min_width * 1.1:
                return {
                    "pattern": "bb_squeeze",
                    "direction": "neutral",  # Direction unknown until breakout
                    "confidence": 0.8,
                    "bb_width_pct": current_width,
                    "min_width_pct": min_width,
                }

        return None

    def _detect_volume_spike(self) -> dict[str, Any] | None:
        """Volume Spike detection."""
        if len(self.df) < 20:
            return None

        volume = self.df["volume"].values
        avg_volume = talib.SMA(volume, timeperiod=20)

        if np.isnan(avg_volume[-1]) or avg_volume[-1] == 0:
            return None

        volume_ratio = volume[-1] / avg_volume[-1]

        if volume_ratio > 3.0:
            return {
                "pattern": "volume_spike",
                "direction": "long" if self.df["close"].iloc[-1] > self.df["open"].iloc[-1] else "short",
                "confidence": min(volume_ratio / 10, 0.9),
                "volume_ratio": volume_ratio,
            }

        return None

    def _detect_gap(self) -> dict[str, Any] | None:
        """Gap detection (for futures/crypto with 24/7, less relevant)."""
        if len(self.df) < 2:
            return None

        prev_close = self.df["close"].iloc[-2]
        curr_open = self.df["open"].iloc[-1]

        gap_pct = (curr_open - prev_close) / prev_close * 100

        if abs(gap_pct) > 1.0:  # 1% gap
            return {
                "pattern": "gap",
                "direction": "long" if gap_pct > 0 else "short",
                "confidence": 0.6,
                "gap_pct": gap_pct,
            }

        return None


def compute_signals(indicators: dict, patterns: list) -> list[dict[str, Any]]:
    """Generate signals from indicators and patterns."""
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

    # RSI extremes
    rsi = indicators.get("rsi")
    if rsi:
        if rsi < 25:
            signals.append({
                "type": "mean_reversion",
                "direction": "long",
                "strength": (25 - rsi) / 25 * 0.5,
                "reason": f"RSI deeply oversold ({rsi:.1f})",
            })
        elif rsi > 75:
            signals.append({
                "type": "mean_reversion",
                "direction": "short",
                "strength": (rsi - 75) / 25 * 0.5,
                "reason": f"RSI deeply overbought ({rsi:.1f})",
            })

    # MACD cross
    macd = indicators.get("macd")
    if macd and macd.get("signal_cross") != "none":
        signals.append({
            "type": "macd_cross",
            "direction": "long" if macd["signal_cross"] == "bullish" else "short",
            "strength": 0.6,
            "reason": f"MACD {macd['signal_cross']} cross",
        })

    # Pattern signals
    for pattern in patterns:
        if pattern.get("confidence", 0) > 0.6:
            signals.append({
                "type": f"pattern_{pattern['pattern']}",
                "direction": pattern.get("direction", "neutral"),
                "strength": pattern["confidence"],
                "reason": f"Pattern: {pattern['pattern']}",
            })

    return signals