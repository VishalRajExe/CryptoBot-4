"""
Risk management and position sizing.
Adapted from day-trader-sisk risk manager, hummingbot V2 risk controls, and Lean portfolio risk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from cryptobot.data.models import Symbol
from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


class RiskAction(str, Enum):
    """Risk check actions."""

    APPROVE = "approve"
    REDUCE = "reduce"
    REJECT = "reject"
    WARNING = "warning"


@dataclass
class RiskCheckResult:
    """Result of a risk check."""

    action: RiskAction
    reason: str
    original_size: float
    adjusted_size: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "original_size": self.original_size,
            "adjusted_size": self.adjusted_size,
            "metadata": self.metadata,
        }


@dataclass
class PositionRisk:
    """Risk metrics for a position."""

    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: float | None
    take_profit: float | None
    risk_reward: float | None
    max_adverse_excursion: float
    max_favorable_excursion: float
    holding_time: timedelta
    var_95: float  # Value at Risk 95%
    var_99: float  # Value at Risk 99%


class PositionSizer:
    """
    Position sizing algorithms.

    Methods:
    - fixed_fractional: Fixed fraction of equity
    - kelly: Kelly criterion
    - vol_target: Volatility targeting
    - risk_parity: Risk parity allocation
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.default_method = self.config.get("method", "vol_target")
        self.max_fraction = self.config.get("max_fraction", 0.10)
        self.min_fraction = self.config.get("min_fraction", 0.005)

    def calculate_size(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        method: str | None = None,
        **kwargs,
    ) -> float:
        """
        Calculate position size.

        Args:
            equity: Account equity
            entry_price: Entry price
            stop_loss: Stop loss price
            method: Sizing method
            **kwargs: Method-specific parameters

        Returns:
            Position size in base currency
        """
        method = method or self.default_method
        risk_per_trade = kwargs.get("risk_per_trade", 0.01)  # 1% default

        if method == "fixed_fractional":
            return self._fixed_fractional(equity, entry_price, stop_loss, risk_per_trade)
        elif method == "kelly":
            return self._kelly(equity, entry_price, stop_loss, **kwargs)
        elif method == "vol_target":
            return self._vol_target(equity, entry_price, stop_loss, **kwargs)
        elif method == "risk_parity":
            return self._risk_parity(equity, entry_price, stop_loss, **kwargs)

        return self._fixed_fractional(equity, entry_price, stop_loss, risk_per_trade)

    def _fixed_fractional(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        risk_per_trade: float,
    ) -> float:
        """Fixed fractional sizing."""
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return 0
        risk_amount = equity * risk_per_trade
        size = risk_amount / risk_per_share
        return min(size, equity * self.max_fraction / entry_price)

    def _kelly(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        win_rate: float = 0.55,
        avg_win_loss_ratio: float = 1.5,
        **kwargs,
    ) -> float:
        """Kelly criterion sizing."""
        kelly_fraction = win_rate - (1 - win_rate) / avg_win_loss_ratio
        kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25% Kelly

        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return 0

        risk_amount = equity * kelly_fraction
        size = risk_amount / risk_per_share
        return min(size, equity * self.max_fraction / entry_price)

    def _vol_target(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        target_daily_vol: float = 0.015,
        lookback_days: int = 30,
        **kwargs,
    ) -> float:
        """Volatility targeting."""
        # Would need historical volatility data
        # Simplified: use stop loss as vol proxy
        risk_per_share = abs(entry_price - stop_loss)
        daily_vol_estimate = risk_per_share / entry_price

        if daily_vol_estimate == 0:
            return 0

        target_fraction = target_daily_vol / daily_vol_estimate
        target_fraction = max(self.min_fraction, min(target_fraction, self.max_fraction))

        risk_amount = equity * target_fraction
        size = risk_amount / risk_per_share
        return size

    def _risk_parity(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        **kwargs,
    ) -> float:
        """Risk parity (simplified - equal risk contribution)."""
        # For single asset, same as vol_target
        return self._vol_target(equity, entry_price, stop_loss, **kwargs)


class RiskManager:
    """
    Comprehensive risk manager with pre-trade and intra-trade checks.

    Checks:
    - Position size limits
    - Portfolio concentration
    - Correlation limits
    - Drawdown controls
    - Leverage limits
    - Daily/weekly/monthly loss limits
    - Circuit breakers
    - Margin requirements
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.position_sizer = PositionSizer(self.config.get("position_sizing", {}))

        # Load risk limits from config
        self.max_position_pct = self.config.get("max_position_pct", 0.10)
        self.max_portfolio_pct = self.config.get("max_portfolio_pct", 0.80)
        self.max_daily_loss_pct = self.config.get("max_daily_loss_pct", 0.05)
        self.max_drawdown_pct = self.config.get("max_drawdown_pct", 0.15)
        self.max_leverage = self.config.get("max_leverage", 3.0)
        self.max_correlation = self.config.get("max_correlation", 0.70)
        self.min_risk_reward = self.config.get("min_risk_reward", 1.5)

        # State tracking
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
        self.peak_equity = 0.0
        self.current_drawdown = 0.0
        self.last_reset_day = datetime.utcnow().date()

        # Position tracking
        self.positions: dict[str, PositionRisk] = {}
        self.pending_orders: dict[str, Any] = {}

    def check_pre_trade(
        self,
        symbol: str,
        action: str,  # buy, sell
        size: float,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        portfolio: dict[str, Any] | None = None,
    ) -> RiskCheckResult:
        """
        Pre-trade risk check.

        Args:
            symbol: Trading symbol
            action: "buy" or "sell"
            size: Position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            portfolio: Current portfolio state

        Returns:
            RiskCheckResult with approval/rejection
        """
        equity = portfolio.get("equity", 0) if portfolio else 0
        current_positions = portfolio.get("positions", {}) if portfolio else {}

        # Reset daily counters if new day
        self._reset_daily_counters()

        # 1. Check position size limit
        position_value = size * entry_price
        position_pct = position_value / equity if equity > 0 else 1.0

        if position_pct > self.max_position_pct:
            return RiskCheckResult(
                action=RiskAction.REJECT,
                reason=f"Position size {position_pct:.2%} exceeds limit {self.max_position_pct:.2%}",
                original_size=size,
                adjusted_size=0,
                metadata={"limit": "max_position_pct", "value": position_pct},
            )

        # 2. Check portfolio concentration
        total_exposed = sum(p.get("value", 0) for p in current_positions.values())
        new_total = total_exposed + position_value
        portfolio_pct = new_total / equity if equity > 0 else 1.0

        if portfolio_pct > self.max_portfolio_pct:
            return RiskCheckResult(
                action=RiskAction.REDUCE,
                reason=f"Portfolio exposure {portfolio_pct:.2%} would exceed limit {self.max_portfolio_pct:.2%}",
                original_size=size,
                adjusted_size=max(0, (equity * self.max_portfolio_pct - total_exposed) / entry_price),
                metadata={"limit": "max_portfolio_pct", "current": portfolio_pct},
            )

        # 3. Check leverage
        if portfolio_pct > self.max_leverage:
            return RiskCheckResult(
                action=RiskAction.REDUCE,
                reason=f"Leverage {portfolio_pct:.2f}x exceeds limit {self.max_leverage:.2f}x",
                original_size=size,
                adjusted_size=size * (self.max_leverage / portfolio_pct),
                metadata={"limit": "max_leverage", "current": portfolio_pct},
            )

        # 4. Check risk-reward
        if stop_loss and take_profit:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            if risk > 0:
                rr = reward / risk
                if rr < self.min_risk_reward:
                    return RiskCheckResult(
                        action=RiskAction.REJECT,
                        reason=f"Risk-reward {rr:.2f} below minimum {self.min_risk_reward}",
                        original_size=size,
                        adjusted_size=0,
                        metadata={"limit": "min_risk_reward", "rr": rr},
                    )

        # 5. Check daily loss limit
        if self.daily_pnl < -equity * self.max_daily_loss_pct:
            return RiskCheckResult(
                action=RiskAction.REJECT,
                reason=f"Daily loss limit reached: {self.daily_pnl/equity:.2%}",
                original_size=size,
                adjusted_size=0,
                metadata={"limit": "daily_loss", "pnl_pct": self.daily_pnl/equity},
            )

        # 6. Check max drawdown
        if self.current_drawdown > self.max_drawdown_pct:
            return RiskCheckResult(
                action=RiskAction.REDUCE,
                reason=f"Max drawdown exceeded: {self.current_drawdown:.2%}",
                original_size=size,
                adjusted_size=size * 0.5,  # Reduce by 50%
                metadata={"limit": "max_drawdown", "dd": self.current_drawdown},
            )

        # 7. Check correlation with existing positions
        if current_positions:
            corr_check = self._check_correlation(symbol, current_positions)
            if not corr_check["passed"]:
                return RiskCheckResult(
                    action=RiskAction.REDUCE,
                    reason=f"High correlation with {corr_check['correlated_symbol']}: {corr_check['correlation']:.2f}",
                    original_size=size,
                    adjusted_size=size * 0.5,
                    metadata={"limit": "correlation", **corr_check},
                )

        # 8. Position sizing validation
        if stop_loss:
            suggested_size = self.position_sizer.calculate_size(
                equity=equity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                method=self.config.get("position_sizing", {}).get("method", "vol_target"),
            )
            if size > suggested_size * 1.5:
                return RiskCheckResult(
                    action=RiskAction.REDUCE,
                    reason=f"Position size exceeds suggested by 50%+",
                    original_size=size,
                    adjusted_size=suggested_size,
                    metadata={"limit": "position_sizing", "suggested": suggested_size},
                )

        return RiskCheckResult(
            action=RiskAction.APPROVE,
            reason="All risk checks passed",
            original_size=size,
            adjusted_size=size,
            metadata={},
        )

    def check_intra_trade(
        self,
        position: PositionRisk,
    ) -> RiskCheckResult:
        """
        Intra-trade risk check for existing position.

        Args:
            position: Current position risk metrics

        Returns:
            RiskCheckResult with action
        """
        # Check stop loss
        if position.stop_loss:
            if position.current_price <= position.stop_loss and position.size > 0:
                return RiskCheckResult(
                    action=RiskAction.APPROVE,  # Trigger stop
                    reason="Stop loss triggered",
                    original_size=position.size,
                    adjusted_size=0,
                    metadata={"trigger": "stop_loss"},
                )
            elif position.current_price >= position.stop_loss and position.size < 0:
                return RiskCheckResult(
                    action=RiskAction.APPROVE,
                    reason="Stop loss triggered (short)",
                    original_size=position.size,
                    adjusted_size=0,
                    metadata={"trigger": "stop_loss"},
                )

        # Check take profit
        if position.take_profit:
            if position.current_price >= position.take_profit and position.size > 0:
                return RiskCheckResult(
                    action=RiskAction.APPROVE,
                    reason="Take profit triggered",
                    original_size=position.size,
                    adjusted_size=0,
                    metadata={"trigger": "take_profit"},
                )
            elif position.current_price <= position.take_profit and position.size < 0:
                return RiskCheckResult(
                    action=RiskAction.APPROVE,
                    reason="Take profit triggered (short)",
                    original_size=position.size,
                    adjusted_size=0,
                    metadata={"trigger": "take_profit"},
                )

        # Check max adverse excursion
        if position.max_adverse_excursion > position.unrealized_pnl * 2:
            return RiskCheckResult(
                action=RiskAction.WARNING,
                reason="Max adverse excursion exceeded",
                original_size=position.size,
                adjusted_size=position.size,
                metadata={"mae": position.max_adverse_excursion},
            )

        # Check holding time
        max_hold = self.config.get("max_hold_hours", 72)
        if position.holding_time > timedelta(hours=max_hold):
            return RiskCheckResult(
                action=RiskAction.WARNING,
                reason=f"Position held for {position.holding_time}, max is {max_hold}h",
                original_size=position.size,
                adjusted_size=position.size,
                metadata={"holding_time": str(position.holding_time)},
            )

        return RiskCheckResult(
            action=RiskAction.APPROVE,
            reason="Intra-trade checks passed",
            original_size=position.size,
            adjusted_size=position.size,
            metadata={},
        )

    def update_position(
        self,
        symbol: str,
        size: float,
        entry_price: float,
        current_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        """Update position tracking."""
        if size == 0:
            self.positions.pop(symbol, None)
            return

        pnl = (current_price - entry_price) * size
        pnl_pct = pnl / (entry_price * abs(size)) if entry_price != 0 else 0

        # Calculate MAE/MFE
        # Would need tick data - simplified
        mae = min(0, pnl_pct)
        mfe = max(0, pnl_pct)

        self.positions[symbol] = PositionRisk(
            symbol=symbol,
            size=size,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=None,
            max_adverse_excursion=mae,
            max_favorable_excursion=mfe,
            holding_time=timedelta(0),  # Would track from entry
            var_95=0,
            var_99=0,
        )

    def update_pnl(self, realized_pnl: float, equity: float) -> None:
        """Update PnL tracking."""
        self._reset_daily_counters()

        self.daily_pnl += realized_pnl
        self.weekly_pnl += realized_pnl
        self.monthly_pnl += realized_pnl

        # Update peak equity and drawdown
        if equity > self.peak_equity:
            self.peak_equity = equity
        if self.peak_equity > 0:
            self.current_drawdown = (self.peak_equity - equity) / self.peak_equity

    def _reset_daily_counters(self) -> None:
        """Reset daily/weekly/monthly counters."""
        today = datetime.utcnow().date()
        if today != self.last_reset_day:
            # Check if new week
            if today.weekday() == 0 and self.last_reset_day.weekday() != 0:
                self.weekly_pnl = 0
            # Check if new month
            if today.day == 1:
                self.monthly_pnl = 0
            self.daily_pnl = 0
            self.last_reset_day = today

    def _check_correlation(
        self,
        symbol: str,
        current_positions: dict[str, Any],
    ) -> dict[str, Any]:
        """Check correlation with existing positions."""
        # Simplified - would need historical returns
        # For now, check if same base asset
        base = symbol.split("/")[0].split(":")[0].upper()

        for pos_symbol in current_positions:
            pos_base = pos_symbol.split("/")[0].split(":")[0].upper()
            if pos_base == base:
                return {
                    "passed": False,
                    "correlated_symbol": pos_symbol,
                    "correlation": 1.0,
                }

        return {"passed": True}

    def get_portfolio_risk(self, portfolio: dict[str, Any]) -> dict[str, Any]:
        """Get portfolio-level risk metrics."""
        equity = portfolio.get("equity", 0)
        positions = portfolio.get("positions", {})

        total_exposure = sum(abs(p.get("size", 0) * p.get("entry_price", 0)) for p in positions.values())
        leverage = total_exposure / equity if equity > 0 else 0

        # Calculate portfolio VaR (simplified)
        returns = []
        for pos in positions.values():
            pos_return = pos.get("unrealized_pnl_pct", 0)
            weight = pos.get("size", 0) * pos.get("entry_price", 0) / total_exposure if total_exposure > 0 else 0
            returns.append(pos_return * weight)

        port_return = sum(returns) if returns else 0
        port_vol = np.std(returns) if len(returns) > 1 else 0

        var_95 = port_return - 1.65 * port_vol
        var_99 = port_return - 2.33 * port_vol

        return {
            "equity": equity,
            "total_exposure": total_exposure,
            "leverage": leverage,
            "daily_pnl": self.daily_pnl,
            "weekly_pnl": self.weekly_pnl,
            "monthly_pnl": self.monthly_pnl,
            "current_drawdown": self.current_drawdown,
            "peak_equity": self.peak_equity,
            "var_95": var_95 * equity,
            "var_99": var_99 * equity,
            "position_count": len(positions),
            "max_position_pct": max(
                (abs(p.get("size", 0) * p.get("entry_price", 0)) / equity if equity > 0 else 0)
                for p in positions.values()
            ) if positions else 0,
        }


class CircuitBreaker:
    """Circuit breaker for market anomalies."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.flash_crash_threshold = self.config.get("flash_crash_threshold_pct", 0.10)
        self.vol_spike_mult = self.config.get("vol_spike_mult", 3.0)
        self.spread_widen_mult = self.config.get("spread_widen_mult", 5.0)
        self.min_orderbook_depth = self.config.get("min_orderbook_depth_usd", 100000)

        self._normal_vol: dict[str, float] = {}
        self._normal_spread: dict[str, float] = {}
        self._triggered: dict[str, datetime] = {}
        self._cooldown = timedelta(seconds=self.config.get("cooldown_seconds", 60))

    def check(
        self,
        symbol: str,
        price_change_pct: float,
        current_vol: float,
        spread_bps: float,
        orderbook_depth: float,
    ) -> dict[str, Any]:
        """Check for circuit breaker conditions."""
        triggered = []

        # Flash crash
        if abs(price_change_pct) > self.flash_crash_threshold:
            triggered.append("flash_crash")

        # Volatility spike
        if symbol in self._normal_vol:
            if current_vol > self._normal_vol[symbol] * self.vol_spike_mult:
                triggered.append("vol_spike")

        # Spread widening
        if symbol in self._normal_spread:
            if spread_bps > self._normal_spread[symbol] * self.spread_widen_mult:
                triggered.append("spread_widen")

        # Liquidity check
        if orderbook_depth < self.min_orderbook_depth:
            triggered.append("low_liquidity")

        # Check cooldown
        if symbol in self._triggered:
            if datetime.utcnow() - self._triggered[symbol] < self._cooldown:
                return {"triggered": True, "reasons": ["cooldown"], "cooldown_remaining": self._cooldown}

        if triggered:
            self._triggered[symbol] = datetime.utcnow()
            return {"triggered": True, "reasons": triggered}

        # Update normal baselines
        self._normal_vol[symbol] = current_vol
        self._normal_spread[symbol] = spread_bps

        return {"triggered": False}


class KillSwitch:
    """Emergency kill switch."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.max_daily_loss_usd = self.config.get("max_daily_loss_usd", 5000)
        self.max_drawdown_usd = self.config.get("max_drawdown_usd", 15000)
        self.max_open_orders = self.config.get("max_open_orders", 100)
        self.max_api_errors_per_min = self.config.get("max_api_errors_per_min", 50)

        self.daily_loss_usd = 0.0
        self.api_errors = 0
        self.api_error_window_start = datetime.utcnow()
        self.triggered = False
        self.trigger_reason = ""

    def check(
        self,
        daily_pnl: float,
        current_drawdown_usd: float,
        open_orders: int,
        api_errors: int = 0,
    ) -> dict[str, Any]:
        """Check kill switch conditions."""
        if not self.enabled:
            return {"triggered": False}

        if self.triggered:
            return {"triggered": True, "reason": self.trigger_reason}

        if daily_pnl < -self.max_daily_loss_usd:
            self.triggered = True
            self.trigger_reason = f"Max daily loss exceeded: ${daily_pnl:.2f}"
            return {"triggered": True, "reason": self.trigger_reason}

        if current_drawdown_usd > self.max_drawdown_usd:
            self.triggered = True
            self.trigger_reason = f"Max drawdown exceeded: ${current_drawdown_usd:.2f}"
            return {"triggered": True, "reason": self.trigger_reason}

        if open_orders > self.max_open_orders:
            self.triggered = True
            self.trigger_reason = f"Too many open orders: {open_orders}"
            return {"triggered": True, "reason": self.trigger_reason}

        # API errors
        now = datetime.utcnow()
        if (now - self.api_error_window_start).seconds > 60:
            self.api_errors = 0
            self.api_error_window_start = now

        self.api_errors += api_errors
        if self.api_errors > self.max_api_errors_per_min:
            self.triggered = True
            self.trigger_reason = f"API error rate exceeded: {self.api_errors}/min"
            return {"triggered": True, "reason": self.trigger_reason}

        return {"triggered": False}

    def reset(self) -> None:
        """Reset kill switch (manual override)."""
        self.triggered = False
        self.trigger_reason = ""
        self.daily_loss_usd = 0.0
        self.api_errors = 0
        self.api_error_window_start = datetime.utcnow()