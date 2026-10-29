"""
Backtest reporting and visualization.
Adapted from vectorbt's plotting and freqtrade's plot commands.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class BacktestReport:
    """Backtest report container."""

    metrics: dict[str, float]
    equity_curve: pd.Series
    trades: list[dict]
    positions: pd.DataFrame | None = None
    signals: pd.DataFrame | None = None
    config: dict[str, Any] | None = None
    generated_at: datetime = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.utcnow()

    def to_html(self, output_path: str | Path | None = None) -> str:
        """Generate HTML report."""
        html = self._generate_html()

        if output_path:
            Path(output_path).write_text(html)
            logger.info(f"Report saved to {output_path}")

        return html

    def to_json(self, output_path: str | Path | None = None) -> str:
        """Generate JSON report."""
        data = {
            "generated_at": self.generated_at.isoformat(),
            "metrics": self.metrics,
            "config": self.config,
            "trade_count": len(self.trades),
        }

        # Add equity curve (sampled)
        if len(self.equity_curve) > 1000:
            equity_sampled = self.equity_curve.iloc[::len(self.equity_curve)//1000]
        else:
            equity_sampled = self.equity_curve
        data["equity_curve"] = equity_sampled.to_dict()

        json_str = json.dumps(data, indent=2, default=str)

        if output_path:
            Path(output_path).write_text(json_str)
            logger.info(f"JSON report saved to {output_path}")

        return json_str

    def _generate_html(self) -> str:
        """Generate HTML report with embedded plots."""
        # Create plots
        equity_fig = self._plot_equity()
        drawdown_fig = self._plot_drawdown()
        returns_fig = self._plot_returns()
        trades_fig = self._plot_trades()

        # Convert to HTML
        equity_html = equity_fig.to_html(include_plotlyjs="cdn", div_id="equity")
        drawdown_html = drawdown_fig.to_html(include_plotlyjs=False, div_id="drawdown")
        returns_html = returns_fig.to_html(include_plotlyjs=False, div_id="returns")
        trades_html = trades_fig.to_html(include_plotlyjs=False, div_id="trades")

        # Metrics table
        metrics_rows = ""
        for key, value in self.metrics.items():
            if isinstance(value, float):
                metrics_rows += f"<tr><td>{key}</td><td>{value:.4f}</td></tr>"
            else:
                metrics_rows += f"<tr><td>{key}</td><td>{value}</td></tr>"

        # Trade table
        trades_rows = ""
        for trade in self.trades[:50]:  # Limit to 50
            trades_rows += f"""
            <tr>
                <td>{trade.get('entry_time', '')}</td>
                <td>{trade.get('symbol', '')}</td>
                <td>{trade.get('side', '')}</td>
                <td>{trade.get('entry_price', 0):.4f}</td>
                <td>{trade.get('exit_price', 0):.4f}</td>
                <td>{trade.get('pnl_pct', 0):.2f}%</td>
                <td>{trade.get('holding_period', 0):.1f}h</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Backtest Report - {self.generated_at.strftime('%Y-%m-%d %H:%M')}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
                h1 {{ color: #1a1a2e; }}
                h2 {{ color: #16213e; border-bottom: 2px solid #e94560; padding-bottom: 10px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #1a1a2e; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .metric-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #e94560; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #1a1a2e; }}
                .metric-label {{ font-size: 14px; color: #666; }}
            </style>
        </head>
        <body>
            <h1>Backtest Report</h1>
            <p>Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>

            <h2>Key Metrics</h2>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{self.metrics.get('total_return_pct', 0):.2f}%</div>
                    <div class="metric-label">Total Return</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.metrics.get('sharpe_ratio', 0):.2f}</div>
                    <div class="metric-label">Sharpe Ratio</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.metrics.get('max_drawdown_pct', 0):.2f}%</div>
                    <div class="metric-label">Max Drawdown</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.metrics.get('win_rate_pct', 0):.1f}%</div>
                    <div class="metric-label">Win Rate</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.metrics.get('profit_factor', 0):.2f}</div>
                    <div class="metric-label">Profit Factor</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.metrics.get('total_trades', 0)}</div>
                    <div class="metric-label">Total Trades</div>
                </div>
            </div>

            <h2>Equity Curve</h2>
            {equity_html}

            <h2>Drawdown</h2>
            {drawdown_html}

            <h2>Monthly Returns</h2>
            {returns_html}

            <h2>Trade Distribution</h2>
            {trades_html}

            <h2>All Metrics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                {metrics_rows}
            </table>

            <h2>Recent Trades</h2>
            <table>
                <tr><th>Entry Time</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>PnL %</th><th>Hold (h)</th></tr>
                {trades_rows}
            </table>
        </body>
        </html>
        """
        return html

    def _plot_equity(self) -> go.Figure:
        """Plot equity curve."""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=self.equity_curve.index,
            y=self.equity_curve.values,
            mode="lines",
            name="Equity",
            line=dict(color="#1a1a2e", width=2),
        ))
        fig.update_layout(
            title="Equity Curve",
            xaxis_title="Date",
            yaxis_title="Equity ($)",
            template="plotly_white",
            height=400,
        )
        return fig

    def _plot_drawdown(self) -> go.Figure:
        """Plot drawdown."""
        cummax = self.equity_curve.cummax()
        drawdown = (self.equity_curve - cummax) / cummax * 100

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode="lines",
            name="Drawdown",
            fill="tozeroy",
            line=dict(color="#e94560", width=1),
            fillcolor="rgba(233, 69, 96, 0.3)",
        ))
        fig.update_layout(
            title="Drawdown (%)",
            xaxis_title="Date",
            yaxis_title="Drawdown (%)",
            template="plotly_white",
            height=300,
        )
        return fig

    def _plot_returns(self) -> go.Figure:
        """Plot monthly returns heatmap."""
        monthly = self.equity_curve.resample("ME").last().pct_change().dropna() * 100
        if len(monthly) < 2:
            return go.Figure()

        # Create pivot table
        monthly_df = pd.DataFrame({"return": monthly})
        monthly_df["year"] = monthly_df.index.year
        monthly_df["month"] = monthly_df.index.month
        pivot = monthly_df.pivot(index="year", columns="month", values="return")

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
            y=[str(y) for y in pivot.index],
            colorscale="RdYlGn",
            zmid=0,
            text=np.round(pivot.values, 1),
            texttemplate="%{text}%",
            textfont={"size": 10},
        ))
        fig.update_layout(
            title="Monthly Returns (%)",
            template="plotly_white",
            height=400,
        )
        return fig

    def _plot_trades(self) -> go.Figure:
        """Plot trade distribution."""
        if not self.trades:
            return go.Figure()

        pnls = [t.get("pnl_pct", 0) for t in self.trades]

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=pnls,
            nbinsx=30,
            name="Trade PnL %",
            marker_color="#1a1a2e",
            opacity=0.7,
        ))
        fig.add_vline(x=0, line_dash="dash", line_color="#e94560")
        fig.update_layout(
            title="Trade PnL Distribution",
            xaxis_title="PnL (%)",
            yaxis_title="Frequency",
            template="plotly_white",
            height=300,
        )
        return fig


def generate_backtest_report(
    metrics: dict[str, float],
    equity_curve: pd.Series,
    trades: list[dict],
    positions: pd.DataFrame | None = None,
    signals: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
) -> BacktestReport:
    """Generate and save backtest report."""
    report = BacktestReport(
        metrics=metrics,
        equity_curve=equity_curve,
        trades=trades,
        positions=positions,
        signals=signals,
        config=config,
    )

    if output_path:
        report.to_html(output_path)
        # Also save JSON
        json_path = Path(output_path).with_suffix(".json")
        report.to_json(json_path)

    return report


def save_equity_curve_plot(
    equity_curve: pd.Series,
    output_path: str | Path,
    benchmark: pd.Series | None = None,
) -> None:
    """Save equity curve plot as image."""
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(equity_curve.index, equity_curve.values, label="Strategy", color="#1a1a2e", linewidth=2)

    if benchmark is not None:
        # Align and scale benchmark
        bench_aligned = benchmark.reindex(equity_curve.index).ffill()
        bench_scaled = bench_aligned / bench_aligned.iloc[0] * equity_curve.iloc[0]
        ax.plot(bench_aligned.index, bench_scaled.values, label="Benchmark", color="#e94560", linewidth=1, alpha=0.7)

    ax.set_title("Equity Curve")
    ax.set_ylabel("Equity ($)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def save_drawdown_plot(
    equity_curve: pd.Series,
    output_path: str | Path,
) -> None:
    """Save drawdown plot as image."""
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax * 100

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="#e94560", alpha=0.3)
    ax.plot(drawdown.index, drawdown.values, color="#e94560", linewidth=1)
    ax.set_title("Drawdown (%)")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def create_tearsheet(
    equity_curve: pd.Series,
    trades: list[dict],
    metrics: dict[str, float],
    benchmark: pd.Series | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Path]:
    """Create full tearsheet with all plots."""
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    files = {}

    # Equity curve
    equity_path = output_dir / "equity_curve.png" if output_dir else None
    save_equity_curve_plot(equity_curve, equity_path, benchmark)
    files["equity_curve"] = equity_path

    # Drawdown
    dd_path = output_dir / "drawdown.png" if output_dir else None
    save_drawdown_plot(equity_curve, dd_path)
    files["drawdown"] = dd_path

    # Monthly returns heatmap
    monthly_path = output_dir / "monthly_returns.png" if output_dir else None
    _save_monthly_heatmap(equity_curve, monthly_path)
    files["monthly_returns"] = monthly_path

    # Trade distribution
    trades_path = output_dir / "trade_distribution.png" if output_dir else None
    _save_trade_distribution(trades, trades_path)
    files["trade_distribution"] = trades_path

    return files


def _save_monthly_heatmap(equity_curve: pd.Series, output_path: Path | None) -> None:
    """Save monthly returns heatmap."""
    monthly = equity_curve.resample("ME").last().pct_change().dropna() * 100
    if len(monthly) < 2:
        return

    monthly_df = pd.DataFrame({"return": monthly})
    monthly_df["year"] = monthly_df.index.year
    monthly_df["month"] = monthly_df.index.month
    pivot = monthly_df.pivot(index="year", columns="month", values="return")

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn", vmin=-10, vmax=10)
    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(y) for y in pivot.index])
    ax.set_title("Monthly Returns (%)")

    # Add text annotations
    for i in range(len(pivot.index)):
        for j in range(12):
            val = pivot.iloc[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=8)

    plt.colorbar(im, ax=ax)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def _save_trade_distribution(trades: list[dict], output_path: Path | None) -> None:
    """Save trade PnL distribution."""
    if not trades:
        return

    pnls = [t.get("pnl_pct", 0) for t in trades]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(pnls, bins=30, color="#1a1a2e", alpha=0.7, edgecolor="white")
    ax.axvline(x=0, color="#e94560", linestyle="--", linewidth=2)
    ax.set_title("Trade PnL Distribution")
    ax.set_xlabel("PnL (%)")
    ax.set_ylabel("Frequency")
    ax.grid(True, alpha=0.3)

    # Add stats
    mean_pnl = np.mean(pnls)
    median_pnl = np.median(pnls)
    ax.text(0.02, 0.98, f"Mean: {mean_pnl:.2f}%\nMedian: {median_pnl:.2f}%",
            transform=ax.transAxes, verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()