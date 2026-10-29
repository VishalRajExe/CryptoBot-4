"""
Comprehensive backtest metrics.
Adapted from vectorbt's metrics and backtesting.py's stats.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_metrics(
    equity_curve: pd.Series,
    trades: list[dict] | None = None,
    benchmark: pd.Series | None = None,
    risk_free_rate: float = 0.02,
) -> dict[str, float]:
    """
    Calculate comprehensive backtest metrics.

    Args:
        equity_curve: Portfolio equity over time
        trades: List of trade dicts
        benchmark: Benchmark equity curve (optional)
        risk_free_rate: Annual risk-free rate

    Returns:
        Dictionary of metrics
    """
    if len(equity_curve) < 2:
        return {}

    returns = equity_curve.pct_change().dropna()
    n_periods = len(returns)

    # Time period
    start = equity_curve.index[0]
    end = equity_curve.index[-1]
    days = (end - start).days
    years = days / 365.25

    # Basic returns
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100
    cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / years) - 1 if years > 0 else 0

    # Volatility
    vol = returns.std() * np.sqrt(252) if n_periods > 0 else 0

    # Risk-adjusted
    sharpe = (returns.mean() * 252 - risk_free_rate) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
    sortino = _sortino_ratio(returns, risk_free_rate)
    calmar = _calmar_ratio(equity_curve)

    # Drawdown
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax * 100
    max_dd = drawdown.min()
    max_dd_duration = _max_drawdown_duration(drawdown)
    avg_dd = drawdown[drawdown < 0].mean() if (drawdown < 0).any() else 0

    # Tail risk
    var_95 = np.percentile(returns, 5) * 100
    var_99 = np.percentile(returns, 1) * 100
    cvar_95 = returns[returns <= np.percentile(returns, 5)].mean() * 100
    cvar_99 = returns[returns <= np.percentile(returns, 1)].mean() * 100

    # Skew/Kurtosis
    skew = returns.skew()
    kurtosis = returns.kurtosis()

    # Benchmark comparison
    alpha = beta = information_ratio = treynor = 0
    if benchmark is not None:
        bench_returns = benchmark.pct_change().dropna()
        common_idx = returns.index.intersection(bench_returns.index)
        if len(common_idx) > 10:
            r = returns.loc[common_idx]
            b = bench_returns.loc[common_idx]
            beta = np.cov(r, b)[0, 1] / np.var(b) if np.var(b) > 0 else 0
            alpha = (r.mean() * 252) - risk_free_rate - beta * (b.mean() * 252 - risk_free_rate)
            excess = r - b
            information_ratio = excess.mean() / excess.std() * np.sqrt(252) if excess.std() > 0 else 0
            treynor = (r.mean() * 252 - risk_free_rate) / beta if beta != 0 else 0

    # Trade metrics
    trade_metrics = {}
    if trades:
        trade_metrics = _calculate_trade_metrics(trades)

    return {
        # Returns
        "total_return_pct": total_return,
        "cagr_pct": cagr * 100,
        "annual_volatility_pct": vol * 100,

        # Risk-adjusted
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "treynor_ratio": treynor,
        "information_ratio": information_ratio,

        # Drawdown
        "max_drawdown_pct": max_dd,
        "max_drawdown_duration_days": max_dd_duration,
        "avg_drawdown_pct": avg_dd,
        "recovery_factor": total_return / abs(max_dd) if max_dd != 0 else 0,

        # Tail risk
        "var_95_pct": var_95,
        "var_99_pct": var_99,
        "cvar_95_pct": cvar_95,
        "cvar_99_pct": cvar_99,

        # Distribution
        "skewness": skew,
        "kurtosis": kurtosis,

        # Benchmark
        "alpha_pct": alpha * 100,
        "beta": beta,
        "information_ratio": information_ratio,

        # Trade stats
        **trade_metrics,

        # Misc
        "n_periods": n_periods,
        "days": days,
        "years": years,
    }


def _sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sortino ratio."""
    excess = returns.mean() * 252 - risk_free_rate
    downside = returns[returns < 0].std() * np.sqrt(252)
    return excess / downside if downside > 0 else 0


def _calmar_ratio(equity_curve: pd.Series) -> float:
    """Calculate Calmar ratio."""
    years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
    if years == 0:
        return 0
    cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / years) - 1
    cummax = equity_curve.cummax()
    max_dd = ((equity_curve - cummax) / cummax).min()
    return cagr / abs(max_dd) if max_dd != 0 else 0


def _max_drawdown_duration(drawdown: pd.Series) -> int:
    """Calculate maximum drawdown duration in days."""
    in_dd = drawdown < 0
    if not in_dd.any():
        return 0

    # Find consecutive drawdown periods
    dd_groups = (in_dd != in_dd.shift()).cumsum()
    durations = in_dd.groupby(dd_groups).sum()
    return int(durations.max())


def _calculate_trade_metrics(trades: list[dict]) -> dict[str, float]:
    """Calculate trade-level metrics."""
    if not trades:
        return {}

    pnls = [t.get("pnl", 0) for t in trades]
    pnl_pcts = [t.get("pnl_pct", 0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_pcts = [p for p in pnl_pcts if p > 0]
    loss_pcts = [p for p in pnl_pcts if p <= 0]

    total_trades = len(trades)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total_trades * 100 if total_trades > 0 else 0

    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    avg_win_pct = np.mean(win_pcts) if win_pcts else 0
    avg_loss_pct = np.mean(loss_pcts) if loss_pcts else 0

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    expectancy = np.mean(pnls) if pnls else 0
    expectancy_pct = np.mean(pnl_pcts) if pnl_pcts else 0

    # Best/worst
    best_trade = max(pnls) if pnls else 0
    worst_trade = min(pnls) if pnls else 0
    best_pct = max(pnl_pcts) if pnl_pcts else 0
    worst_pct = min(pnl_pcts) if pnl_pcts else 0

    # Durations
    durations = [t.get("holding_period", 0) for t in trades]
    avg_duration = np.mean(durations) if durations else 0
    max_duration = max(durations) if durations else 0

    # Consecutive wins/losses
    consec_wins = _max_consecutive(pnls, lambda x: x > 0)
    consec_losses = _max_consecutive(pnls, lambda x: x <= 0)

    return {
        "total_trades": total_trades,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "expectancy_pct": expectancy_pct,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "best_trade_pct": best_pct,
        "worst_trade_pct": worst_pct,
        "avg_holding_hours": avg_duration,
        "max_holding_hours": max_duration,
        "max_consec_wins": consec_wins,
        "max_consec_losses": consec_losses,
    }


def _max_consecutive(values: list, predicate: callable) -> int:
    """Calculate max consecutive values satisfying predicate."""
    max_consec = 0
    current = 0
    for v in values:
        if predicate(v):
            current += 1
            max_consec = max(max_consec, current)
        else:
            current = 0
    return max_consec


def monthly_returns(equity_curve: pd.Series) -> pd.DataFrame:
    """Calculate monthly returns table."""
    if len(equity_curve) < 2:
        return pd.DataFrame()

    returns = equity_curve.resample("ME").last().pct_change().dropna() * 100
    returns.index = returns.index.to_period("M")

    # Pivot to year/month table
    table = returns.unstack().T
    table.columns = [str(c) for c in table.columns]

    # Add yearly totals
    table["Year"] = table.sum(axis=1)
    table.loc["Total"] = table.sum()

    return table


def rolling_metrics(
    equity_curve: pd.Series,
    window: int = 252,
) -> pd.DataFrame:
    """Calculate rolling metrics."""
    returns = equity_curve.pct_change().dropna()

    rolling = pd.DataFrame(index=returns.index)
    rolling["rolling_sharpe"] = (
        returns.rolling(window).mean() * 252 /
        (returns.rolling(window).std() * np.sqrt(252) + 1e-8)
    )
    rolling["rolling_vol"] = returns.rolling(window).std() * np.sqrt(252) * 100
    rolling["rolling_return"] = returns.rolling(window).mean() * 252 * 100

    cummax = equity_curve.cummax()
    dd = (equity_curve - cummax) / cummax * 100
    rolling["rolling_max_dd"] = dd.rolling(window).min()

    return rolling.dropna()


def regime_metrics(
    equity_curve: pd.Series,
    regime_indicator: pd.Series,
) -> dict[str, dict[str, float]]:
    """Calculate metrics per regime."""
    returns = equity_curve.pct_change().dropna()
    common = returns.index.intersection(regime_indicator.index)
    returns = returns.loc[common]
    regimes = regime_indicator.loc[common]

    metrics = {}
    for regime in regimes.unique():
        mask = regimes == regime
        if mask.sum() < 10:
            continue
        r = returns[mask]
        metrics[str(regime)] = {
            "return_pct": (1 + r).prod() - 1 * 100,
            "vol_pct": r.std() * np.sqrt(252) * 100,
            "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0,
            "n_periods": int(mask.sum()),
        }

    return metrics