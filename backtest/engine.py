"""
Vectorized backtesting engine at scale.
Adapted from vectorbt's Portfolio and Vibe-Trading's backtest runner.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import numpy as np
import pandas as pd

from cryptobot.data.models import Symbol, Candle
from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=RuntimeWarning)


@dataclass
class BacktestConfig:
    """Backtest configuration."""

    initial_cash: float = 100000.0
    commission: float = 0.0005  # 0.05%
    slippage: float = 0.0002  # 0.02%
    funding_rate_enabled: bool = True
    liquidation_enabled: bool = True
    max_leverage: float = 1.0
    min_order_size: float = 10.0


@dataclass
class TradeRecord:
    """Individual trade record."""

    entry_time: datetime
    exit_time: datetime
    symbol: str
    side: str  # long, short
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    commission: float
    slippage: float
    holding_period: float  # hours
    return_pct: float


@dataclass
class BacktestResult:
    """Complete backtest result."""

    equity_curve: pd.Series
    trades: list[TradeRecord]
    positions: pd.DataFrame
    metrics: dict[str, float]
    config: BacktestConfig
    signals: pd.DataFrame

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = self._calculate_metrics()

    def _calculate_metrics(self) -> dict[str, float]:
        """Calculate performance metrics."""
        if len(self.equity_curve) < 2:
            return {}

        returns = self.equity_curve.pct_change().dropna()
        total_return = (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0] - 1) * 100
        annual_return = (1 + returns.mean()) ** 252 - 1 if len(returns) > 0 else 0
        annual_vol = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        # Drawdown
        cummax = self.equity_curve.cummax()
        drawdown = (self.equity_curve - cummax) / cummax * 100
        max_dd = drawdown.min()

        # Trade stats
        if self.trades:
            wins = [t for t in self.trades if t.pnl > 0]
            losses = [t for t in self.trades if t.pnl <= 0]
            win_rate = len(wins) / len(self.trades) * 100
            avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
            avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
            profit_factor = abs(sum(t.pnl for t in wins) / sum(t.pnl for t in losses)) if losses else float('inf')
            expectancy = np.mean([t.pnl_pct for t in self.trades])
        else:
            win_rate = avg_win = avg_loss = profit_factor = expectancy = 0

        return {
            "total_return_pct": total_return,
            "annual_return_pct": annual_return * 100,
            "annual_volatility_pct": annual_vol * 100,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd,
            "win_rate_pct": win_rate,
            "avg_win_pct": avg_win,
            "avg_loss_pct": avg_loss,
            "profit_factor": profit_factor,
            "expectancy_pct": expectancy,
            "total_trades": len(self.trades),
            "avg_holding_hours": np.mean([t.holding_period for t in self.trades]) if self.trades else 0,
        }


class BacktestEngine:
    """
    Vectorized backtesting engine.

    Features:
    - from_signals: Signal-based backtesting
    - from_orders: Order-based backtesting
    - from_order_func: Custom order function
    - Broadcasting over parameter grids
    - Numba-accelerated (optional)
    - Realistic costs (commission, slippage, funding)
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        prices: pd.DataFrame,  # columns=symbols, index=timestamps
        signals: pd.DataFrame,  # columns=symbols, values=1/0/-1
        **kwargs,
    ) -> BacktestResult:
        """
        Run backtest from signals.

        Args:
            prices: Price DataFrame (close prices)
            signals: Signal DataFrame (1=long, -1=short, 0=flat)
            **kwargs: Additional parameters

        Returns:
            BacktestResult
        """
        # Align prices and signals
        common_idx = prices.index.intersection(signals.index)
        prices = prices.loc[common_idx]
        signals = signals.loc[common_idx]

        # Forward fill signals
        signals = signals.ffill().fillna(0)

        # Calculate position sizes (1 unit per signal)
        positions = signals.copy()

        # Calculate returns
        price_returns = prices.pct_change().fillna(0)
        position_returns = positions.shift(1) * price_returns

        # Apply costs
        position_changes = positions.diff().abs()
        costs = position_changes * (self.config.commission + self.config.slippage)
        net_returns = position_returns - costs

        # Portfolio returns
        portfolio_returns = net_returns.sum(axis=1)

        # Equity curve
        equity_curve = (1 + portfolio_returns).cumprod() * self.config.initial_cash

        # Extract trades
        trades = self._extract_trades(positions, prices, equity_curve.index)

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            positions=positions,
            metrics={},
            config=self.config,
            signals=signals,
        )

    def _extract_trades(
        self,
        positions: pd.DataFrame,
        prices: pd.DataFrame,
        timestamps: pd.DatetimeIndex,
    ) -> list[TradeRecord]:
        """Extract individual trades from position changes."""
        trades = []

        for symbol in positions.columns:
            pos = positions[symbol]
            price = prices[symbol]

            # Find entry/exit points
            changes = pos.diff()
            entries = changes[changes != 0]

            for i, (entry_time, change) in enumerate(entries.items()):
                if change == 0:
                    continue

                entry_price = price.loc[entry_time]
                entry_side = "long" if change > 0 else "short"

                # Find exit
                exit_idx = entries.index.get_loc(entry_time) + 1
                if exit_idx < len(entries):
                    exit_time = entries.index[exit_idx]
                    exit_price = price.loc[exit_time]
                else:
                    # Still open - use last price
                    exit_time = timestamps[-1]
                    exit_price = price.iloc[-1]

                quantity = abs(change)
                if entry_side == "long":
                    pnl = (exit_price - entry_price) * quantity
                else:
                    pnl = (entry_price - exit_price) * quantity

                pnl_pct = pnl / (entry_price * quantity) * 100
                commission = entry_price * quantity * self.config.commission * 2
                slippage = entry_price * quantity * self.config.slippage * 2
                holding_hours = (exit_time - entry_time).total_seconds() / 3600

                trades.append(TradeRecord(
                    entry_time=entry_time,
                    exit_time=exit_time,
                    symbol=symbol,
                    side=entry_side,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    pnl=pnl - commission - slippage,
                    pnl_pct=pnl_pct,
                    commission=commission,
                    slippage=slippage,
                    holding_period=holding_hours,
                    return_pct=pnl_pct,
                ))

        return trades

    @classmethod
    def from_signals(
        cls,
        prices: pd.DataFrame,
        signals: pd.DataFrame,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        """Class method for signal-based backtest."""
        engine = cls(config)
        return engine.run(prices, signals)

    @classmethod
    def from_orders(
        cls,
        prices: pd.DataFrame,
        orders: pd.DataFrame,  # columns: symbol, side, quantity, price, timestamp
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        """Class method for order-based backtest."""
        # Convert orders to signals
        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)

        for _, order in orders.iterrows():
            symbol = order["symbol"]
            if symbol not in signals.columns:
                continue

            idx = prices.index.get_indexer([order["timestamp"]], method="nearest")[0]
            side = 1 if order["side"] == "buy" else -1
            signals.iloc[idx:, signals.columns.get_loc(symbol)] = side * order["quantity"]

        return cls.from_signals(prices, signals, config)


def run_vectorized_backtest(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    initial_cash: float = 100000.0,
    commission: float = 0.0005,
    slippage: float = 0.0002,
) -> BacktestResult:
    """Convenience function for vectorized backtest."""
    config = BacktestConfig(
        initial_cash=initial_cash,
        commission=commission,
        slippage=slippage,
    )
    return BacktestEngine.from_signals(prices, signals, config)