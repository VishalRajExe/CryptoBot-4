"""
Order Management System.
Adapted from Lean's TransactionHandlers and hummingbot's order executors.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from cryptobot.execution.adapters.base import (
    ExchangeAdapter,
    Order,
    OrderStatus,
    OrderSide,
    OrderType,
    TimeInForce,
    Position,
    exchange_adapter_registry,
)
from cryptobot.data.models import Symbol
from cryptobot.risk.manager import RiskManager, RiskCheckResult, RiskAction

logger = logging.getLogger(__name__)


class OMSState(str, Enum):
    """OMS state."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    EMERGENCY = "emergency"


@dataclass
class OrderRequest:
    """Order request from strategy."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: Symbol = None
    side: OrderSide = OrderSide.BUY
    type: OrderType = OrderType.MARKET
    quantity: Decimal = Decimal("0")
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    client_order_id: str | None = None
    strategy: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Risk check result
    risk_result: RiskCheckResult | None = None


@dataclass
class OrderTicket:
    """Internal order ticket tracking."""

    request: OrderRequest
    exchange_order: Order | None = None
    exchange: str = ""
    status: OrderStatus = OrderStatus.NEW
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    error: str | None = None


class OrderManager:
    """
    Order Management System.

    Features:
    - Multi-exchange order routing
    - Idempotency keys
    - Order state machine
    - Risk pre-checks
    - Order lifecycle callbacks
    - Retry logic
    - OCO/bracket order support
    """

    def __init__(
        self,
        risk_manager: RiskManager | None = None,
        config: dict[str, Any] | None = None,
    ):
        self.config = config or {}
        self.risk_manager = risk_manager or RiskManager()
        self.state = OMSState.RUNNING

        # Adapters
        self._adapters: dict[str, ExchangeAdapter] = {}

        # Order tracking
        self._tickets: dict[str, OrderTicket] = {}
        self._tickets_by_client_id: dict[str, str] = {}
        self._tickets_by_exchange_order: dict[str, str] = {}

        # Callbacks
        self._order_callbacks: list[Callable[[OrderTicket], Any]] = []
        self._trade_callbacks: list[Callable[[OrderTicket], Any]] = []

        # Retry config
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 1.0)
        self.order_timeout = self.config.get("order_timeout", 30)

    def add_adapter(self, name: str, adapter: ExchangeAdapter) -> None:
        """Add exchange adapter."""
        self._adapters[name] = adapter
        logger.info(f"Added exchange adapter: {name}")

    def get_adapter(self, name: str) -> ExchangeAdapter | None:
        """Get adapter by name."""
        return self._adapters.get(name)

    def set_default_exchange(self, name: str) -> None:
        """Set default exchange."""
        self.config["default_exchange"] = name

    # ===== Order Submission =====
    async def submit_order(self, request: OrderRequest) -> OrderTicket:
        """
        Submit order with risk checks.

        Args:
            request: Order request

        Returns:
            OrderTicket for tracking
        """
        if self.state != OMSState.RUNNING:
            raise RuntimeError(f"OMS not running: {self.state}")

        # Generate client order ID if not provided
        if not request.client_order_id:
            request.client_order_id = f"{request.strategy}_{request.request_id[:8]}"

        # Check idempotency
        if request.client_order_id in self._tickets_by_client_id:
            existing_id = self._tickets_by_client_id[request.client_order_id]
            logger.warning(f"Duplicate client_order_id: {request.client_order_id}")
            return self._tickets[existing_id]

        # Risk pre-check
        portfolio = self._get_portfolio_snapshot()
        risk_result = self.risk_manager.check_pre_trade(
            symbol=request.symbol.unified,
            action=request.side.value,
            size=float(request.quantity),
            entry_price=float(request.price or 0),
            stop_loss=float(request.stop_price) if request.stop_price else None,
            take_profit=None,
            portfolio=portfolio,
        )
        request.risk_result = risk_result

        if risk_result.action == RiskAction.REJECT:
            ticket = OrderTicket(
                request=request,
                status=OrderStatus.REJECTED,
                error=risk_result.reason,
            )
            self._store_ticket(ticket)
            self._notify_callbacks(ticket)
            return ticket

        # Adjust size if needed
        if risk_result.action == RiskAction.REDUCE:
            request.quantity = Decimal(str(risk_result.adjusted_size))
            logger.warning(f"Order size reduced: {risk_result.reason}")

        # Create ticket
        ticket = OrderTicket(request=request)
        self._store_ticket(ticket)

        # Submit to exchange
        asyncio.create_task(self._execute_order(ticket))

        return ticket

    async def _execute_order(self, ticket: OrderTicket) -> None:
        """Execute order on exchange."""
        request = ticket.request
        exchange_name = self.config.get("default_exchange", "binance")
        adapter = self._adapters.get(exchange_name)

        if not adapter:
            ticket.status = OrderStatus.REJECTED
            ticket.error = f"Exchange not available: {exchange_name}"
            self._update_ticket(ticket)
            return

        try:
            # Create order on exchange
            exchange_order = await asyncio.wait_for(
                adapter.create_order(
                    symbol=request.symbol,
                    side=request.side,
                    type=request.type,
                    quantity=request.quantity,
                    price=request.price,
                    stop_price=request.stop_price,
                    time_in_force=request.time_in_force,
                    client_order_id=request.client_order_id,
                ),
                timeout=self.order_timeout,
            )

            ticket.exchange_order = exchange_order
            ticket.exchange = exchange_name
            ticket.status = exchange_order.status
            self._update_ticket(ticket)

            # Track exchange order ID
            self._tickets_by_exchange_order[exchange_order.id] = ticket.request.request_id

            # Wait for fill if market order
            if request.type == OrderType.MARKET:
                await self._wait_for_fill(ticket)

        except asyncio.TimeoutError:
            ticket.status = OrderStatus.REJECTED
            ticket.error = "Order timeout"
            self._update_ticket(ticket)
            await self._handle_timeout(ticket)

        except Exception as e:
            logger.error(f"Order execution error: {e}")
            await self._handle_error(ticket, e)

    async def _wait_for_fill(self, ticket: OrderTicket, timeout: float = 30) -> None:
        """Wait for market order to fill."""
        start = datetime.utcnow()
        while (datetime.utcnow() - start).seconds < timeout:
            await asyncio.sleep(0.5)
            if ticket.exchange_order and ticket.exchange_order.is_terminal():
                break

    async def _handle_timeout(self, ticket: OrderTicket) -> None:
        """Handle order timeout."""
        # Try to cancel
        if ticket.exchange_order:
            adapter = self._adapters.get(ticket.exchange)
            if adapter:
                await adapter.cancel_order(ticket.exchange_order.id, ticket.request.symbol)

    async def _handle_error(self, ticket: OrderTicket, error: Exception) -> None:
        """Handle order error with retry."""
        ticket.retry_count += 1

        if ticket.retry_count < self.max_retries:
            await asyncio.sleep(self.retry_delay * ticket.retry_count)
            await self._execute_order(ticket)
        else:
            ticket.status = OrderStatus.REJECTED
            ticket.error = str(error)
            self._update_ticket(ticket)

    # ===== Order Management =====
    async def cancel_order(self, request_id: str) -> bool:
        """Cancel order by request ID."""
        ticket = self._tickets.get(request_id)
        if not ticket or not ticket.exchange_order:
            return False

        adapter = self._adapters.get(ticket.exchange)
        if not adapter:
            return False

        success = await adapter.cancel_order(
            ticket.exchange_order.id,
            ticket.request.symbol,
        )

        if success:
            ticket.status = OrderStatus.CANCELLED
            self._update_ticket(ticket)

        return success

    async def cancel_all_orders(self, symbol: Symbol | None = None) -> dict[str, list[str]]:
        """Cancel all orders across exchanges."""
        results = {}
        for name, adapter in self._adapters.items():
            cancelled = await adapter.cancel_all_orders(symbol)
            results[name] = cancelled
        return results

    def get_order(self, request_id: str) -> OrderTicket | None:
        """Get order ticket by request ID."""
        return self._tickets.get(request_id)

    def get_order_by_client_id(self, client_order_id: str) -> OrderTicket | None:
        """Get order ticket by client order ID."""
        request_id = self._tickets_by_client_id.get(client_order_id)
        return self._tickets.get(request_id) if request_id else None

    def get_open_orders(self, symbol: Symbol | None = None) -> list[OrderTicket]:
        """Get all open orders."""
        return [
            t for t in self._tickets.values()
            if t.status not in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED)
            and (symbol is None or t.request.symbol == symbol)
        ]

    # ===== Bracket/OCO Orders =====
    async def submit_bracket_order(
        self,
        symbol: Symbol,
        side: OrderSide,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        strategy: str = "",
    ) -> list[OrderTicket]:
        """Submit bracket order (entry + stop + target)."""
        tickets = []

        # Entry order
        entry_request = OrderRequest(
            symbol=symbol,
            side=side,
            type=OrderType.LIMIT,
            quantity=quantity,
            price=entry_price,
            strategy=strategy,
        )
        entry_ticket = await self.submit_order(entry_request)
        tickets.append(entry_ticket)

        # Wait for entry to fill
        while entry_ticket.status == OrderStatus.NEW or entry_ticket.status == OrderStatus.PENDING:
            await asyncio.sleep(0.5)
            if entry_ticket.status == OrderStatus.REJECTED:
                return tickets  # Entry failed

        if entry_ticket.status == OrderStatus.FILLED:
            # Submit stop loss
            stop_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
            stop_request = OrderRequest(
                symbol=symbol,
                side=stop_side,
                type=OrderType.STOP,
                quantity=quantity,
                stop_price=stop_loss,
                strategy=strategy,
                metadata={"bracket_entry_id": entry_ticket.request.request_id},
            )
            stop_ticket = await self.submit_order(stop_request)
            tickets.append(stop_ticket)

            # Submit take profit
            tp_request = OrderRequest(
                symbol=symbol,
                side=stop_side,
                type=OrderType.LIMIT,
                quantity=quantity,
                price=take_profit,
                strategy=strategy,
                metadata={"bracket_entry_id": entry_ticket.request.request_id},
            )
            tp_ticket = await self.submit_order(tp_request)
            tickets.append(tp_ticket)

        return tickets

    # ===== Callbacks =====
    def on_order_update(self, callback: Callable[[OrderTicket], Any]) -> None:
        """Register order update callback."""
        self._order_callbacks.append(callback)

    def on_trade(self, callback: Callable[[OrderTicket], Any]) -> None:
        """Register trade callback."""
        self._trade_callbacks.append(callback)

    def _notify_callbacks(self, ticket: OrderTicket) -> None:
        """Notify all callbacks."""
        for cb in self._order_callbacks:
            try:
                cb(ticket)
            except Exception as e:
                logger.error(f"Order callback error: {e}")

    # ===== Internal =====
    def _store_ticket(self, ticket: OrderTicket) -> None:
        """Store ticket in tracking maps."""
        self._tickets[ticket.request.request_id] = ticket
        if ticket.request.client_order_id:
            self._tickets_by_client_id[ticket.request.client_order_id] = ticket.request.request_id

    def _update_ticket(self, ticket: OrderTicket) -> None:
        """Update ticket and notify callbacks."""
        ticket.updated_at = datetime.utcnow()
        self._notify_callbacks(ticket)

    def _get_portfolio_snapshot(self) -> dict[str, Any]:
        """Get current portfolio snapshot for risk checks."""
        # Would aggregate from all adapters
        return {
            "equity": 100000,  # Placeholder
            "positions": {},
        }


class OrderRouter:
    """
    Smart order router for multi-exchange execution.

    Features:
    - Best price routing
    - Liquidity aggregation
    - Fee optimization
    - Latency awareness
    """

    def __init__(self, order_manager: OrderManager):
        self.oms = order_manager

    async def route_order(
        self,
        request: OrderRequest,
        strategy: str = "best_price",
    ) -> OrderTicket:
        """Route order to best exchange."""
        # For now, use default exchange
        # In production, would compare prices across exchanges
        return await self.oms.submit_order(request)


# Idempotency key generator
def generate_idempotency_key(strategy: str, symbol: Symbol, side: OrderSide, price: Decimal | None) -> str:
    """Generate idempotency key for order."""
    price_str = str(price) if price else "market"
    return f"{strategy}:{symbol.unified}:{side.value}:{price_str}:{uuid.uuid4().hex[:8]}"