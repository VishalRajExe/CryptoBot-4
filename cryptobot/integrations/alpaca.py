"""
Alpaca Paper Trading Adapter.

Integrates with Alpaca Markets paper trading API for crypto and equities.
Uses the provided API credentials for paper trading.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

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
from cryptobot.data.models import Symbol, MarketType

logger = logging.getLogger(__name__)


@dataclass
class AlpacaConfig:
    """Alpaca-specific configuration."""

    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets/v2"
    ws_url: str = "wss://paper-api.alpaca.markets/stream"
    crypto_enabled: bool = True


class AlpacaAdapter(ExchangeAdapter):
    """
    Alpaca paper trading adapter.

    Supports:
    - Crypto trading (24/7)
    - Equities trading (market hours)
    - Paper trading by default
    - Real-time WebSocket streams
    - Order management (bracket, OCO, trailing)
    """

    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        self.alpaca_config = AlpacaConfig(
            api_key=config.api_key or "",
            secret_key=config.api_secret or "",
            base_url=config.options.get("base_url", "https://paper-api.alpaca.markets/v2"),
            ws_url=config.options.get("ws_url", "wss://paper-api.alpaca.markets/stream"),
        )
        self._client: httpx.AsyncClient | None = None
        self._account_id: str | None = None
        self._ws_connections: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "alpaca"

    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        return {
            "APCA-API-KEY-ID": self.alpaca_config.api_key,
            "APCA-API-SECRET-KEY": self.alpaca_config.secret_key,
            "Content-Type": "application/json",
        }

    async def connect(self) -> None:
        """Connect to Alpaca API."""
        self._client = httpx.AsyncClient(
            base_url=self.alpaca_config.base_url,
            headers=self._get_headers(),
            timeout=httpx.Timeout(30.0),
        )

        # Test connection and get account info
        try:
            await self._get_account()
            self._connected = True
            logger.info("Connected to Alpaca paper trading")
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Alpaca."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        for ws in self._ws_connections.values():
            await ws.close()
        self._ws_connections.clear()
        self._connected = False
        logger.info("Disconnected from Alpaca")

    async def _get_account(self) -> dict[str, Any]:
        """Get account info."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        resp = await self._client.get("/v2/account")
        resp.raise_for_status()
        account = resp.json()
        self._account_id = account.get("id")
        return account

    def _symbol_to_alpaca(self, symbol: Symbol) -> str:
        """Convert unified symbol to Alpaca format."""
        if symbol.market_type == MarketType.SPOT:
            return f"{symbol.base}/{symbol.quote}"
        # For crypto, Alpaca uses BASE/QUOTE format
        return f"{symbol.base}/{symbol.quote}"

    def _symbol_from_alpaca(self, alpaca_symbol: str) -> Symbol:
        """Convert Alpaca symbol to unified format."""
        parts = alpaca_symbol.split("/")
        if len(parts) == 2:
            return Symbol(
                base=parts[0],
                quote=parts[1],
                exchange="alpaca",
                market_type=MarketType.SPOT,
            )
        return Symbol(
            base=alpaca_symbol,
            quote="USD",
            exchange="alpaca",
            market_type=MarketType.SPOT,
        )

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Make authenticated request."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        resp = await self._client.request(
            method=method,
            url=path,
            json=json,
            params=params,
        )
        resp.raise_for_status()
        return resp

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
        """Create order on Alpaca."""
        alpaca_symbol = self._symbol_to_alpaca(symbol)

        # Map order type
        type_map = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
            OrderType.STOP: "stop",
            OrderType.STOP_LIMIT: "stop_limit",
        }
        alpaca_type = type_map.get(type, "market")

        # Map time in force
        tif_map = {
            TimeInForce.GTC: "gtc",
            TimeInForce.IOC: "ioc",
            TimeInForce.FOK: "fok",
            TimeInForce.DAY: "day",
        }
        alpaca_tif = tif_map.get(time_in_force, "gtc")

        # Build order payload
        payload = {
            "symbol": alpaca_symbol,
            "qty": str(quantity),
            "side": side.value.lower(),
            "type": alpaca_type,
            "time_in_force": alpaca_tif,
        }

        if client_order_id:
            payload["client_order_id"] = client_order_id

        if price is not None:
            payload["limit_price"] = str(price)

        if stop_price is not None:
            payload["stop_price"] = str(stop_price)

        # Handle bracket orders (OCO)
        if kwargs.get("take_profit") or kwargs.get("stop_loss"):
            order_class = "bracket"
            if kwargs.get("take_profit"):
                payload["take_profit"] = {"limit_price": str(kwargs["take_profit"])}
            if kwargs.get("stop_loss"):
                payload["stop_loss"] = {"stop_price": str(kwargs["stop_loss"])}
        else:
            order_class = "simple"

        payload["order_class"] = order_class

        try:
            resp = await self._request("POST", "/v2/orders", json=payload)
            data = resp.json()

            return self._parse_order_response(data, symbol, side, type, quantity, price, stop_price)

        except httpx.HTTPStatusError as e:
            logger.error(f"Alpaca order error: {e.response.text}")
            raise

    def _parse_order_response(
        self,
        data: dict,
        symbol: Symbol,
        side: OrderSide,
        type: OrderType,
        quantity: Decimal,
        price: Decimal | None,
        stop_price: Decimal | None,
    ) -> Order:
        """Parse Alpaca order response."""
        status_map = {
            "new": OrderStatus.NEW,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "done_for_day": OrderStatus.NEW,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
            "pending_review": OrderStatus.PENDING,
        }

        legs = data.get("legs", [])
        if legs:
            # Bracket order - main leg
            leg = legs[0]
        else:
            leg = data

        return Order(
            id=str(leg.get("id", data.get("id"))),
            client_order_id=leg.get("client_order_id", data.get("client_order_id")),
            symbol=symbol,
            side=side,
            type=type,
            quantity=Decimal(str(leg.get("qty", quantity))),
            price=Decimal(str(leg.get("limit_price", price or 0))) if leg.get("limit_price") else price,
            stop_price=Decimal(str(leg.get("stop_price", stop_price or 0))) if leg.get("stop_price") else stop_price,
            status=status_map.get(leg.get("status", "new"), OrderStatus.NEW),
            time_in_force=TimeInForce.GTC,
            filled_quantity=Decimal(str(leg.get("filled_qty", "0"))),
            avg_fill_price=Decimal(str(leg.get("filled_avg_price", "0"))) if leg.get("filled_avg_price") else None,
            commission=Decimal("0"),
            created_at=datetime.fromisoformat(leg.get("submitted_at", datetime.utcnow().isoformat()).replace("Z", "+00:00")),
        )

    async def cancel_order(self, order_id: str, symbol: Symbol) -> bool:
        """Cancel order by ID."""
        try:
            resp = await self._request("DELETE", f"/v2/orders/{order_id}")
            return resp.status_code == 204
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    async def cancel_all_orders(self, symbol: Symbol | None = None) -> list[str]:
        """Cancel all open orders."""
        try:
            params = {}
            if symbol:
                params["symbols"] = self._symbol_to_alpaca(symbol)

            resp = await self._request("DELETE", "/v2/orders", params=params)
            data = resp.json()
            return [str(o.get("id")) for o in data]
        except Exception as e:
            logger.error(f"Cancel all orders error: {e}")
            return []

    async def get_order(self, order_id: str, symbol: Symbol) -> Order | None:
        """Get order by ID."""
        try:
            resp = await self._request("GET", f"/v2/orders/{order_id}")
            data = resp.json()
            return self._parse_order_response(data, symbol, OrderSide.BUY, OrderType.MARKET, Decimal("0"), None, None)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_open_orders(self, symbol: Symbol | None = None) -> list[Order]:
        """Get all open orders."""
        try:
            params = {"status": "open"}
            if symbol:
                params["symbols"] = self._symbol_to_alpaca(symbol)

            resp = await self._request("GET", "/v2/orders", params=params)
            data = resp.json()

            orders = []
            for o in data:
                symbol_obj = self._symbol_from_alpaca(o["symbol"])
                orders.append(self._parse_order_response(o, symbol_obj, OrderSide.BUY, OrderType.MARKET, Decimal("0"), None, None))
            return orders
        except Exception as e:
            logger.error(f"Get open orders error: {e}")
            return []

    async def get_order_history(
        self,
        symbol: Symbol | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get order history."""
        try:
            params = {"status": "closed", "limit": str(limit)}
            if symbol:
                params["symbols"] = self._symbol_to_alpaca(symbol)
            if start:
                params["after"] = start.isoformat()
            if end:
                params["until"] = end.isoformat()

            resp = await self._request("GET", "/v2/orders", params=params)
            data = resp.json()

            orders = []
            for o in data:
                symbol_obj = self._symbol_from_alpaca(o["symbol"])
                orders.append(self._parse_order_response(o, symbol_obj, OrderSide.BUY, OrderType.MARKET, Decimal("0"), None, None))
            return orders
        except Exception as e:
            logger.error(f"Get order history error: {e}")
            return []

    # ===== Position Management =====

    async def get_positions(self, symbol: Symbol | None = None) -> list[Position]:
        """Get current positions."""
        try:
            resp = await self._request("GET", "/v2/positions")
            data = resp.json()

            positions = []
            for p in data:
                if p.get("asset_class") != "crypto" and not self.alpaca_config.crypto_enabled:
                    continue

                sym = self._symbol_from_alpaca(p["symbol"])
                if symbol and sym != symbol:
                    continue

                qty = Decimal(str(p["qty"]))
                if qty == 0:
                    continue

                positions.append(Position(
                    symbol=self._symbol_from_alpaca(p["symbol"]),
                    quantity=qty,
                    entry_price=Decimal(str(p["avg_entry_price"])),
                    mark_price=Decimal(str(p["current_price"])),
                    unrealized_pnl=Decimal(str(p["unrealized_pl"])),
                    realized_pnl=Decimal("0"),
                    leverage=Decimal("1"),
                    margin=Decimal("0"),
                ))

            return positions
        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return []

    async def get_position(self, symbol: Symbol) -> Position | None:
        """Get position for symbol."""
        positions = await self.get_positions(symbol)
        return positions[0] if positions else None

    async def set_leverage(self, symbol: Symbol, leverage: int) -> bool:
        """Alpaca doesn't support leverage setting for crypto."""
        return True

    async def set_margin_type(self, symbol: Symbol, margin_type: str) -> bool:
        """Alpaca doesn't support margin type setting."""
        return True

    # ===== Account =====

    async def get_balances(self) -> list[Balance]:
        """Get account balances."""
        try:
            resp = await self._request("GET", "/v2/account")
            data = resp.json()

            balances = []
            # Total equity
            balances.append(Balance(
                asset="EQUITY",
                total=Decimal(str(data.get("equity", "0"))),
                available=Decimal(str(data.get("cash", "0"))),
            ))

            # Cash
            balances.append(Balance(
                asset="USD",
                total=Decimal(str(data.get("cash", "0"))),
                available=Decimal(str(data.get("cash", "0"))),
            ))

            # Crypto balances (if available)
            # Would need separate endpoint for crypto balances
            return balances
        except Exception as e:
            logger.error(f"Get balances error: {e}")
            return []

    async def get_balance(self, asset: str) -> Balance | None:
        """Get balance for asset."""
        balances = await self.get_balances()
        return next((b for b in balances if b.asset == asset), None)

    async def get_account_info(self) -> dict[str, Any]:
        """Get account info."""
        try:
            resp = await self._request("GET", "/v2/account")
            return resp.json()
        except Exception as e:
            logger.error(f"Get account info error: {e}")
            return {}

    # ===== Market Data (delegates to data layer) =====

    # ===== WebSocket Streams =====

    async def subscribe_orders(self, callback) -> str:
        """Subscribe to order updates via WebSocket."""
        sub_id = f"alpaca_orders_{id(callback)}"
        # Would implement WebSocket subscription
        return sub_id

    async def subscribe_positions(self, callback) -> str:
        """Subscribe to position updates via WebSocket."""
        sub_id = f"alpaca_positions_{id(callback)}"
        return sub_id

    async def subscribe_trades(self, symbol: Symbol, callback) -> str:
        """Subscribe to trade stream."""
        sub_id = f"alpaca_trades_{symbol.unified}_{id(callback)}"
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        ws = self._ws_connections.pop(subscription_id, None)
        if ws:
            await ws.close()

    # ===== Symbol Conversion =====

    def _symbol_to_exchange(self, symbol: Symbol) -> str:
        return self._symbol_to_alpaca(symbol)

    def _symbol_from_exchange(self, exchange_symbol: str, market_type: MarketType) -> Symbol:
        return self._symbol_from_alpaca(exchange_symbol)

    def _format_quantity(self, symbol: Symbol, quantity: Decimal) -> str:
        return f"{quantity:.8f}".rstrip("0").rstrip(".")

    def _format_price(self, symbol: Symbol, price: Decimal | None) -> str:
        if price is None:
            return "0"
        return f"{price:.4f}".rstrip("0").rstrip(".")


# =============================================================================
# Alpaca Paper Trading Engine
# =============================================================================

class AlpacaPaperEngine:
    """
    High-level Alpaca paper trading engine.

    Manages:
    - Account creation with provided API keys
    - Position tracking
    - Order management
    - Real-time updates via WebSocket
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper: bool = True,
        base_url: str | None = None,
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper

        self.adapter = AlpacaAdapter(ExchangeConfig(
            name="alpaca",
            api_key=api_key,
            api_secret=secret_key,
            testnet=paper,
            options={
                "base_url": base_url or ("https://paper-api.alpaca.markets/v2" if paper else "https://api.alpaca.markets/v2"),
                "crypto_enabled": True,
            },
        ))

        self._running = False

    async def start(self) -> None:
        """Start the engine."""
        await self.adapter.connect()
        self._running = True
        logger.info("Alpaca paper engine started")

    async def stop(self) -> None:
        """Stop the engine."""
        await self.adapter.disconnect()
        self._running = False
        logger.info("Alpaca paper engine stopped")

    def get_adapter(self) -> AlpacaAdapter:
        return self.adapter

    async def create_account(self, initial_cash: float = 100000) -> dict[str, Any]:
        """Create paper trading account (Alpaca creates automatically)."""
        account = await self.adapter._get_account()
        return {
            "account_id": account.get("id"),
            "equity": float(account.get("equity", 0)),
            "cash": float(account.get("cash", 0)),
            "status": account.get("status"),
            "trading_blocked": account.get("trading_blocked"),
        }

    async def get_account_summary(self) -> dict[str, Any]:
        """Get account summary."""
        account = await self.adapter._get_account()
        positions = await self.adapter.get_positions()

        return {
            "account_id": account.get("id"),
            "equity": float(account.get("equity", 0)),
            "cash": float(account.get("cash", 0)),
            "buying_power": float(account.get("buying_power", 0)),
            "positions_count": len(positions),
            "daytrade_count": account.get("daytrade_count", 0),
        }

    async def get_positions(self) -> list[dict]:
        """Get formatted positions."""
        positions = await self.adapter.get_positions()
        return [
            {
                "symbol": p.symbol.unified,
                "quantity": float(p.quantity),
                "side": "long" if p.quantity > 0 else "short",
                "entry_price": float(p.entry_price),
                "mark_price": float(p.mark_price),
                "unrealized_pnl": float(p.unrealized_pnl),
                "unrealized_pnl_pct": float(p.unrealized_pnl) / (float(p.entry_price) * abs(float(p.quantity))) * 100 if p.quantity != 0 else 0,
            }
            for p in positions
        ]


# =============================================================================
# Factory Functions
# =============================================================================

async def create_alpaca_engine(
    api_key: str = "PKP753ICW5ZTKXS3KWXUT6P2P3",
    secret_key: str = "E6EPPR8sLqqHJGEdMncagQYyfQ9CbpnuWhdTF6x4HhY6",
    paper: bool = True,
) -> AlpacaPaperEngine:
    """Create and start Alpaca paper trading engine."""
    engine = AlpacaPaperEngine(
        api_key=api_key,
        secret_key=secret_key,
        paper=paper,
    )
    await engine.start()
    return engine


async def create_alpaca_adapter(
    api_key: str = "PKP753ICW5ZTKXS3KWXUT6P2P3",
    secret_key: str = "E6EPPR8sLqqHJGEdMncagQYyfQ9CbpnuWhdTF6x4HhY6",
    paper: bool = True,
) -> AlpacaAdapter:
    """Create and connect Alpaca adapter."""
    adapter = AlpacaAdapter(ExchangeConfig(
        name="alpaca",
        api_key=api_key,
        api_secret=secret_key,
        testnet=paper,
        options={"crypto_enabled": True},
    ))
    await adapter.connect()
    return adapter