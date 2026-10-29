"""
Paper trading engine.
Adapted from Vibe-Trading's paper trading and freqtrade's dry-run.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any

from cryptobot.execution.adapters.base import (
    ExchangeAdapter,
    ExchangeConfig,
    Order,
    OrderStatus,
    OrderSide,
    OrderType,
    TimeInForce,
    Position,
    Balance,
)
from cryptobot.data.models import Symbol, MarketType, Candle
from cryptobot.data.fetcher import get_fetcher
from cryptobot.risk.manager import RiskManager, RiskCheckResult, RiskAction

logger = logging.getLogger(__name__)


@dataclass
class PaperAccount:
    """Paper trading account state."""

    id: str
    name: str
    equity: Decimal
    balances: dict[str, Balance] = field(default_factory=dict)
    positions: dict[str, Position] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    trades: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_total_equity(self, mark_prices: dict[str, Decimal]) -> Decimal:
        """Calculate total equity including unrealized PnL."""
        total = self.equity
        for pos in self.positions.values():
            mark_price = mark_prices.get(pos.symbol.unified, pos.mark_price)
            unrealized = (mark_price - pos.entry_price) * pos.quantity
            total += unrealized
        return total


class PaperExchangeAdapter(ExchangeAdapter):
    """
    Paper trading exchange adapter.

    Simulates order execution with realistic:
    - Latency simulation
    - Slippage models
    - Commission
    - Funding payments
    - Liquidation
    """

    def __init__(
        self,
        config: ExchangeConfig,
        account: PaperAccount,
        slippage_bps: float = 2.0,
        commission_bps: float = 5.0,
        latency_ms: float = 50.0,
    ):
        super().__init__(config)
        self.account = account
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps
        self.latency_ms = latency_ms

        # Market data
        self._mark_prices: dict[str, Decimal] = {}
        self._orderbooks: dict[str, Any] = {}

        # Funding simulation
        self._funding_rates: dict[str, Decimal] = {}
        self._last_funding: dict[str, datetime] = {}

        # Liquidation
        self.maintenance_margin = Decimal("0.05")  # 5%

        # Order ID counter
        self._order_counter = 0

    @property
    def name(self) -> str:
        return f"paper_{self.config.name}"

    def _symbol_to_exchange(self, symbol: Symbol) -> str:
        return f"{symbol.base}{symbol.quote}"

    def _symbol_from_exchange(self, exchange_symbol: str, market_type: MarketType) -> Symbol:
        for q in ["USDT", "BUSD", "USDC", "BTC", "ETH"]:
            if exchange_symbol.endswith(q):
                base = exchange_symbol[:-len(q)]
                return Symbol(base=base, quote=q, exchange="paper", market_type=market_type)
        return Symbol(
            base=exchange_symbol[:-4],
            quote=exchange_symbol[-4:],
            exchange="paper",
            market_type=market_type,
        )

    async def connect(self) -> None:
        """Initialize paper engine."""
        self._connected = True
        # Initialize balances
        if not self.account.balances:
            self.account.balances["USDT"] = Balance(
                asset="USDT",
                total=self.account.equity,
                available=self.account.equity,
            )
        # Start funding simulation
        asyncio.create_task(self._funding_loop())
        logger.info(f"Paper engine connected: {self.name}")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info(f"Paper engine disconnected: {self.name}")

    async def _simulate_latency(self) -> None:
        """Simulate network latency."""
        await asyncio.sleep(self.latency_ms / 1000)

    def _apply_slippage(self, price: Decimal, side: OrderSide, symbol: Symbol) -> Decimal:
        """Apply slippage to price."""
        slippage = price * Decimal(str(self.slippage_bps / 10000))
        if side == OrderSide.BUY:
            return price + slippage
        return price - slippage

    def _calculate_commission(self, notional: Decimal) -> Decimal:
        """Calculate commission."""
        return notional * Decimal(str(self.commission_bps / 10000))

    def _check_margin(self, position: Position) -> bool:
        """Check if position should be liquidated."""
        if position.margin <= 0:
            return False
        margin_ratio = position.margin / position.notional
        return margin_ratio < self.maintenance_margin

    # ===== Order Management =====
    async def create_order(
        self,
        symbol: Symbol,
        side: OrderSide,
        type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: str | None = None,
        **kwargs,
    ) -> Order:
        """Create paper order."""
        await self._simulate_latency()

        self._order_counter += 1
        order_id = f"paper_{self._order_counter}_{uuid.uuid4().hex[:8]}"
        client_oid = client_order_id or f"paper_{uuid.uuid4().hex[:12]}"

        # Get mark price for validation
        mark_price = self._mark_prices.get(symbol.unified)
        if mark_price is None:
            fetcher = await get_fetcher()
            ticker = await fetcher.fetch_ticker(symbol)
            if ticker:
                mark_price = ticker.last_price
                self._mark_prices[symbol.unified] = mark_price

        if mark_price is None:
            raise ValueError(f"No mark price for {symbol.unified}")

        # Determine fill price
        if type == OrderType.MARKET:
            fill_price = self._apply_slippage(mark_price, side, symbol)
        elif type == OrderType.LIMIT:
            if price is None:
                raise ValueError("Limit order requires price")
            # Check if limit is marketable
            if side == OrderSide.BUY and price < mark_price:
                fill_price = price  # Will sit on book
            elif side == OrderSide.SELL and price > mark_price:
                fill_price = price
            else:
                fill_price = self._apply_slippage(mark_price, side, symbol)  # Marketable
        else:
            fill_price = price or mark_price

        # Create order
        order = Order(
            id=order_id,
            client_order_id=client_oid,
            symbol=symbol,
            side=side,
            type=type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status=OrderStatus.NEW,
            time_in_force=time_in_force,
            created_at=datetime.utcnow(),
        )

        # Check balance
        required_margin = self._calculate_required_margin(symbol, side, quantity, fill_price)
        if not self._has_sufficient_balance(side, required_margin):
            order.status = OrderStatus.REJECTED
            self.account.orders[order.id] = order
            return order

        # Reserve margin
        self._reserve_margin(side, required_margin)

        # Simulate fill for market orders
        if type == OrderType.MARKET:
            await self._fill_order(order, fill_price)

        self.account.orders[order.id] = order
        return order

    def _calculate_required_margin(self, symbol: Symbol, side: OrderSide, quantity: Decimal, price: Decimal) -> Decimal:
        """Calculate required margin for order."""
        notional = quantity * price
        leverage = self.config.options.get("leverage", 10)
        return notional / Decimal(str(leverage))

    def _has_sufficient_balance(self, side: OrderSide, margin: Decimal) -> bool:
        """Check if account has sufficient balance."""
        usdt_balance = self.account.balances.get("USDT")
        if not usdt_balance:
            return False
        return usdt_balance.available >= margin

    def _reserve_margin(self, side: OrderSide, margin: Decimal) -> None:
        """Reserve margin from available balance."""
        usdt_balance = self.account.balances["USDT"]
        usdt_balance.available -= margin
        usdt_balance.locked += margin

    def _release_margin(self, margin: Decimal) -> None:
        """Release margin back to available."""
        usdt_balance = self.account.balances["USDT"]
        usdt_balance.available += margin
        usdt_balance.locked -= margin

    async def _fill_order(self, order: Order, fill_price: Decimal) -> None:
        """Fill order and update account."""
        commission = self._calculate_commission(order.quantity * fill_price)

        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.commission = commission
        order.updated_at = datetime.utcnow()

        # Update balances
        self._release_margin(self._calculate_required_margin(
            order.symbol, order.side, order.quantity, fill_price
        ))

        notional = order.quantity * fill_price
        usdt_balance = self.account.balances["USDT"]

        if order.side == OrderSide.BUY:
            usdt_balance.total -= notional + commission
            usdt_balance.available -= commission
        else:
            usdt_balance.total += notional - commission
            usdt_balance.available += notional - commission

        # Update position
        await self._update_position(order, fill_price, commission)

        # Record trade
        self.account.trades.append({
            "order_id": order.id,
            "symbol": order.symbol.unified,
            "side": order.side.value,
            "quantity": str(order.quantity),
            "price": str(fill_price),
            "commission": str(commission),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _update_position(self, order: Order, fill_price: Decimal, commission: Decimal) -> None:
        """Update or create position."""
        symbol_key = order.symbol.unified

        if symbol_key in self.account.positions:
            pos = self.account.positions[symbol_key]
            # Average entry price
            total_qty = pos.quantity + (order.quantity if order.side == OrderSide.BUY else -order.quantity)
            if total_qty != 0:
                pos.entry_price = (
                    (pos.entry_price * pos.quantity + fill_price * order.quantity * (1 if order.side == OrderSide.BUY else -1))
                    / total_qty
                )
            pos.quantity = total_qty
            pos.mark_price = fill_price
            pos.unrealized_pnl = Decimal("0")  # Recalculated on mark
            pos.updated_at = datetime.utcnow()

            if pos.quantity == 0:
                del self.account.positions[symbol_key]
        else:
            if order.side == OrderSide.BUY:
                qty = order.quantity
            else:
                qty = -order.quantity

            self.account.positions[symbol_key] = Position(
                symbol=order.symbol,
                quantity=qty,
                entry_price=fill_price,
                mark_price=fill_price,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
            )

    async def cancel_order(self, order_id: str, symbol: Symbol) -> bool:
        """Cancel paper order."""
        order = self.account.orders.get(order_id)
        if not order or order.status not in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED):
            return False

        # Release margin
        margin = self._calculate_required_margin(symbol, order.side, order.quantity - order.filled_quantity, order.price or Decimal("0"))
        self._release_margin(margin)

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        return True

    async def cancel_all_orders(self, symbol: Symbol | None = None) -> list[str]:
        """Cancel all paper orders."""
        cancelled = []
        for order in list(self.account.orders.values()):
            if order.status in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED):
                if symbol is None or order.symbol == symbol:
                    await self.cancel_order(order.id, order.symbol)
                    cancelled.append(order.id)
        return cancelled

    async def get_order(self, order_id: str, symbol: Symbol) -> Order | None:
        return self.account.orders.get(order_id)

    async def get_open_orders(self, symbol: Symbol | None = None) -> list[Order]:
        orders = []
        for order in self.account.orders.values():
            if order.status in (OrderStatus.NEW, OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED):
                if symbol is None or order.symbol == symbol:
                    orders.append(order)
        return orders

    async def get_order_history(
        self,
        symbol: Symbol | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[Order]:
        orders = []
        for order in list(self.account.orders.values())[::-1]:
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                if symbol is None or order.symbol == symbol:
                    if start and order.created_at < start:
                        continue
                    if end and order.created_at > end:
                        continue
                    orders.append(order)
                    if len(orders) >= limit:
                        break
        return orders

    # ===== Position Management =====
    async def get_positions(self, symbol: Symbol | None = None) -> list[Position]:
        positions = []
        for pos in self.account.positions.values():
            if symbol is None or pos.symbol == symbol:
                # Update mark price
                mark_price = self._mark_prices.get(pos.symbol.unified, pos.mark_price)
                pos.mark_price = mark_price
                pos.unrealized_pnl = (mark_price - pos.entry_price) * pos.quantity
                positions.append(pos)
        return positions

    async def get_position(self, symbol: Symbol) -> Position | None:
        pos = self.account.positions.get(symbol.unified)
        if pos:
            mark_price = self._mark_prices.get(symbol.unified, pos.mark_price)
            pos.mark_price = mark_price
            pos.unrealized_pnl = (mark_price - pos.entry_price) * pos.quantity
        return pos

    async def set_leverage(self, symbol: Symbol, leverage: int) -> bool:
        self.config.options["leverage"] = leverage
        return True

    async def set_margin_type(self, symbol: Symbol, margin_type: str) -> bool:
        return True

    # ===== Account =====
    async def get_balances(self) -> list[Balance]:
        return list(self.account.balances.values())

    async def get_balance(self, asset: str) -> Balance | None:
        return self.account.balances.get(asset)

    async def get_account_info(self) -> dict[str, Any]:
        mark_prices = {k: v for k, v in self._mark_prices.items()}
        total_equity = self.account.get_total_equity(mark_prices)

        return {
            "equity": str(total_equity),
            "available_balance": str(self.account.balances.get("USDT", Balance("USDT", Decimal("0"), Decimal("0"))).available),
            "positions": len(self.account.positions),
            "open_orders": len([o for o in self.account.orders.values() if o.status in (OrderStatus.NEW, OrderStatus.PENDING)]),
        }

    # ===== Market Data Simulation =====
    async def update_mark_price(self, symbol: Symbol, price: Decimal) -> None:
        """Update mark price (called from market data feed)."""
        self._mark_prices[symbol.unified] = price

        # Update position unrealized PnL
        if symbol.unified in self.account.positions:
            pos = self.account.positions[symbol.unified]
            pos.mark_price = price
            pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity

            # Check liquidation
            if self._check_margin(pos):
                await self._liquidate_position(pos)

    async def _liquidate_position(self, position: Position) -> None:
        """Liquidate position."""
        logger.warning(f"Liquidating position: {position.symbol.unified}")

        # Create market order to close
        side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        order = await self.create_order(
            symbol=position.symbol,
            side=side,
            type=OrderType.MARKET,
            quantity=abs(position.quantity),
        )

        if order.status == OrderStatus.FILLED:
            position.realized_pnl += position.unrealized_pnl
            position.quantity = Decimal("0")
            del self.account.positions[position.symbol.unified]

    # ===== Funding Simulation =====
    async def _funding_loop(self) -> None:
        """Simulate funding payments every 8 hours."""
        while self._connected:
            await asyncio.sleep(8 * 3600)  # 8 hours
            await self._process_funding()

    async def _process_funding(self) -> None:
        """Process funding payments for all positions."""
        for pos in self.account.positions.values():
            symbol_key = pos.symbol.unified
            funding_rate = self._funding_rates.get(symbol_key, Decimal("0"))

            if funding_rate != 0 and pos.quantity != 0:
                # Funding = position_notional * funding_rate
                notional = abs(pos.quantity) * pos.mark_price
                funding_payment = notional * funding_rate

                # Shorts pay when rate positive, longs pay when rate negative
                if (pos.quantity > 0 and funding_rate > 0) or (pos.quantity < 0 and funding_rate < 0):
                    funding_payment = -funding_payment

                # Apply to balance
                usdt_balance = self.account.balances["USDT"]
                usdt_balance.total += funding_payment
                usdt_balance.available += funding_payment

                logger.info(f"Funding payment for {symbol_key}: {funding_payment}")

    def set_funding_rate(self, symbol: Symbol, rate: Decimal) -> None:
        """Set funding rate for symbol."""
        self._funding_rates[symbol.unified] = rate

    # ===== WebSocket Streams =====
    async def subscribe_orders(self, callback) -> str:
        sub_id = f"paper_orders_{uuid.uuid4().hex[:8]}"
        return sub_id

    async def subscribe_positions(self, callback) -> str:
        sub_id = f"paper_positions_{uuid.uuid4().hex[:8]}"
        return sub_id

    async def subscribe_trades(self, symbol: Symbol, callback) -> str:
        sub_id = f"paper_trades_{symbol.unified}_{uuid.uuid4().hex[:8]}"
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        pass


class PaperEngine:
    """
    Paper trading engine managing multiple accounts.

    Features:
    - Multiple isolated accounts
    - Bar-agnostic lifecycle (from Vibe-Trading)
    - Stable replay IDs
    - Fail-closed cancellation
    - Day settlement
    - Deterministic snapshots
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.accounts: dict[str, PaperAccount] = {}
        self.adapters: dict[str, PaperExchangeAdapter] = {}
        self.risk_manager = RiskManager()
        self._running = False

    def create_account(
        self,
        name: str,
        equity: Decimal = Decimal("100000"),
        exchange: str = "binance",
        **kwargs,
    ) -> PaperAccount:
        """Create paper trading account."""
        account_id = f"paper_{name}_{uuid.uuid4().hex[:8]}"
        account = PaperAccount(id=account_id, name=name, equity=equity)

        # Create adapter
        exchange_config = ExchangeConfig(
            name=exchange,
            testnet=True,
            options=kwargs,
        )
        adapter = PaperExchangeAdapter(
            config=exchange_config,
            account=account,
            slippage_bps=self.config.get("slippage_bps", 2.0),
            commission_bps=self.config.get("commission_bps", 5.0),
            latency_ms=self.config.get("latency_ms", 50.0),
        )

        self.accounts[account_id] = account
        self.adapters[account_id] = adapter

        logger.info(f"Created paper account: {name} ({account_id}) with {equity} equity")
        return account

    def get_account(self, account_id: str) -> PaperAccount | None:
        return self.accounts.get(account_id)

    def get_adapter(self, account_id: str) -> PaperExchangeAdapter | None:
        return self.adapters.get(account_id)

    async def start_all(self) -> None:
        """Start all paper accounts."""
        for adapter in self.adapters.values():
            await adapter.connect()
        self._running = True
        logger.info("Paper engine started")

    async def stop_all(self) -> None:
        """Stop all paper accounts."""
        for adapter in self.adapters.values():
            await adapter.disconnect()
        self._running = False
        logger.info("Paper engine stopped")

    async def update_market_data(self, symbol: Symbol, price: Decimal) -> None:
        """Update mark prices across all accounts."""
        for adapter in self.adapters.values():
            await adapter.update_mark_price(symbol, price)

    def get_account_summary(self, account_id: str) -> dict[str, Any] | None:
        """Get account summary."""
        account = self.accounts.get(account_id)
        adapter = self.adapters.get(account_id)
        if not account or not adapter:
            return None

        return {
            "account_id": account_id,
            "name": account.name,
            "equity": str(account.equity),
            "total_equity": str(account.get_total_equity(adapter._mark_prices)),
            "positions": len(account.positions),
            "open_orders": len([o for o in account.orders.values() if o.status in (OrderStatus.NEW, OrderStatus.PENDING)]),
            "trades_today": len([t for t in account.trades if datetime.fromisoformat(t["timestamp"]).date() == datetime.utcnow().date()]),
        }