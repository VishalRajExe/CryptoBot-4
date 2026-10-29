"""
Base exchange adapter protocol.
Adapted from hummingbot V2 controllers and NautilusTrader adapters.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from cryptobot.data.models import Symbol, OrderBook, Trade, Ticker, FundingRate, MarketType

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    """Order status."""

    NEW = "new"
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderSide(str, Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING = "trailing"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"


class TimeInForce(str, Enum):
    """Time in force."""

    GTC = "GTC"  # Good till cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill
    GTD = "GTD"  # Good till date
    DAY = "DAY"  # Day order
    AT_THE_OPEN = "AT_THE_OPEN"
    AT_THE_CLOSE = "AT_THE_CLOSE"


@dataclass
class Order:
    """Order representation."""

    id: str
    client_order_id: str
    symbol: Symbol
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    status: OrderStatus = OrderStatus.NEW
    time_in_force: TimeInForce = TimeInForce.GTC
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Decimal | None = None
    commission: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status in (OrderStatus.NEW, OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED)

    def is_terminal(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED)


@dataclass
class Position:
    """Position representation."""

    symbol: Symbol
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    leverage: Decimal = Decimal("1")
    margin: Decimal = Decimal("0")
    margin_type: str = "cross"
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def notional(self) -> Decimal:
        return abs(self.quantity) * self.mark_price


@dataclass
class Balance:
    """Account balance."""

    asset: str
    total: Decimal
    available: Decimal
    locked: Decimal = Decimal("0")
    usd_value: Decimal | None = None


@dataclass
class ExchangeConfig:
    """Exchange adapter configuration."""

    name: str
    api_key: str | None = None
    api_secret: str | None = None
    passphrase: str | None = None
    testnet: bool = True
    rate_limit: int = 1200
    ws_enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


class ExchangeAdapter(ABC):
    """
    Abstract base class for exchange adapters.

    Provides unified interface for:
    - Order management
    - Position management
    - Market data (via data layer)
    - Account info
    - WebSocket streams
    """

    def __init__(self, config: ExchangeConfig):
        self.config = config
        self._connected = False
        self._ws_connections: dict[str, Any] = {}
        self._order_callbacks: list[Callable[[Order], Any]] = []
        self._position_callbacks: list[Callable[[Position], Any]] = []
        self._trade_callbacks: list[Callable[[Trade], Any]] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Exchange name."""
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Connect to exchange."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from exchange."""
        pass

    # ===== Order Management =====
    @abstractmethod
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
        """Create a new order."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: Symbol) -> bool:
        """Cancel an order."""
        pass

    @abstractmethod
    async def cancel_all_orders(self, symbol: Symbol | None = None) -> list[str]:
        """Cancel all orders for symbol or all symbols."""
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: Symbol) -> Order | None:
        """Get order by ID."""
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Symbol | None = None) -> list[Order]:
        """Get all open orders."""
        pass

    @abstractmethod
    async def get_order_history(
        self,
        symbol: Symbol | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get order history."""
        pass

    # ===== Position Management =====
    @abstractmethod
    async def get_positions(self, symbol: Symbol | None = None) -> list[Position]:
        """Get current positions."""
        pass

    @abstractmethod
    async def get_position(self, symbol: Symbol) -> Position | None:
        """Get position for symbol."""
        pass

    @abstractmethod
    async def set_leverage(self, symbol: Symbol, leverage: int) -> bool:
        """Set position leverage."""
        pass

    @abstractmethod
    async def set_margin_type(self, symbol: Symbol, margin_type: str) -> bool:
        """Set margin type (cross/isolated)."""
        pass

    # ===== Account =====
    @abstractmethod
    async def get_balances(self) -> list[Balance]:
        """Get account balances."""
        pass

    @abstractmethod
    async def get_balance(self, asset: str) -> Balance | None:
        """Get balance for asset."""
        pass

    @abstractmethod
    async def get_account_info(self) -> dict[str, Any]:
        """Get account info (fees, limits, etc.)."""
        pass

    # ===== Market Data (delegates to data layer) =====
    async def get_ticker(self, symbol: Symbol) -> Ticker | None:
        """Get ticker from data layer."""
        from cryptobot.data.fetcher import get_fetcher
        fetcher = await get_fetcher()
        return await fetcher.fetch_ticker(symbol)

    async def get_orderbook(self, symbol: Symbol, depth: int = 100) -> OrderBook | None:
        """Get order book from data layer."""
        from cryptobot.data.fetcher import get_fetcher
        fetcher = await get_fetcher()
        return await fetcher.fetch_orderbook(symbol, depth)

    async def get_funding_rate(self, symbol: Symbol) -> FundingRate | None:
        """Get funding rate from data layer."""
        from cryptobot.data.fetcher import get_fetcher
        fetcher = await get_fetcher()
        return await fetcher.fetch_funding_rate(symbol)

    # ===== WebSocket Streams =====
    @abstractmethod
    async def subscribe_orders(self, callback: Callable[[Order], Any]) -> str:
        """Subscribe to order updates."""
        pass

    @abstractmethod
    async def subscribe_positions(self, callback: Callable[[Position], Any]) -> str:
        """Subscribe to position updates."""
        pass

    @abstractmethod
    async def subscribe_trades(self, symbol: Symbol, callback: Callable[[Trade], Any]) -> str:
        """Subscribe to trade stream."""
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from stream."""
        pass

    # ===== Exchange-Specific =====
    @abstractmethod
    def _symbol_to_exchange(self, symbol: Symbol) -> str:
        """Convert unified symbol to exchange format."""
        pass

    @abstractmethod
    def _symbol_from_exchange(self, exchange_symbol: str, market_type: MarketType) -> Symbol:
        """Convert exchange symbol to unified format."""
        pass

    def _round_quantity(self, symbol: Symbol, quantity: Decimal) -> Decimal:
        """Round quantity to exchange precision."""
        # Would use exchange info
        return quantity

    def _round_price(self, symbol: Symbol, price: Decimal) -> Decimal:
        """Round price to exchange precision."""
        return price


# Registry for exchange adapters
class ExchangeAdapterRegistry:
    """Registry for exchange adapters."""

    def __init__(self):
        self._adapters: dict[str, type[ExchangeAdapter]] = {}

    def register(self, name: str) -> Callable:
        """Decorator to register an adapter class."""

        def decorator(cls: type[ExchangeAdapter]) -> type[ExchangeAdapter]:
            self._adapters[name.lower()] = cls
            logger.info(f"Registered exchange adapter: {name}")
            return cls

        return decorator

    def get(self, name: str) -> type[ExchangeAdapter] | None:
        """Get adapter class by name."""
        return self._adapters.get(name.lower())

    def create(self, name: str, config: ExchangeConfig) -> ExchangeAdapter | None:
        """Create adapter instance."""
        cls = self.get(name)
        if cls:
            return cls(config)
        return None

    def list_adapters(self) -> list[str]:
        """List registered adapters."""
        return list(self._adapters.keys())


exchange_adapter_registry = ExchangeAdapterRegistry()