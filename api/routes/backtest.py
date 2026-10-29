"""
Backtest API routes.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from cryptobot.backtest.engine import BacktestEngine, BacktestConfig, run_vectorized_backtest
from cryptobot.backtest.optimizer import BacktestOptimizer, create_param_space
from cryptobot.backtest.validation import WalkForwardValidator
from cryptobot.backtest.report import generate_backtest_report
from cryptobot.data.fetcher import get_fetcher
from cryptobot.data.models import Symbol, MarketType

router = APIRouter()


# Request/Response models
class BacktestRequest(BaseModel):
    symbols: list[str]
    start_date: str | None = None
    end_date: str | None = None
    timeframe: str = "1h"
    initial_cash: float = 100000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    strategy_type: str = "trend_follow"
    strategy_params: dict[str, Any] = {}


class BacktestResponse(BaseModel):
    backtest_id: str
    status: str
    metrics: dict[str, float] | None = None
    equity_curve: list[dict] | None = None
    trades: list[dict] | None = None
    created_at: str


class OptimizationRequest(BaseModel):
    symbols: list[str]
    param_space: dict[str, Any]
    metric: str = "sharpe_ratio"
    direction: str = "maximize"
    method: str = "random"  # random, bayesian, grid
    n_trials: int = 50
    start_date: str | None = None
    end_date: str | None = None
    timeframe: str = "1h"


class WalkForwardRequest(BaseModel):
    symbols: list[str]
    train_window: int = 252
    test_window: int = 60
    step: int = 21
    strategy_type: str = "trend_follow"
    strategy_params: dict[str, Any] = {}


# In-memory storage (replace with database)
_backtest_results: dict[str, dict] = {}


@router.post("", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
):
    """Run a backtest."""
    import uuid
    backtest_id = str(uuid.uuid4())[:8]

    # Initialize result
    _backtest_results[backtest_id] = {
        "backtest_id": backtest_id,
        "status": "running",
        "request": request.model_dump(),
        "created_at": datetime.utcnow().isoformat(),
    }

    # Run in background
    background_tasks.add_task(_run_backtest_task, backtest_id, request)

    return BacktestResponse(
        backtest_id=backtest_id,
        status="running",
        created_at=datetime.utcnow().isoformat(),
    )


async def _run_backtest_task(backtest_id: str, request: BacktestRequest):
    """Background task to run backtest."""
    try:
        fetcher = await get_fetcher()

        # Fetch data for all symbols
        price_data = {}
        for symbol_str in request.symbols:
            symbol = Symbol.from_unified(symbol_str) if ":" in symbol_str else Symbol(
                base=symbol_str.split("/")[0] if "/" in symbol_str else symbol_str,
                quote="USDT",
                exchange="binance",
                market_type=MarketType.LINEAR,
            )

            start = datetime.fromisoformat(request.start_date) if request.start_date else None
            end = datetime.fromisoformat(request.end_date) if request.end_date else None

            candles = await fetcher.fetch_candles(
                symbol,
                timeframe=request.timeframe,
                start=start,
                end=end,
                limit=5000,
            )

            if candles:
                df = pd.DataFrame([c.to_dict() for c in candles])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp").sort_index()
                price_data[symbol_str] = df["close"]

        if not price_data:
            _backtest_results[backtest_id]["status"] = "failed"
            _backtest_results[backtest_id]["error"] = "No data available"
            return

        prices = pd.DataFrame(price_data)

        # Generate signals based on strategy
        signals = await _generate_strategy_signals(
            prices,
            request.strategy_type,
            request.strategy_params,
        )

        # Run backtest
        config = BacktestConfig(
            initial_cash=request.initial_cash,
            commission=request.commission,
            slippage=request.slippage,
        )

        result = run_vectorized_backtest(
            prices=prices,
            signals=signals,
            initial_cash=request.initial_cash,
            commission=request.commission,
            slippage=request.slippage,
        )

        # Store results
        _backtest_results[backtest_id].update({
            "status": "completed",
            "metrics": result.metrics,
            "equity_curve": result.equity_curve.to_dict(),
            "trades": [t.__dict__ if hasattr(t, '__dict__') else t for t in result.trades],
            "completed_at": datetime.utcnow().isoformat(),
        })

    except Exception as e:
        _backtest_results[backtest_id]["status"] = "failed"
        _backtest_results[backtest_id]["error"] = str(e)


async def _generate_strategy_signals(
    prices: pd.DataFrame,
    strategy_type: str,
    params: dict,
) -> pd.DataFrame:
    """Generate signals for strategy."""
    import talib

    signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)

    for col in prices.columns:
        close = prices[col].values

        if strategy_type == "trend_follow":
            fast = params.get("fast_period", 10)
            slow = params.get("slow_period", 30)
            fast_ma = talib.EMA(close, timeperiod=fast)
            slow_ma = talib.EMA(close, timeperiod=slow)
            signal = np.where(fast_ma > slow_ma, 1, np.where(fast_ma < slow_ma, -1, 0))

        elif strategy_type == "mean_reversion":
            bb_period = params.get("bb_period", 20)
            rsi_period = params.get("rsi_period", 14)
            rsi = talib.RSI(close, timeperiod=rsi_period)
            upper, middle, lower = talib.BBANDS(close, timeperiod=bb_period)
            signal = np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0))

        elif strategy_type == "momentum":
            period = params.get("period", 14)
            roc = talib.ROC(close, timeperiod=period)
            signal = np.where(roc > 0, 1, np.where(roc < 0, -1, 0))

        else:
            signal = np.zeros(len(close))

        signals[col] = signal

    return signals


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(backtest_id: str):
    """Get backtest result."""
    if backtest_id not in _backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")

    result = _backtest_results[backtest_id]
    return BacktestResponse(
        backtest_id=backtest_id,
        status=result.get("status", "unknown"),
        metrics=result.get("metrics"),
        equity_curve=result.get("equity_curve"),
        trades=result.get("trades"),
        created_at=result.get("created_at", ""),
    )


@router.get("/{backtest_id}/report")
async def get_backtest_report(backtest_id: str):
    """Get full backtest report as HTML."""
    if backtest_id not in _backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")

    result = _backtest_results[backtest_id]
    if result.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Backtest not completed")

    # Generate report
    import pandas as pd
    equity_curve = pd.Series(result["equity_curve"])
    trades = result.get("trades", [])

    report = generate_backtest_report(
        metrics=result["metrics"],
        equity_curve=equity_curve,
        trades=trades,
    )

    return report.to_html()


@router.post("/optimize", response_model=dict)
async def optimize_strategy(request: OptimizationRequest):
    """Run parameter optimization."""
    # This would run the optimizer
    # For now, return mock response
    return {
        "optimization_id": "opt_123",
        "status": "running",
        "best_params": {
            "fast_period": 12,
            "slow_period": 26,
        },
        "best_score": 2.45,
    }


@router.post("/walkforward", response_model=dict)
async def run_walkforward(request: WalkForwardRequest):
    """Run walk-forward validation."""
    return {
        "walkforward_id": "wf_123",
        "status": "running",
        "windows": 10,
    }


@router.get("", response_model=list[BacktestResponse])
async def list_backtests():
    """List all backtests."""
    return [
        BacktestResponse(
            backtest_id=k,
            status=v.get("status", "unknown"),
            metrics=v.get("metrics"),
            created_at=v.get("created_at", ""),
        )
        for k, v in _backtest_results.items()
    ]


@router.delete("/{backtest_id}")
async def delete_backtest(backtest_id: str):
    """Delete backtest result."""
    if backtest_id not in _backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    del _backtest_results[backtest_id]
    return {"message": "Backtest deleted"}