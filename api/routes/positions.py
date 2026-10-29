"""
Positions API routes.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from cryptobot.execution.paper import PaperEngine, PaperAccount
from cryptobot.data.models import Symbol, MarketType
from cryptobot.api.main import get_paper_engine

router = APIRouter()


class PositionResponse(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    leverage: float
    margin: float
    side: str  # long, short
    updated_at: str


class AccountResponse(BaseModel):
    account_id: str
    name: str
    equity: float
    total_equity: float
    available_balance: float
    positions: list[PositionResponse]
    open_orders: int
    trades_today: int


@router.get("", response_model=list[AccountResponse])
async def list_positions(
    engine: PaperEngine = Depends(get_paper_engine),
):
    """List all accounts and their positions."""
    accounts = []
    for account_id, account in engine.accounts.items():
        adapter = engine.adapters.get(account_id)
        if not adapter:
            continue

        positions_resp = []
        for pos in account.positions.values():
            positions_resp.append(PositionResponse(
                symbol=pos.symbol.unified,
                quantity=float(pos.quantity),
                entry_price=float(pos.entry_price),
                mark_price=float(pos.mark_price),
                unrealized_pnl=float(pos.unrealized_pnl),
                unrealized_pnl_pct=float(pos.unrealized_pnl) / (float(pos.entry_price) * abs(float(pos.quantity))) * 100 if pos.quantity != 0 else 0,
                leverage=float(pos.leverage),
                margin=float(pos.margin),
                side="long" if pos.quantity > 0 else "short",
                updated_at=pos.updated_at.isoformat(),
            ))

        accounts.append(AccountResponse(
            account_id=account_id,
            name=account.name,
            equity=float(account.equity),
            total_equity=float(account.get_total_equity(adapter._mark_prices)),
            available_balance=float(account.balances.get("USDT", {}).available) if "USDT" in account.balances else 0,
            positions=positions_resp,
            open_orders=len([o for o in account.orders.values() if o.status.name in ("NEW", "PENDING", "PARTIALLY_FILLED")]),
            trades_today=len([t for t in account.trades if t.get("timestamp", "").startswith(datetime.utcnow().date().isoformat())]),
        ))

    return accounts


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account_positions(
    account_id: str,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Get positions for specific account."""
    account = engine.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    adapter = engine.get_adapter(account_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Adapter not found")

    positions_resp = []
    for pos in account.positions.values():
        positions_resp.append(PositionResponse(
            symbol=pos.symbol.unified,
            quantity=float(pos.quantity),
            entry_price=float(pos.entry_price),
            mark_price=float(pos.mark_price),
            unrealized_pnl=float(pos.unrealized_pnl),
            unrealized_pnl_pct=float(pos.unrealized_pnl) / (float(pos.entry_price) * abs(float(pos.quantity))) * 100 if pos.quantity != 0 else 0,
            leverage=float(pos.leverage),
            margin=float(pos.margin),
            side="long" if pos.quantity > 0 else "short",
            updated_at=pos.updated_at.isoformat(),
        ))

    return AccountResponse(
        account_id=account_id,
        name=account.name,
        equity=float(account.equity),
        total_equity=float(account.get_total_equity(adapter._mark_prices)),
        available_balance=float(account.balances.get("USDT", {}).available) if "USDT" in account.balances else 0,
        positions=positions_resp,
        open_orders=len([o for o in account.orders.values() if o.status.name in ("NEW", "PENDING", "PARTIALLY_FILLED")]),
        trades_today=len([t for t in account.trades if t.get("timestamp", "").startswith(datetime.utcnow().date().isoformat())]),
    )


@router.get("/{account_id}/summary")
async def get_account_summary(
    account_id: str,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Get account summary."""
    summary = engine.get_account_summary(account_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Account not found")
    return summary


@router.post("/{account_id}/close/{symbol}")
async def close_position(
    account_id: str,
    symbol: str,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Close a specific position."""
    adapter = engine.get_adapter(account_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Account not found")

    sym = Symbol.from_unified(symbol) if ":" in symbol else Symbol(
        base=symbol.split("/")[0] if "/" in symbol else symbol,
        quote="USDT",
        exchange="binance",
        market_type=MarketType.LINEAR,
    )

    # Get position
    position = await adapter.get_position(sym)
    if not position or position.quantity == 0:
        raise HTTPException(status_code=404, detail="Position not found")

    # Close position
    side = "sell" if position.quantity > 0 else "buy"
    order = await adapter.create_order(
        symbol=sym,
        side=side,
        type="market",
        quantity=abs(position.quantity),
    )

    return {
        "message": "Position closed",
        "order_id": order.id,
        "symbol": symbol,
        "side": side,
        "quantity": float(abs(position.quantity)),
    }


@router.post("/{account_id}/close_all")
async def close_all_positions(
    account_id: str,
    engine: PaperEngine = Depends(get_paper_engine),
):
    """Close all positions for account."""
    adapter = engine.get_adapter(account_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Account not found")

    positions = await adapter.get_positions()
    closed = []

    for position in positions:
        if position.quantity != 0:
            side = "sell" if position.quantity > 0 else "buy"
            order = await adapter.create_order(
                symbol=position.symbol,
                side=side,
                type="market",
                quantity=abs(position.quantity),
            )
            closed.append({
                "symbol": position.symbol.unified,
                "order_id": order.id,
            })

    return {
        "message": f"Closed {len(closed)} positions",
        "closed": closed,
    }