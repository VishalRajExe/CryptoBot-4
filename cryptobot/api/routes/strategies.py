"""
Strategy API routes.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from cryptobot.strategy.generator import SignalEngine, StrategySignal
from cryptobot.data.models import Symbol, MarketType
from cryptobot.data.fetcher import get_fetcher
from cryptobot.config.settings import settings

router = APIRouter()


# Request/Response models
class StrategyCreate(BaseModel):
    name: str
    type: str
    parameters: dict[str, Any] = {}
    symbols: list[str] = []
    enabled: bool = True


class StrategyResponse(BaseModel):
    id: str
    name: str
    type: str
    parameters: dict[str, Any]
    symbols: list[str]
    enabled: bool
    created_at: str
    performance: dict[str, float] | None = None


class SignalRequest(BaseModel):
    symbols: list[str]
    timeframe: str = "1h"
    lookback: int = 500
    enabled_strategies: list[str] | None = None


class SignalResponse(BaseModel):
    symbol: str
    timestamp: str
    direction: str
    strength: float
    signal_type: str
    source: str
    metadata: dict[str, Any]


# In-memory strategy store (replace with database in production)
_strategies: dict[str, dict] = {}


@router.get("", response_model=list[StrategyResponse])
async def list_strategies():
    """List all strategies."""
    return [
        StrategyResponse(id=k, **v)
        for k, v in _strategies.items()
    ]


@router.post("", response_model=StrategyResponse)
async def create_strategy(strategy: StrategyCreate):
    """Create a new strategy."""
    import uuid
    strategy_id = str(uuid.uuid4())[:8]

    _strategies[strategy_id] = {
        "name": strategy.name,
        "type": strategy.type,
        "parameters": strategy.parameters,
        "symbols": strategy.symbols,
        "enabled": strategy.enabled,
        "created_at": datetime.utcnow().isoformat(),
        "performance": {},
    }

    return StrategyResponse(id=strategy_id, **_strategies[strategy_id])


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str):
    """Get strategy by ID."""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyResponse(id=strategy_id, **_strategies[strategy_id])


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(strategy_id: str, strategy: StrategyCreate):
    """Update strategy."""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")

    _strategies[strategy_id].update({
        "name": strategy.name,
        "type": strategy.type,
        "parameters": strategy.parameters,
        "symbols": strategy.symbols,
        "enabled": strategy.enabled,
    })

    return StrategyResponse(id=strategy_id, **_strategies[strategy_id])


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """Delete strategy."""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    del _strategies[strategy_id]
    return {"message": "Strategy deleted"}


@router.post("/{strategy_id}/enable")
async def enable_strategy(strategy_id: str):
    """Enable strategy."""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    _strategies[strategy_id]["enabled"] = True
    return {"message": "Strategy enabled"}


@router.post("/{strategy_id}/disable")
async def disable_strategy(strategy_id: str):
    """Disable strategy."""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")
    _strategies[strategy_id]["enabled"] = False
    return {"message": "Strategy disabled"}


@router.post("/signals", response_model=list[SignalResponse])
async def generate_signals(request: SignalRequest):
    """Generate trading signals for symbols."""
    fetcher = await get_fetcher()
    signal_engine = SignalEngine()

    results = await signal_engine.generate(
        symbols=request.symbols,
        timeframe=request.timeframe,
        lookback=request.lookback,
        enabled_strategies=request.enabled_strategies,
    )

    all_signals = []
    for symbol, signals in results.items():
        for signal in signals:
            all_signals.append(SignalResponse(
                symbol=signal.symbol,
                timestamp=signal.timestamp.isoformat(),
                direction=signal.direction,
                strength=signal.strength,
                signal_type=signal.signal_type,
                source=signal.source,
                metadata=signal.metadata,
            ))

    return all_signals


@router.get("/{strategy_id}/performance")
async def get_strategy_performance(strategy_id: str):
    """Get strategy performance metrics."""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Would fetch from backtest results
    return _strategies[strategy_id].get("performance", {})


@router.post("/{strategy_id}/backtest")
async def run_strategy_backtest(
    strategy_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_cash: float = 100000.0,
):
    """Run backtest for strategy."""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy = _strategies[strategy_id]

    # This would run the actual backtest
    # For now, return mock response
    return {
        "strategy_id": strategy_id,
        "status": "completed",
        "metrics": {
            "total_return_pct": 15.5,
            "sharpe_ratio": 1.8,
            "max_drawdown_pct": -8.2,
            "win_rate_pct": 58.3,
        },
    }