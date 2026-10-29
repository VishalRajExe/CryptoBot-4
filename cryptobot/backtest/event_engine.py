"""
Event-driven backtesting engine for production parity.
Adapted from NautilusTrader's backtest engine and backtesting.py's Strategy class.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

import numpy as np
import pandas as pd

from cryptobot.data.models import Candle, Symbol, OrderBook, Trade, MarketType
from cryptobot.execution.adapters.base import (
    Order,
    OrderStatus,
    OrderSide,
    OrderType,
    TimeInForce,
    Position,
)
from cryptobot.risk.manager import RiskManager

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types in the simulation."""

    BAR = "bar"
    TICK = "tick"
    ORDER = "order"
    FILL = "fill"
    FUNDING = "funding"
    LIQUIDATION = "liquidation"


@dataclass
class Event:
    """Simulation event."""

    type: EventType
    timestamp: datetime
    symbol: Symbol
    data: Any


class Strategy(ABC):
    """
    Base strategy class for event-driven backtesting.
    Adapted from backtesting.py's Strategy class.
    """

    def __init__(self, broker, data, params):
        self._broker = broker
        self._data = data
        self._params = params
        self._indicators = []

    def __repr__(self):
        params = ','.join(f'{k}={v}' for k, v in self._params.items())
        return f'{self.__class__.__name__}({params})'

    @abstractmethod
    def init(self) -> None:
        """Initialize strategy (called once at start)."""
        pass

    @abstractmethod
    def next(self) -> None:
        """Process next bar (called for each bar)."""
        pass

    def I(self, func: Callable, *args, name=None, plot=True, **kwargs) -> np.ndarray:
        """Declare indicator."""
        try:
            value = func(*args, **kwargs)
        except Exception as e:
            raise RuntimeError(f'Indicator "{name or func.__name__}" error: {e}')

        if isinstance(value, pd.DataFrame):
            value = value.values.T
        elif not isinstance(value, np.ndarray):
            value = np.array(value)

        self._indicators.append({
            "name": name or func.__name__,
            "values": value,
            "plot": plot,
        })
        return value

    def buy(
        self,
        size: float | None = None,
        limit: float | None = None,
        stop: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
    ) -> None:
        """Submit buy order."""
        self._broker.submit_order(
            side=OrderSide.BUY,
            size=size,
            limit=limit,
            stop=stop,
            sl=sl,
            tp=tp,
        )

    def sell(
        self,
        size: float | None = None,
        limit: float | None = None,
        stop: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
    ) -> None:
        """Submit sell order."""
        self._broker.submit_order(
            side=OrderSide.SELL,
            size=size,
            limit=limit,
            stop=stop,
            sl=sl,
            tp=tp,
        )

    def close(self) -> None:
        """Close all positions."""
        self._broker.close_all()


class SimulatedBroker:
    """
    Simulated broker for event-driven backtesting.

    Handles:
    - Order submission and management
    - Position tracking
    - Fill simulation with slippage/commission
    - Margin and liquidation
    """

    def __init__(
        self,
        data: pd.DataFrame,
        cash: float = 100000.0,
        commission: float = 0.0005,
        slippage: float = 0.0002,
        leverage: float = 1.0,
    ):
        self.data = data
        self.initial_cash = cash
        self.cash = cash
        self.commission = commission
        self.slippage = slippage
        self.leverage = leverage

        self.orders: dict[str, Order] = {}
        self.positions: dict[str, Position] = {}
        self.trades: list[dict] = []
        self.equity_curve: list[float] = [cash]

        # Pending orders
        self._pending_orders: list[Order] = []
        self._order_id_counter = 0

        # Strategy reference
        self.strategy: Strategy | None = None

    def submit_order(
        self,
        side: OrderSide,
        size: float | None = None,
        limit: float | None = None,
        stop: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
    ) -> Order:
        """Submit order to broker."""
        self._order_id_counter += 1
        order_id = f"sim_{self._order_id_counter}"

        # Determine order type
        if limit is not None and stop is not None:
            order_type = OrderType.STOP_LIMIT
        elif limit is not None:
            order_type = OrderType.LIMIT
        elif stop is not None:
            order_type = OrderType.STOP
        else:
            order_type = OrderType.MARKET

        # Get current symbol from strategy data
        symbol = getattr(self.strategy, "_current_symbol", None)
        if symbol is None:
            symbol = self.data.columns[0]

        order = Order(
            id=order_id,
            client_order_id=order_id,
            symbol=Symbol(base=symbol, quote="USDT", exchange="sim"),
            side=side,
            type=order_type,
            quantity=Decimal(str(size or 1)),
            price=Decimal(str(limit)) if limit else None,
            stop_price=Decimal(str(stop)) if stop else None,
            status=OrderStatus.PENDING,
        )

        self.orders[order_id] = order
        self._pending_orders.append(order)
        return order

    def close_all(self) -> None:
        """Close all open positions."""
        for symbol, position in list(self.positions.items()):
            if position.quantity > 0:
                self.submit_order(OrderSide.SELL, size=float(position.quantity))
            elif position.quantity < 0:
                self.submit_order(OrderSide.BUY, size=abs(float(position.quantity)))

    def process_bar(self, timestamp: datetime, symbol: Symbol, ohlcv: dict) -> None:
        """Process a new bar - check pending orders, update positions."""
        # Update mark price
        mark_price = Decimal(str(ohlcv["close"]))

        # Update position marks
        for pos in self.positions.values():
            if pos.symbol == symbol:
                pos.mark_price = mark_price
                pos.unrealized_pnl = (mark_price - pos.entry_price) * pos.quantity

        # Process pending orders
        self._process_pending_orders(timestamp, symbol, ohlcv)

        # Record equity
        equity = self.cash + sum(p.unrealized_pnl for p in self.positions.values())
        self.equity_curve.append(float(equity))

    def _process_pending_orders(
        self,
        timestamp: datetime,
        symbol: Symbol,
        ohlcv: dict,
    ) -> None:
        """Process pending orders against current bar."""
        high = Decimal(str(ohlcv["high"]))
        low = Decimal(str(ohlcv["low"]))
        open_price = Decimal(str(ohlcv["open"]))
        close = Decimal(str(ohlcv["close"]))

        filled_orders = []
        for order in self._pending_orders:
            if order.symbol != symbol:
                continue

            filled = False
            fill_price = None

            if order.type == OrderType.MARKET:
                # Market order fills at open (next bar) or close (same bar)
                fill_price = open_price * (1 + Decimal(str(self.slippage)) * (1 if order.side == OrderSide.BUY else -1))
                filled = True

            elif order.type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and order.price >= low:
                    fill_price = min(order.price, open_price)
                    filled = True
                elif order.side == OrderSide.SELL and order.price <= high:
                    fill_price = max(order.price, open_price)
                    filled = True

            elif order.type == OrderType.STOP:
                if order.side == OrderSide.BUY and order.stop_price <= high:
                    fill_price = max(order.stop_price, open_price)
                    filled = True
                elif order.side == OrderSide.SELL and order.stop_price >= low:
                    fill_price = min(order.stop_price, open_price)
                    filled = True

            elif order.type == OrderType.STOP_LIMIT:
                # Stop triggers, then limit
                if order.side == OrderSide.BUY and order.stop_price <= high:
                    if order.price >= low:
                        fill_price = min(order.price, max(order.stop_price, open_price))
                        filled = True
                elif order.side == OrderSide.SELL and order.stop_price >= low:
                    if order.price <= high:
                        fill_price = max(order.price, min(order.stop_price, open_price))
                        filled = True

            if filled:
                self._fill_order(order, fill_price, timestamp)
                filled_orders.append(order)

        # Remove filled orders
        for order in filled_orders:
            self._pending_orders.remove(order)

    def _fill_order(self, order: Order, fill_price: Decimal, timestamp: datetime) -> None:
        """Fill an order."""
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.updated_at = timestamp

        # Calculate commission
        notional = order.quantity * fill_price
        commission = notional * Decimal(str(self.commission))
        order.commission = commission

        # Update cash
        if order.side == OrderSide.BUY:
            cost = notional + commission
            self.cash -= cost
        else:
            proceeds = notional - commission
            self.cash += proceeds

        # Update position
        symbol_key = str(order.symbol)
        if symbol_key in self.positions:
            pos = self.positions[symbol_key]
            # Average entry
            total_qty = pos.quantity + (order.quantity if order.side == OrderSide.BUY else -order.quantity)
            if total_qty != 0:
                pos.entry_price = (
                    (pos.entry_price * pos.quantity + fill_price * order.quantity * (1 if order.side == OrderSide.BUY else -1))
                    / total_qty
                )
            pos.quantity = total_qty
            pos.mark_price = fill_price
            pos.unrealized_pnl = Decimal("0")
            pos.updated_at = timestamp

            if pos.quantity == 0:
                del self.positions[symbol_key]
        else:
            qty = order.quantity if order.side == OrderSide.BUY else -order.quantity
            self.positions[symbol_key] = Position(
                symbol=order.symbol,
                quantity=qty,
                entry_price=fill_price,
                mark_price=fill_price,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
            )

        # Record trade
        self.trades.append({
            "order_id": order.id,
            "symbol": symbol_key,
            "side": order.side.value,
            "quantity": float(order.quantity),
            "price": float(fill_price),
            "commission": float(commission),
            "timestamp": timestamp.isoformat(),
        })


class EventBacktestEngine:
    """
    Event-driven backtest engine.

    Runs strategy through historical data bar by bar,
    simulating realistic order execution.
    """

    def __init__(
        self,
        strategy_class: type[Strategy],
        data: pd.DataFrame,
        cash: float = 100000.0,
        commission: float = 0.0005,
        slippage: float = 0.0002,
        leverage: float = 1.0,
    ):
        self.strategy_class = strategy_class
        self.data = data
        self.cash = cash
        self.commission = commission
        self.slippage = slippage
        self.leverage = leverage

        self.broker: SimulatedBroker | None = None
        self.strategy: Strategy | None = None
        self.results: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        """Run the backtest."""
        # Initialize broker
        self.broker = SimulatedBroker(
            data=self.data,
            cash=self.cash,
            commission=self.commission,
            slippage=self.slippage,
            leverage=self.leverage,
        )

        # Initialize strategy
        self.strategy = self.strategy_class(
            broker=self.broker,
            data=self.data,
            params={},
        )
        self.broker.strategy = self.strategy

        # Call init
        self.strategy.init()

        # Run simulation
        timestamps = self.data.index
        symbols = self.data.columns.get_level_values(0).unique() if isinstance(self.data.columns, pd.MultiIndex) else [self.data.columns[0]]

        for i, timestamp in enumerate(timestamps):
            # Get data for all symbols at this timestamp
            for symbol in symbols:
                if isinstance(self.data.columns, pd.MultiIndex):
                    row = self.data.loc[timestamp, symbol]
                else:
                    row = self.data.loc[timestamp]

                ohlcv = {
                    "open": row["open"] if "open" in row else row.iloc[0],
                    "high": row["high"] if "high" in row else row.iloc[1],
                    "low": row["low"] if "low" in row else row.iloc[2],
                    "close": row["close"] if "close" in row else row.iloc[3],
                    "volume": row["volume"] if "volume" in row else row.iloc[4],
                }

                # Set current symbol for strategy
                self.strategy._current_symbol = symbol

                # Process bar
                self.broker.process_bar(timestamp, Symbol(base=symbol, quote="USDT", exchange="sim"), ohlcv)

                # Call strategy next()
                try:
                    self.strategy.next()
                except Exception as e:
                    logger.error(f"Strategy error at {timestamp}: {e}")

        # Finalize
        self._finalize()

        return self.results

    def _finalize(self) -> None:
        """Finalize backtest and compute results."""
        equity = pd.Series(self.broker.equity_curve, index=[self.data.index[0]] + list(self.data.index[1:]))

        returns = equity.pct_change().dropna()
        total_return = (equity.iloc[-1] / equity.iloc[0] - 1) * 100
        annual_return = (1 + returns.mean()) ** 252 - 1 if len(returns) > 0 else 0
        annual_vol = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax * 100
        max_dd = drawdown.min()

        self.results = {
            "equity_curve": equity,
            "trades": self.broker.trades,
            "orders": self.broker.orders,
            "positions": self.broker.positions,
            "metrics": {
                "total_return_pct": total_return,
                "annual_return_pct": annual_return * 100,
                "annual_volatility_pct": annual_vol * 100,
                "sharpe_ratio": sharpe,
                "max_drawdown_pct": max_dd,
                "total_trades": len(self.broker.trades),
            },
        }


def run_event_backtest(
    strategy_class: type[Strategy],
    data: pd.DataFrame,
    cash: float = 100000.0,
    commission: float = 0.0005,
    slippage: float = 0.0002,
) -> dict[str, Any]:
    """Convenience function for event-driven backtest."""
    engine = EventBacktestEngine(
        strategy_class=strategy_class,
        data=data,
        cash=cash,
        commission=commission,
        slippage=slippage,
    )
    return engine.run()