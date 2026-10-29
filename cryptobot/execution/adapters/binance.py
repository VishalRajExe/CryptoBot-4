"""
Binance exchange adapter.
Adapted from hummingbot's Binance connector and freqtrade's Binance exchange.
"""

from __future__ import annotations

import asyncio
import hmac
import hashlib
import time
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets
import json

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
    exchange_adapter_registry,
)
from cryptobot.data.models import Symbol, MarketType

logger = logging.getLogger(__name__)


class BinanceAdapter(ExchangeAdapter):
    """Binance exchange adapter (Spot + Futures)."""

    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        self._base_url = config.base_url or (
            "https://testnet.binancefuture.com" if config.testnet else "https://fapi.binance.com"
        )
        self._spot_base = "https://testnet.binance.vision" if config.testnet else "https://api.binance.com"
        self._ws_base = config.ws_url or (
            "wss://stream.binancefuture.com" if config.testnet else "wss://fstream.binance.com"
        )
        self._spot_ws = "wss://testnet.binance.vision" if config.testnet else "wss://stream.binance.com"
        self._listen_key: str | None = None
        self._listen_key_task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        return "binance"

    def _get_base_url(self, market: MarketType) -> str:
        if market == MarketType.SPOT:
            return self._spot_base
        return self._base_url

    def _get_ws_url(self, market: MarketType) -> str:
        if market == MarketType.SPOT:
            return self._spot_ws
        return self._ws_base

    def _symbol_to_binance(self, symbol: Symbol) -> str:
        """Convert unified symbol to Binance format."""
        return f"{symbol.base}{symbol.quote}"

    def _symbol_from_binance(self, binance_symbol: str, market: MarketType) -> Symbol:
        """Convert Binance symbol to unified format."""
        # Binance uses BASEQUOTE format
        for q in ["USDT", "BUSD", "USDC", "BTC", "ETH"]:
            if binance_symbol.endswith(q):
                base = binance_symbol[:-len(q)]
                quote = q
                return Symbol(base=base, quote=quote, exchange="binance", market_type=market)
        # Default
        return Symbol(
            base=binance_symbol[:-4],
            quote=binance_symbol[-4:],
            exchange="binance",
            market_type=market,
        )

    def _sign_params(self, params: dict) -> str:
        """Sign parameters for authenticated requests."""
        query = urlencode(params, doseq=True)
        signature = hmac.new(
            self.config.api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{query}&signature={signature}"

    def _get_headers(self) -> dict[str, str]:
        """Get headers for authenticated requests."""
        return {"X-MBX-APIKEY": self.config.api_key or ""}

    async def connect(self) -> None:
        """Connect to Binance."""
        if self._connected:
            return

        # Start user data stream
        await self._start_user_stream()
        self._connected = True
        logger.info("Connected to Binance")

    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        if self._listen_key_task:
            self._listen_key_task.cancel()
            try:
                await self._listen_key_task
            except asyncio.CancelledError:
                pass
        await self._close_user_stream()
        for ws in self._ws_connections.values():
            await ws.close()
        self._ws_connections.clear()
        self._connected = False
        logger.info("Disconnected from Binance")

    async def _start_user_stream(self) -> None:
        """Start user data stream for order/position updates."""
        client = httpx.AsyncClient()
        try:
            url = f"{self._base_url}/fapi/v1/listenKey"
            resp = await client.post(url, headers=self._get_headers())
            resp.raise_for_status()
            self._listen_key = resp.json()["listenKey"]

            # Keep alive task
            async def keep_alive():
                while True:
                    await asyncio.sleep(30 * 60)  # Every 30 min
                    try:
                        await client.put(f"{self._base_url}/fapi/v1/listenKey", headers=self._get_headers())
                    except Exception as e:
                        logger.error(f"Listen key keep-alive failed: {e}")

            self._listen_key_task = asyncio.create_task(keep_alive())

            # Connect to user data stream
            ws_url = f"{self._ws_base}/ws/{self._listen_key}"
            asyncio.create_task(self._user_stream_listener(ws_url))

        except Exception as e:
            logger.error(f"Failed to start user stream: {e}")
        finally:
            await client.aclose()

    async def _close_user_stream(self) -> None:
        """Close user data stream."""
        if self._listen_key:
            client = httpx.AsyncClient()
            try:
                await client.delete(
                    f"{self._base_url}/fapi/v1/listenKey",
                    headers=self._get_headers(),
                )
            except Exception:
                pass
            finally:
                await client.aclose()

    async def _user_stream_listener(self, ws_url: str) -> None:
        """Listen to user data stream."""
        async with websockets.connect(ws_url) as ws:
            self._ws_connections["user_stream"] = ws
            async for msg in ws:
                try:
                    data = json.loads(msg)
                    await self._handle_user_stream_event(data)
                except Exception as e:
                    logger.error(f"User stream error: {e}")

    async def _handle_user_stream_event(self, data: dict) -> None:
        """Handle user stream events."""
        event_type = data.get("e")

        if event_type == "ORDER_TRADE_UPDATE":
            order = self._parse_order_update(data["o"])
            for cb in self._order_callbacks:
                try:
                    await cb(order)
                except Exception as e:
                    logger.error(f"Order callback error: {e}")

        elif event_type == "ACCOUNT_UPDATE":
            for pos_data in data.get("a", {}).get("P", []):
                position = self._parse_position_update(pos_data)
                for cb in self._position_callbacks:
                    try:
                        await cb(position)
                    except Exception as e:
                        logger.error(f"Position callback error: {e}")

    def _parse_order_update(self, data: dict) -> Order:
        """Parse order update from user stream."""
        status_map = {
            "NEW": OrderStatus.NEW,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
        }

        symbol = self._symbol_from_binance(data["s"], MarketType.LINEAR)

        return Order(
            id=str(data["i"]),
            client_order_id=data["c"],
            symbol=symbol,
            side=OrderSide.BUY if data["S"] == "BUY" else OrderSide.SELL,
            type=OrderType(data["o"].lower()),
            quantity=Decimal(data["q"]),
            price=Decimal(data["p"]) if data["p"] != "0" else None,
            stop_price=Decimal(data["sp"]) if data.get("sp") and data["sp"] != "0" else None,
            status=status_map.get(data["X"], OrderStatus.NEW),
            time_in_force=TimeInForce(data["f"]),
            filled_quantity=Decimal(data["z"]),
            avg_fill_price=Decimal(data["ap"]) if data["ap"] != "0" else None,
            commission=Decimal(data.get("n", "0")),
            updated_at=datetime.fromtimestamp(data["T"] / 1000),
        )

    def _parse_position_update(self, data: dict) -> Position:
        """Parse position update from user stream."""
        symbol = self._symbol_from_binance(data["s"], MarketType.LINEAR)

        return Position(
            symbol=symbol,
            quantity=Decimal(data["pa"]),
            entry_price=Decimal(data["ep"]),
            mark_price=Decimal(data["mt"]),
            unrealized_pnl=Decimal(data["up"]),
            realized_pnl=Decimal("0"),
            leverage=Decimal(data["le"]),
            margin=Decimal(data.get("im", "0")),
            margin_type=data.get("mt", "cross"),
        )

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
        """Create order on Binance."""
        client = httpx.AsyncClient()
        try:
            binance_symbol = self._symbol_to_binance(symbol)
            market_type = symbol.market_type

            params = {
                "symbol": binance_symbol,
                "side": side.value.upper(),
                "type": type.value.upper(),
                "quantity": self._format_quantity(symbol, quantity),
                "timeInForce": time_in_force.value,
                "timestamp": int(time.time() * 1000),
            }

            if client_order_id:
                params["newClientOrderId"] = client_order_id

            if type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
                params["price"] = self._format_price(symbol, price)
            if type in (OrderType.STOP, OrderType.STOP_LIMIT):
                params["stopPrice"] = self._format_price(symbol, stop_price)
            if type == OrderType.TRAILING:
                params["callbackRate"] = kwargs.get("callback_rate", 1.0)

            query = self._sign_params(params)
            url = f"{self._get_base_url(market_type)}/fapi/v1/order"
            if market_type == MarketType.SPOT:
                url = f"{self._spot_base}/api/v3/order"

            headers = self._get_headers()
            resp = await client.post(url, data=query, headers=headers)
            resp.raise_for_status()

            data = resp.json()
            return self._parse_order_response(data, symbol, side, type, quantity, price, stop_price)

        except httpx.HTTPStatusError as e:
            logger.error(f"Binance order error: {e.response.text}")
            raise
        finally:
            await client.aclose()

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
        status_map = {
            "NEW": OrderStatus.NEW,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
        }

        return Order(
            id=str(data["orderId"]),
            client_order_id=data["clientOrderId"],
            symbol=symbol,
            side=side,
            type=type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status=status_map.get(data["status"], OrderStatus.NEW),
            time_in_force=TimeInForce(data["timeInForce"]),
            filled_quantity=Decimal(data.get("executedQty", "0")),
            avg_fill_price=Decimal(data["avgPrice"]) if data.get("avgPrice") != "0.00000000" else None,
            commission=Decimal("0"),
            created_at=datetime.fromtimestamp(data["transactTime"] / 1000),
        )

    async def cancel_order(self, order_id: str, symbol: Symbol) -> bool:
        """Cancel order."""
        client = httpx.AsyncClient()
        try:
            binance_symbol = self._symbol_to_binance(symbol)
            market_type = symbol.market_type

            params = {
                "symbol": binance_symbol,
                "orderId": order_id,
                "timestamp": int(time.time() * 1000),
            }

            query = self._sign_params(params)
            url = f"{self._get_base_url(market_type)}/fapi/v1/order"
            if market_type == MarketType.SPOT:
                url = f"{self._spot_base}/api/v3/order"

            headers = self._get_headers()
            resp = await client.delete(url, params=query, headers=headers)
            resp.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False
        finally:
            await client.aclose()

    async def cancel_all_orders(self, symbol: Symbol | None = None) -> list[str]:
        """Cancel all open orders."""
        client = httpx.AsyncClient()
        cancelled = []
        try:
            if symbol:
                symbols = [symbol]
            else:
                # Get all symbols with open orders
                symbols = await self._get_symbols_with_orders()

            for sym in symbols:
                binance_symbol = self._symbol_to_binance(sym)
                market_type = sym.market_type

                params = {
                    "symbol": binance_symbol,
                    "timestamp": int(time.time() * 1000),
                }

                query = self._sign_params(params)
                url = f"{self._get_base_url(market_type)}/fapi/v1/allOpenOrders"
                if market_type == MarketType.SPOT:
                    url = f"{self._spot_base}/api/v3/allOpenOrders"

                headers = self._get_headers()
                resp = await client.delete(url, params=query, headers=headers)
                if resp.status_code == 200:
                    cancelled.append(binance_symbol)

        except Exception as e:
            logger.error(f"Cancel all orders error: {e}")
        finally:
            await client.aclose()

        return cancelled

    async def get_order(self, order_id: str, symbol: Symbol) -> Order | None:
        """Get order by ID."""
        client = httpx.AsyncClient()
        try:
            binance_symbol = self._symbol_to_binance(symbol)
            market_type = symbol.market_type

            params = {
                "symbol": binance_symbol,
                "orderId": order_id,
                "timestamp": int(time.time() * 1000),
            }

            query = self._sign_params(params)
            url = f"{self._get_base_url(market_type)}/fapi/v1/order"
            if market_type == MarketType.SPOT:
                url = f"{self._spot_base}/api/v3/order"

            headers = self._get_headers()
            resp = await client.get(url, params=query, headers=headers)
            resp.raise_for_status()

            data = resp.json()
            return self._parse_order_response(data, symbol, OrderSide.BUY, OrderType.LIMIT, Decimal("0"), None, None)

        except Exception as e:
            logger.error(f"Get order error: {e}")
            return None
        finally:
            await client.aclose()

    async def get_open_orders(self, symbol: Symbol | None = None) -> list[Order]:
        """Get open orders."""
        client = httpx.AsyncClient()
        orders = []
        try:
            symbols = [symbol] if symbol else await self._get_symbols_with_orders()

            for sym in symbols:
                binance_symbol = self._symbol_to_binance(sym)
                market_type = sym.market_type

                params = {
                    "symbol": binance_symbol,
                    "timestamp": int(time.time() * 1000),
                }

                query = self._sign_params(params)
                url = f"{self._get_base_url(market_type)}/fapi/v1/openOrders"
                if market_type == MarketType.SPOT:
                    url = f"{self._spot_base}/api/v3/openOrders"

                headers = self._get_headers()
                resp = await client.get(url, params=query, headers=headers)
                resp.raise_for_status()

                data = resp.json()
                for o in data:
                    orders.append(self._parse_order_response(o, sym, OrderSide.BUY, OrderType.LIMIT, Decimal("0"), None, None))

        except Exception as e:
            logger.error(f"Get open orders error: {e}")
        finally:
            await client.aclose()

        return orders

    async def get_order_history(
        self,
        symbol: Symbol | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get order history."""
        # Similar to get_open_orders but with time range
        return []

    async def _get_symbols_with_orders(self) -> list[Symbol]:
        """Get symbols that have open orders."""
        # Would query exchange for all symbols with open orders
        return []

    # ===== Position Management =====
    async def get_positions(self, symbol: Symbol | None = None) -> list[Position]:
        """Get current positions."""
        client = httpx.AsyncClient()
        positions = []
        try:
            params = {"timestamp": int(time.time() * 1000)}
            if symbol:
                params["symbol"] = self._symbol_to_binance(symbol)

            query = self._sign_params(params)
            url = f"{self._base_url}/fapi/v2/positionRisk"

            headers = self._get_headers()
            resp = await client.get(url, params=query, headers=headers)
            resp.raise_for_status()

            data = resp.json()
            for p in data:
                if Decimal(p["positionAmt"]) != 0:
                    sym = self._symbol_from_binance(p["symbol"], MarketType.LINEAR)
                    if symbol is None or sym == symbol:
                        positions.append(self._parse_position_data(p, sym))

        except Exception as e:
            logger.error(f"Get positions error: {e}")
        finally:
            await client.aclose()

        return positions

    async def get_position(self, symbol: Symbol) -> Position | None:
        """Get position for symbol."""
        positions = await self.get_positions(symbol)
        return positions[0] if positions else None

    def _parse_position_data(self, data: dict, symbol: Symbol) -> Position:
        return Position(
            symbol=symbol,
            quantity=Decimal(data["positionAmt"]),
            entry_price=Decimal(data["entryPrice"]),
            mark_price=Decimal(data["markPrice"]),
            unrealized_pnl=Decimal(data["unRealizedProfit"]),
            realized_pnl=Decimal("0"),
            leverage=Decimal(data["leverage"]),
            margin=Decimal(data.get("isolatedMargin", "0")),
            margin_type=data.get("marginType", "cross"),
        )

    async def set_leverage(self, symbol: Symbol, leverage: int) -> bool:
        """Set leverage."""
        client = httpx.AsyncClient()
        try:
            binance_symbol = self._symbol_to_binance(symbol)

            params = {
                "symbol": binance_symbol,
                "leverage": leverage,
                "timestamp": int(time.time() * 1000),
            }

            query = self._sign_params(params)
            url = f"{self._base_url}/fapi/v1/leverage"

            headers = self._get_headers()
            resp = await client.post(url, data=query, headers=headers)
            resp.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Set leverage error: {e}")
            return False
        finally:
            await client.aclose()

    async def set_margin_type(self, symbol: Symbol, margin_type: str) -> bool:
        """Set margin type."""
        client = httpx.AsyncClient()
        try:
            binance_symbol = self._symbol_to_binance(symbol)

            params = {
                "symbol": binance_symbol,
                "marginType": margin_type.upper(),
                "timestamp": int(time.time() * 1000),
            }

            query = self._sign_params(params)
            url = f"{self._base_url}/fapi/v1/marginType"

            headers = self._get_headers()
            resp = await client.post(url, data=query, headers=headers)
            resp.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Set margin type error: {e}")
            return False
        finally:
            await client.aclose()

    # ===== Account =====
    async def get_balances(self) -> list[Balance]:
        """Get account balances."""
        client = httpx.AsyncClient()
        balances = []
        try:
            params = {"timestamp": int(time.time() * 1000)}
            query = self._sign_params(params)

            # Futures balances
            url = f"{self._base_url}/fapi/v2/balance"
            headers = self._get_headers()
            resp = await client.get(url, params=query, headers=headers)
            resp.raise_for_status()

            data = resp.json()
            for b in data:
                if Decimal(b["balance"]) > 0:
                    balances.append(Balance(
                        asset=b["asset"],
                        total=Decimal(b["balance"]),
                        available=Decimal(b["availableBalance"]),
                    ))

        except Exception as e:
            logger.error(f"Get balances error: {e}")
        finally:
            await client.aclose()

        return balances

    async def get_balance(self, asset: str) -> Balance | None:
        """Get balance for asset."""
        balances = await self.get_balances()
        return next((b for b in balances if b.asset == asset), None)

    async def get_account_info(self) -> dict[str, Any]:
        """Get account info."""
        client = httpx.AsyncClient()
        try:
            params = {"timestamp": int(time.time() * 1000)}
            query = self._sign_params(params)
            url = f"{self._base_url}/fapi/v2/account"
            headers = self._get_headers()
            resp = await client.get(url, params=query, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            await client.aclose()

    # ===== WebSocket Streams =====
    async def subscribe_orders(self, callback: Callable[[Order], Any]) -> str:
        """Subscribe to order updates."""
        self._order_callbacks.append(callback)
        sub_id = f"orders_{len(self._order_callbacks)}"
        return sub_id

    async def subscribe_positions(self, callback: Callable[[Position], Any]) -> str:
        """Subscribe to position updates."""
        self._position_callbacks.append(callback)
        sub_id = f"positions_{len(self._position_callbacks)}"
        return sub_id

    async def subscribe_trades(self, symbol: Symbol, callback: Callable) -> str:
        """Subscribe to trade stream."""
        binance_symbol = self._symbol_to_binance(symbol).lower()
        market_type = symbol.market_type
        stream = f"{binance_symbol}@trade"
        url = f"{self._get_ws_url(market_type)}/ws/{stream}"

        sub_id = f"trades_{symbol.unified}_{id(callback)}"

        async def _listen():
            async with websockets.connect(url) as ws:
                self._ws_connections[sub_id] = ws
                async for msg in ws:
                    data = json.loads(msg)
                    trade = self._parse_trade(data, symbol)
                    await callback(trade)

        asyncio.create_task(_listen())
        return sub_id

    def _parse_trade(self, data: dict, symbol: Symbol) -> Any:
        from cryptobot.data.models import Trade
        return Trade(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(data["T"] / 1000),
            price=Decimal(data["p"]),
            size=Decimal(data["q"]),
            side="buy" if data["m"] else "sell",
            trade_id=str(data["t"]),
            is_buyer_maker=data["m"],
        )

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from stream."""
        ws = self._ws_connections.pop(subscription_id, None)
        if ws:
            await ws.close()

    # ===== Symbol Conversion =====
    def _symbol_to_exchange(self, symbol: Symbol) -> str:
        return self._symbol_to_binance(symbol)

    def _symbol_from_exchange(self, exchange_symbol: str, market_type: MarketType) -> Symbol:
        return self._symbol_from_binance(exchange_symbol, market_type)

    def _format_quantity(self, symbol: Symbol, quantity: Decimal) -> str:
        """Format quantity for Binance."""
        # Would use exchange precision
        return f"{quantity:.8f}".rstrip("0").rstrip(".")

    def _format_price(self, symbol: Symbol, price: Decimal | None) -> str:
        """Format price for Binance."""
        if price is None:
            return "0"
        return f"{price:.8f}".rstrip("0").rstrip(".")


@exchange_adapter_registry.register("binance")
class BinanceAdapterRegistered(BinanceAdapter):
    pass