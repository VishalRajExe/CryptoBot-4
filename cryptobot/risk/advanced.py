"""
Advanced Risk Management Features.

Combines patterns from:
- freqtrade: PairLock / Cooldown, Trailing Stop Offset
- beebots: Monotonic Ratchet Stops, Volatility Circuit Breakers
- hummingbot: Triple-Barrier Protection (TP/SL/Time)
- day-trader-skill: Volume Anomaly Alerts
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from cryptobot.data.models import Symbol
from cryptobot.execution.adapters.base import Order, OrderSide, OrderStatus, OrderType
from cryptobot.risk.manager import PositionRisk

logger = logging.getLogger(__name__)


class CircuitBreakerType(str, Enum):
    """Types of circuit breakers."""

    FLASH_CRASH = "flash_crash"
    VOLATILITY_SPIKE = "volatility_spike"
    SPREAD_WIDENING = "spread_widening"
    LIQUIDITY_DRY_UP = "liquidity_dry_up"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"


@dataclass
class CircuitBreakerEvent:
    """Circuit breaker trigger event."""

    breaker_type: CircuitBreakerType
    symbol: str | None
    triggered_at: datetime
    value: float
    threshold: float
    action: str  # "pause", "reduce", "halt"
    metadata: dict[str, Any]


@dataclass
class PairLock:
    """Trading pair lock (from freqtrade)."""

    symbol: str
    reason: str
    locked_at: datetime
    unlock_at: datetime | None
    lock_type: str  # "cooldown", "stop_loss", "manual", "circuit_breaker"
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        if self.unlock_at is None:
            return True
        return datetime.utcnow() < self.unlock_at


@dataclass
class TrailingStopConfig:
    """Trailing stop configuration (freqtrade style)."""

    enabled: bool = True
    offset_pct: float = 0.02  # 2% trailing
    offset_price: float | None = None  # Absolute offset
    activation_pct: float = 0.01  # Activate after 1% profit
    ratchet: bool = True  # Only move in favor (beebots monotonic ratchet)
    callback_rate: float = 0.0  # Callback rate for ratchet


@dataclass
class TripleBarrierConfig:
    """Triple-barrier protection (hummingbot style)."""

    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None
    time_limit_bars: int | None = None
    trailing_stop: TrailingStopConfig | None = None

    # Order types for execution
    take_profit_order_type: str = "limit"
    stop_loss_order_type: str = "market"
    time_limit_order_type: str = "market"


class PairLockManager:
    """
    Manages trading pair locks and cooldowns.

    Features from freqtrade:
    - PairLock after stop loss hit
    - Cooldown periods
    - Manual lock/unlock
    - Auto-unlock on time expiry
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.locks: dict[str, PairLock] = {}
        self.default_cooldown = self.config.get("default_cooldown_minutes", 60)
        self.stop_loss_cooldown = self.config.get("stop_loss_cooldown_minutes", 120)
        self.max_locks_per_symbol = self.config.get("max_locks_per_symbol", 3)

    def lock(
        self,
        symbol: str,
        reason: str,
        duration_minutes: int | None = None,
        lock_type: str = "cooldown",
        metadata: dict[str, Any] | None = None,
    ) -> PairLock:
        """Apply a lock to a symbol."""
        now = datetime.utcnow()
        duration = duration_minutes or self.default_cooldown
        unlock_at = now + timedelta(minutes=duration)

        lock = PairLock(
            symbol=symbol,
            reason=reason,
            locked_at=now,
            unlock_at=unlock_at,
            lock_type=lock_type,
            metadata=metadata or {},
        )

        self.locks[symbol] = lock
        logger.info(f"Locked {symbol}: {reason} for {duration} minutes (type: {lock_type})")
        return lock

    def lock_after_stop_loss(self, symbol: str, metadata: dict[str, Any] | None = None) -> PairLock:
        """Apply stop loss cooldown lock (freqtrade pattern)."""
        return self.lock(
            symbol=symbol,
            reason="Stop loss triggered",
            duration_minutes=self.stop_loss_cooldown,
            lock_type="stop_loss",
            metadata=metadata,
        )

    def unlock(self, symbol: str) -> bool:
        """Manually unlock a symbol."""
        if symbol in self.locks:
            del self.locks[symbol]
            logger.info(f"Manually unlocked {symbol}")
            return True
        return False

    def is_locked(self, symbol: str) -> bool:
        """Check if symbol is currently locked."""
        lock = self.locks.get(symbol)
        if lock is None:
            return False
        if lock.is_active():
            return True
        else:
            # Auto-cleanup expired locks
            del self.locks[symbol]
            return False

    def get_lock(self, symbol: str) -> PairLock | None:
        """Get lock info for a symbol."""
        lock = self.locks.get(symbol)
        if lock and not lock.is_active():
            del self.locks[symbol]
            return None
        return lock

    def get_all_locks(self) -> dict[str, PairLock]:
        """Get all active locks."""
        # Cleanup expired
        expired = [s for s, l in self.locks.items() if not l.is_active()]
        for s in expired:
            del self.locks[s]
        return self.locks.copy()


class TrailingStopManager:
    """
    Advanced trailing stop management.

    Features:
    - freqtrade: Trailing Stop Offset (rides huge pumps)
    - beebots: Monotonic Ratchet Stops (locks in profits as candle spikes)
    - hummingbot: Triple-barrier integration
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.trailing_stops: dict[str, dict[str, Any]] = {}

    def initialize_trailing(
        self,
        symbol: str,
        entry_price: float,
        side: str,  # "long" or "short"
        config: TrailingStopConfig,
    ) -> None:
        """Initialize trailing stop for a position."""
        self.trailing_stops[symbol] = {
            "entry_price": entry_price,
            "side": side,
            "config": config,
            "highest_price": entry_price if side == "long" else None,
            "lowest_price": entry_price if side == "short" else None,
            "trailing_activated": False,
            "trailing_price": None,
            "last_update": datetime.utcnow(),
        }

    def update_price(self, symbol: str, current_price: float, current_high: float, current_low: float) -> dict[str, Any] | None:
        """
        Update trailing stop with new price data.

        Returns:
            dict with trailing stop info, or None if not triggered
        """
        stop = self.trailing_stops.get(symbol)
        if not stop:
            return None

        config: TrailingStopConfig = stop["config"]
        side = stop["side"]

        if side == "long":
            # Update highest price
            if current_high > (stop["highest_price"] or 0):
                stop["highest_price"] = current_high

            # Check activation
            profit_pct = (current_price - stop["entry_price"]) / stop["entry_price"]
            if not stop["trailing_activated"] and profit_pct >= config.activation_pct:
                stop["trailing_activated"] = True
                stop["trailing_price"] = current_high * (1 - config.offset_pct)
                logger.info(f"Trailing stop activated for {symbol} at {stop['trailing_price']:.4f}")

            # Update trailing price (monotonic ratchet - only moves up)
            if stop["trailing_activated"] and config.ratchet:
                new_trailing = current_high * (1 - config.offset_pct)
                if new_trailing > (stop["trailing_price"] or 0):
                    old = stop["trailing_price"]
                    stop["trailing_price"] = new_trailing
                    logger.debug(f"Trailing stop ratcheted up for {symbol}: {old:.4f} -> {new_trailing:.4f}")

            # Check stop hit
            if stop["trailing_activated"] and current_low <= (stop["trailing_price"] or float('inf')):
                return {
                    "triggered": True,
                    "stop_price": stop["trailing_price"],
                    "current_price": current_price,
                    "reason": "trailing_stop_hit",
                }

        else:  # short
            # Update lowest price
            if current_low < (stop["lowest_price"] or float('inf')):
                stop["lowest_price"] = current_low

            # Check activation
            profit_pct = (stop["entry_price"] - current_price) / stop["entry_price"]
            if not stop["trailing_activated"] and profit_pct >= config.activation_pct:
                stop["trailing_activated"] = True
                stop["trailing_price"] = current_low * (1 + config.offset_pct)
                logger.info(f"Trailing stop activated for {symbol} at {stop['trailing_price']:.4f}")

            # Update trailing price (monotonic ratchet - only moves down)
            if stop["trailing_activated"] and config.ratchet:
                new_trailing = current_low * (1 + config.offset_pct)
                if new_trailing < (stop["trailing_price"] or float('inf')):
                    old = stop["trailing_price"]
                    stop["trailing_price"] = new_trailing
                    logger.debug(f"Trailing stop ratcheted down for {symbol}: {old:.4f} -> {new_trailing:.4f}")

            # Check stop hit
            if stop["trailing_activated"] and current_high >= (stop["trailing_price"] or 0):
                return {
                    "triggered": True,
                    "stop_price": stop["trailing_price"],
                    "current_price": current_price,
                    "reason": "trailing_stop_hit",
                }

        stop["last_update"] = datetime.utcnow()
        return None

    def get_trailing_price(self, symbol: str) -> float | None:
        """Get current trailing stop price."""
        stop = self.trailing_stops.get(symbol)
        if stop and stop.get("trailing_activated"):
            return stop.get("trailing_price")
        return None

    def remove(self, symbol: str) -> None:
        """Remove trailing stop for symbol."""
        self.trailing_stops.pop(symbol, None)


class TripleBarrierManager:
    """
    Triple-barrier protection (hummingbot style).

    Three barriers:
    1. Take Profit - Exit with profit
    2. Stop Loss - Exit with limited loss
    3. Time Limit - Exit after max holding period
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.barriers: dict[str, dict[str, Any]] = {}

    def set_barriers(
        self,
        symbol: str,
        entry_price: float,
        side: str,
        quantity: float,
        config: TripleBarrierConfig,
    ) -> None:
        """Set up triple barriers for a position."""
        tp_price = None
        sl_price = None

        if config.take_profit_pct:
            if config.side == "long":
                tp_price = entry_price * (1 + config.take_profit_pct)
            else:
                tp_price = entry_price * (1 - config.take_profit_pct)

        if config.stop_loss_pct:
            if side == "long":
                sl_price = entry_price * (1 - config.stop_loss_pct)
            else:
                sl_price = entry_price * (1 + config.stop_loss_pct)

        self.barriers[symbol] = {
            "entry_price": entry_price,
            "side": side,
            "quantity": quantity,
            "config": config,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "start_time": datetime.utcnow(),
            "start_bar": 0,  # Would track bar count
            "tp_hit": False,
            "sl_hit": False,
            "time_hit": False,
        }

    def check_barriers(
        self,
        symbol: str,
        current_price: float,
        current_high: float,
        current_low: float,
        current_bar: int,
    ) -> dict[str, Any] | None:
        """
        Check if any barrier is hit.

        Returns:
            dict with hit info, or None if no barrier hit
        """
        barrier = self.barriers.get(symbol)
        if not barrier:
            return None

        config: TripleBarrierConfig = barrier["config"]
        side = barrier["side"]

        # Check Take Profit
        if barrier["tp_price"] and not barrier["tp_hit"]:
            if side == "long" and current_high >= barrier["tp_price"]:
                barrier["tp_hit"] = True
                return {"hit": "take_profit", "price": barrier["tp_price"], "reason": "take_profit_hit"}
            elif side == "short" and current_low <= barrier["tp_price"]:
                barrier["tp_hit"] = True
                return {"hit": "take_profit", "price": barrier["tp_price"], "reason": "take_profit_hit"}

        # Check Stop Loss
        if barrier["sl_price"] and not barrier["sl_hit"]:
            if side == "long" and current_low <= barrier["sl_price"]:
                barrier["sl_hit"] = True
                return {"hit": "stop_loss", "price": barrier["sl_price"], "reason": "stop_loss_hit"}
            elif side == "short" and current_high >= barrier["sl_price"]:
                barrier["sl_hit"] = True
                return {"hit": "stop_loss", "price": barrier["sl_price"], "reason": "stop_loss_hit"}

        # Check Time Limit
        if config.time_limit_bars and not barrier["time_hit"]:
            if current_bar >= barrier["start_bar"] + config.time_limit_bars:
                barrier["time_hit"] = True
                return {"hit": "time_limit", "price": None, "reason": "time_limit_reached"}

        return None

    def remove(self, symbol: str) -> None:
        """Remove barriers for symbol."""
        self.barriers.pop(symbol, None)


class VolatilityCircuitBreaker:
    """
    Volatility circuit breaker (beebots style).

    Halts new entries during extreme ATR spikes.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.atr_threshold_mult = self.config.get("atr_threshold_mult", 3.0)
        self.volume_spike_mult = self.config.get("volume_spike_mult", 5.0)
        self.spread_widen_mult = self.config.get("spread_widen_mult", 5.0)
        self.cooldown_minutes = self.config.get("cooldown_minutes", 30)

        self._normal_atr: dict[str, float] = {}
        self._normal_volume: dict[str, float] = {}
        self._normal_spread: dict[str, float] = {}
        self._triggered: dict[str, datetime] = {}
        self._cooldown_until: dict[str, datetime] = {}

    def update_baseline(self, symbol: str, atr: float, volume: float, spread_bps: float) -> None:
        """Update normal baseline values."""
        # Exponential moving average for baseline
        alpha = 0.1
        if symbol in self._normal_atr:
            self._normal_atr[symbol] = alpha * atr + (1 - alpha) * self._normal_atr[symbol]
            self._normal_volume[symbol] = alpha * volume + (1 - alpha) * self._normal_volume[symbol]
            self._normal_spread[symbol] = alpha * spread_bps + (1 - alpha) * self._normal_spread[symbol]
        else:
            self._normal_atr[symbol] = atr
            self._normal_volume[symbol] = volume
            self._normal_spread[symbol] = spread_bps

    def check(
        self,
        symbol: str,
        current_atr: float,
        current_volume: float,
        spread_bps: float,
    ) -> dict[str, Any] | None:
        """
        Check for circuit breaker conditions.

        Returns trigger info if triggered, None otherwise.
        """
        # Check cooldown
        if symbol in self._cooldown_until:
            if datetime.utcnow() < self._cooldown_until[symbol]:
                remaining = (self._cooldown_until[symbol] - datetime.utcnow()).total_seconds()
                return {
                    "triggered": True,
                    "type": "cooldown",
                    "remaining_seconds": remaining,
                }
            else:
                del self._cooldown_until[symbol]

        # Need baseline
        if symbol not in self._normal_atr:
            return None

        normal_atr = self._normal_atr[symbol]
        normal_volume = self._normal_volume[symbol]
        normal_spread = self._normal_spread[symbol]

        triggered = []
        reasons = []

        # ATR spike
        if current_atr > normal_atr * self.atr_threshold_mult:
            triggered.append("atr_spike")
            reasons.append(f"ATR {current_atr:.4f} > {normal_atr:.4f} * {self.atr_threshold_mult}")

        # Volume spike
        if current_volume > normal_volume * self.volume_spike_mult:
            triggered.append("volume_spike")
            reasons.append(f"Volume {current_volume} > {normal_volume} * {self.volume_spike_mult}")

        # Spread widening
        if normal_spread > 0 and current_spread > normal_spread * self.spread_widen_mult:
            triggered.append("spread_widening")
            reasons.append(f"Spread {current_spread:.1f}bps > {normal_spread:.1f} * {self.spread_widen_mult}")

        if triggered:
            # Set cooldown
            self._cooldown_until[symbol] = datetime.utcnow() + timedelta(minutes=self.cooldown_minutes)

            return {
                "triggered": True,
                "type": "volatility_circuit_breaker",
                "reasons": reasons,
                "cooldown_minutes": self.cooldown_minutes,
                "symbol": symbol,
            }

        return None

    def is_in_cooldown(self, symbol: str) -> bool:
        """Check if symbol is in cooldown."""
        if symbol in self._cooldown_until:
            return datetime.utcnow() < self._cooldown_until[symbol]
        return False


class CircuitBreakerManager:
    """
    Comprehensive circuit breaker manager.

    Combines:
    - Flash crash detection
    - Volatility spikes
    - Spread widening
    - Liquidity dry up
    - Correlation breakdown
    - Daily loss / drawdown limits
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

        # Flash crash
        self.flash_crash_threshold = self.config.get("flash_crash_threshold_pct", 0.10)  # 10%
        self.flash_crash_window = self.config.get("flash_crash_window_seconds", 60)

        # Daily limits
        self.max_daily_loss_pct = self.config.get("max_daily_loss_pct", 0.05)
        self.max_drawdown_pct = self.config.get("max_drawdown_pct", 0.15)

        # Volatility circuit breaker
        self.vol_breaker = VolatilityCircuitBreaker(config)

        # State
        self.daily_pnl = 0.0
        self.peak_equity = 0.0
        self.current_equity = 0.0
        self._triggered_breakers: dict[str, CircuitBreakerEvent] = {}
        self._cooldowns: dict[str, datetime] = {}

    def update_equity(self, equity: float, realized_pnl: float = 0.0) -> None:
        """Update equity tracking."""
        self.current_equity = equity
        self.daily_pnl += realized_pnl

        if equity > self.peak_equity:
            self.peak_equity = equity

    def check_all(
        self,
        symbol: str,
        price_change_pct: float,
        current_atr: float,
        current_volume: float,
        spread_bps: float,
        equity: float,
        realized_pnl: float = 0.0,
    ) -> list[CircuitBreakerEvent]:
        """
        Check all circuit breaker conditions.

        Returns list of triggered breakers.
        """
        self.update_equity(equity)
        triggered = []

        # Flash crash
        if abs(price_change_pct) > self.flash_crash_threshold:
            event = CircuitBreakerEvent(
                breaker_type=CircuitBreakerType.FLASH_CRASH,
                symbol=symbol,
                triggered_at=datetime.utcnow(),
                value=abs(price_change_pct),
                threshold=self.flash_crash_threshold,
                action="halt_new_entries",
                metadata={"price_change_pct": price_change_pct},
            )
            triggered.append(event)

        # Daily loss limit
        if self.current_equity > 0:
            daily_loss_pct = abs(self.daily_pnl) / self.current_equity
            if daily_loss_pct > self.max_daily_loss_pct:
                event = CircuitBreakerEvent(
                    breaker_type=CircuitBreakerType.DAILY_LOSS_LIMIT,
                    symbol=None,
                    triggered_at=datetime.utcnow(),
                    value=daily_loss_pct,
                    threshold=self.max_daily_loss_pct,
                    action="halt_all_trading",
                    metadata={"daily_pnl": self.daily_pnl},
                )
                triggered.append(event)

        # Max drawdown
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
            if drawdown > self.max_drawdown_pct:
                event = CircuitBreakerEvent(
                    breaker_type=CircuitBreakerType.DRAWDOWN_LIMIT,
                    symbol=None,
                    triggered_at=datetime.utcnow(),
                    value=drawdown,
                    threshold=self.max_drawdown_pct,
                    action="reduce_positions",
                    metadata={"drawdown_pct": drawdown},
                )
                triggered.append(event)

        # Volatility circuit breaker
        vol_result = self.vol_breaker.check(
            symbol,  # Need ATR, volume, spread from market data
            # These would come from market data
            0, 0, 0
        )
        if vol_result and vol_result.get("triggered"):
            event = CircuitBreakerEvent(
                breaker_type=CircuitBreakerType.VOLATILITY_SPIKE,
                symbol=symbol,
                triggered_at=datetime.utcnow(),
                value=0,
                threshold=0,
                action="halt_new_entries",
                metadata=vol_result,
            )
            triggered.append(event)

        # Store and apply cooldowns
        for event in triggered:
            self._triggered_breakers[event.breaker_type.value] = event
            self._cooldowns[event.breaker_type.value] = datetime.utcnow() + timedelta(minutes=30)

        return triggered

    def is_trading_halted(self) -> bool:
        """Check if any halt-all-trading breaker is active."""
        for event in self._triggered_breakers.values():
            if event.action == "halt_all_trading":
                # Check if cooldown expired
                if event.breaker_type.value in self._cooldowns:
                    if datetime.utcnow() > self._cooldowns[event.breaker_type.value]:
                        del self._cooldowns[event.breaker_type.value]
                        continue
                return True
        return False

    def is_symbol_halted(self, symbol: str) -> bool:
        """Check if new entries halted for symbol."""
        for event in self._triggered_breakers.values():
            if event.symbol == symbol and event.action in ("halt_new_entries", "halt_all_trading"):
                if event.breaker_type.value in self._cooldowns:
                    if datetime.utcnow() > self._cooldowns[event.breaker_type.value]:
                        del self._cooldowns[event.breaker_type.value]
                        continue
                return True
        return False

    def reset_daily(self) -> None:
        """Reset daily counters (call at day start)."""
        self.daily_pnl = 0.0
        self.peak_equity = self.current_equity


class AdvancedRiskManager:
    """
    Unified advanced risk manager combining all protection layers.

    Integrates:
    - PairLockManager (freqtrade)
    - TrailingStopManager (freqtrade/beebots)
    - TripleBarrierManager (hummingbot)
    - VolatilityCircuitBreaker (beebots)
    - CircuitBreakerManager (comprehensive)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

        self.pair_locks = PairLockManager(config.get("pair_locks", {}))
        self.trailing_stops = TrailingStopManager(config.get("trailing_stops", {}))
        self.triple_barriers = TripleBarrierManager(config.get("triple_barriers", {}))
        self.circuit_breakers = CircuitBreakerManager(config.get("circuit_breakers", {}))

        # Position tracking
        self.positions: dict[str, PositionRisk] = {}
        self.open_orders: dict[str, list] = defaultdict(list)

    def on_position_opened(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        trailing_config: TrailingStopConfig | None = None,
        triple_barrier_config: TripleBarrierConfig | None = None,
    ) -> None:
        """Call when a new position is opened."""
        # Initialize trailing stop
        if trailing_config:
            self.trailing_stops.initialize_trailing(symbol, entry_price, side, trailing_config)

        # Initialize triple barrier
        if triple_barrier_config:
            self.triple_barriers.set_barriers(symbol, entry_price, side, 1.0, triple_barrier_config)

    def on_price_update(
        self,
        symbol: str,
        current_price: float,
        current_high: float,
        current_low: float,
        current_bar: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Process price update and check all protections.

        Returns list of triggered actions.
        """
        actions = []

        # Check trailing stop
        trail_result = self.trailing_stops.update_price(symbol, current_price, current_high, current_low)
        if trail_result and trail_result.get("triggered"):
            actions.append({
                "action": "close_position",
                "symbol": symbol,
                "reason": "trailing_stop",
                "price": trail_result["stop_price"],
            })

        # Check triple barriers
        barrier_result = self.triple_barriers.check_barriers(symbol, current_price, current_high, current_low, 0)
        if barrier_result:
            actions.append({
                "action": "close_position",
                "symbol": symbol,
                "reason": barrier_result["reason"],
                "price": barrier_result.get("price"),
            })

        return actions

    def on_position_closed(self, symbol: str, pnl: float, stop_loss_hit: bool = False) -> None:
        """Call when position is closed."""
        # Apply pair lock after stop loss (freqtrade pattern)
        if stop_loss_hit:
            self.pair_locks.lock_after_stop_loss(symbol)

        # Clean up
        self.trailing_stops.remove(symbol)
        self.triple_barriers.remove(symbol)

    def check_pre_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        equity: float,
    ) -> dict[str, Any]:
        """
        Pre-trade risk check.

        Returns dict with action and adjusted size.
        """
        # Check circuit breakers
        cb_result = self.circuit_breakers.check_all(
            symbol=symbol,
            price_change_pct=0,
            current_atr=0,
            current_volume=0,
            spread_bps=0,
            equity=equity,
        )

        for event in cb_result:
            if event.action in ("halt_new_entries", "halt_all_trading"):
                return {
                    "action": "reject",
                    "reason": f"Circuit breaker: {event.breaker_type.value}",
                    "original_size": quantity,
                    "adjusted_size": 0,
                }

        # Check pair lock
        if self.pair_locks.is_locked(symbol):
            lock = self.pair_locks.get_lock(symbol)
            return {
                "action": "reject",
                "reason": f"Pair locked: {lock.reason}",
                "original_size": quantity,
                "adjusted_size": 0,
            }

        # Check symbol halted
        if self.circuit_breakers.is_symbol_halted(symbol):
            return {
                "action": "reject",
                "reason": "Symbol halted by circuit breaker",
                "original_size": quantity,
                "adjusted_size": 0,
            }

        return {
            "action": "approve",
            "reason": "All checks passed",
            "original_size": quantity,
            "adjusted_size": quantity,
        }

    def get_status(self) -> dict[str, Any]:
        """Get current risk manager status."""
        return {
            "pair_locks": {s: {"reason": l.reason, "type": l.lock_type} for s, l in self.pair_locks.get_all_locks().items()},
            "circuit_breakers": {
                "trading_halted": self.circuit_breakers.is_trading_halted(),
                "active_breakers": [e.breaker_type.value for e in self.circuit_breakers._triggered_breakers.values()],
            },
            "active_trailing_stops": list(self.trailing_stops.trailing_stops.keys()),
            "active_triple_barriers": list(self.triple_barriers.barriers.keys()),
        }