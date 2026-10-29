"""
Orders API routes.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from cryptobot.execution.paper import PaperEngine
from cryptobot.execution.adapters.base import Order, OrderStatus, OrderSide, OrderType, TimeInForce
from cryptobot.data.models import Symbol, MarketType
from cryptobot.api.deps import get_paper_engine

router = APIRouter()


class OrderRequest(BaseModel):
    symbol: str
    side: str  # buy, sell
    type: str = "market"  # market, limit, stop, stop_limit
    quantity: float
    price: float | None = None
    stop_price: float | None = None
    time_in_force: str = "GTC"
    client_order_id: str | None = None


class OrderResponse(BaseModel):
    id: str
    client_order_id: str
    symbol: str
    side: str
    type: str
    quantity: float
    price: float | None
    stop_price: float | None
    status: str
    filled_quantity: float
    avg_fill_price: float | None
    commission: float
    created_at: str
    updated_at: str


class CancelRequest(BaseModel):
    order_id: str


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    account_id: str | None = None,
    symbol: str | None = None,
    status: str | None = None,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """List orders across all accounts or specific account."""
    all_orders = []

    accounts = [engine.accounts[account_id]] if account_id else engine.accounts.values()

    for account in accounts:
        for order in account.orders.values():
            if symbol and order.symbol.unified != symbol:
                continue
            if status and order.status.name != status.upper():
                continue

            all_orders.append(OrderResponse(
                id=order.id,
                client_order_id=order.client_order_id,
                symbol=order.symbol.unified,
                side=order.side.value,
                type=order.type.value,
                quantity=float(order.quantity),
                price=float(order.price) if order.price else None,
                stop_price=float(order.stop_price) if order.stop_price else None,
                status=order.status.name,
                filled_quantity=float(order.filled_quantity),
                avg_fill_price=float(order.avg_fill_price) if order.avg_fill_price else None,
                commission=float(order.commission),
                created_at=order.created_at.isoformat(),
                updated_at=order.updated_at.isoformat(),
            ))

    return all_orders


@router.post("", response_model=OrderResponse)
async def create_order(
    request: OrderRequest,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Create a new order."""
    # Use default account if not specified
    account_id = list(engine.accounts.keys())[0]
    adapter = engine.get_adapter(account_id)
    if not adapter:
        raise HTTPException(status_code=503, detail="No adapter available")

    sym = Symbol.from_unified(request.symbol) if ":" in request.symbol else Symbol(
        base=request.symbol.split("/")[0] if "/" in request.symbol else request.symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )

    order = await adapter.create_order(
        symbol=sym,
        side=OrderSide(request.side.upper()),
        type=OrderType(request.type.upper()),
        quantity=request.quantity,
        price=request.price,
        stop_price=request.stop_price,
        time_in_force=TimeInForce(request.time_in_force),
        client_order_id=request.client_order_id,
    )

    return OrderResponse(
        id=order.id,
        client_order_id=order.client_order_id,
        symbol=order.symbol.unified,
        side=order.side.value,
        type=order.type.value,
        quantity=float(order.quantity),
        price=float(order.price) if order.price else None,
        stop_price=float(order.stop_price) if order.stop_price else None,
        status=order.status.name,
        filled_quantity=float(order.filled_quantity),
        avg_fill_price=float(order.avg_fill_price) if order.avg_fill_price else None,
        commission=float(order.commission),
        created_at=order.created_at.isoformat(),
        updated_at=order.updated_at.isoformat(),
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    account_id: str | None = None,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Get order by ID."""
    accounts = [engine.accounts[account_id]] if account_id else engine.accounts.values()

    for account in accounts:
        order = account.orders.get(order_id)
        if order:
            return OrderResponse(
                id=order.id,
                client_order_id=order.client_order_id,
                symbol=order.symbol.unified,
                side=order.side.value,
                type=order.type.value,
                quantity=float(order.quantity),
                price=float(order.price) if order.price else None,
                stop_price=float(order.stop_price) if order.stop_price else None,
                status=order.status.name,
                filled_quantity=float(order.filled_quantity),
                avg_fill_price=float(order.avg_fill_price) if order.avg_fill_price else None,
                commission=float(order.commission),
                created_at=order.created_at.isoformat(),
                updated_at=order.updated_at.isoformat(),
            )

    raise HTTPException(status_code=404, detail="Order not found")


@router.delete("/{order_id}")
async def cancel_order(
    order_id: str,
    account_id: str | None = None,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Cancel an order."""
    accounts = [engine.accounts[account_id]] if account_id else engine.accounts.values()

    for account in accounts:
        adapter = engine.get_adapter(account.id)
        if not adapter:
            continue

        success = await adapter.cancel_order(order_id, Symbol(base="", quote="", exchange=""))
        if success:
            return {"message": "Order cancelled", "order_id": order_id}

    raise HTTPException(status_code=404, detail="Order not found or cannot be cancelled")


@router.post("/cancel_all")
async def cancel_all_orders(
    account_id: str | None = None,
    symbol: str | None = None,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Cancel all open orders."""
    accounts = [engine.accounts[account_id]] if account_id else engine.accounts.values()

    results = {}
    for account in accounts:
        adapter = engine.get_adapter(account.id)
        if not adapter:
            continue

        sym = Symbol.from_unified(symbol) if symbol else None
        cancelled = await adapter.cancel_all_orders(sym)
        results[account.id] = cancelled

    return {"cancelled": results}


@router.get("/{order_id}/fills")
async def get_order_fills(
    order_id: str,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Get fills for an order."""
    # Would query trade history
    return {"order_id": order_id, "fills": []}


@router.post("/bracket")
async def create_bracket_order(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Create bracket order (entry + stop loss + take profit)."""
    account_id = list(engine.accounts.keys())[0]
    adapter = engine.get_adapter(account_id)
    if not adapter:
        raise HTTPException(status_code=503, detail="No adapter available")

    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )

    # Entry order
    entry_order = await adapter.create_order(
        symbol=sym,
        side=OrderSide(side.upper()),
        type=OrderType.LIMIT,
        quantity=quantity,
        price=entry_price,
    )

    orders = [entry_order]

    if entry_order.status == OrderStatus.FILLED:
        # Stop loss
        stop_side = OrderSide.SELL if side == "buy" else OrderSide.BUY
        stop_order = await adapter.create_order(
            symbol=sym,
            side=stop_side,
            type=OrderType.STOP,
            quantity=quantity,
            stop_price=stop_loss,
        )
        orders.append(stop_order)

        # Take profit
        tp_order = await adapter.create_order(
            symbol=sym,
            side=stop_side,
            type=OrderType.LIMIT,
            quantity=quantity,
            price=take_profit,
        )
        orders.append(tp_order)

    return {
        "orders": [
            OrderResponse(
                id=o.id,
                client_order_id=o.client_order_id,
                symbol=o.symbol.unified,
                side=o.side.value,
                type=o.type.value,
                quantity=float(o.quantity),
                price=float(o.price) if o.price else None,
                stop_price=float(o.stop_price) if o.stop_price else None,
                status=o.status.name,
                filled_quantity=float(o.filled_quantity),
                avg_fill_price=float(o.avg_fill_price) if o.avg_fill_price else None,
                commission=float(o.commission),
                created_at=o.created_at.isoformat(),
                updated_at=o.updated_at.isoformat(),
            )
            for o in orders
        ]
    }