"""
Backtesting package.
"""

from cryptobot.backtest.engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    TradeRecord,
    run_vectorized_backtest,
)
from cryptobot.backtest.event_engine import (
    Strategy,
    SimulatedBroker,
    EventBacktestEngine,
    run_event_backtest,
)
from cryptobot.backtest.validation import (
    WalkForwardValidator,
    MonteCarloValidator,
    CPCVValidator,
    SyntheticDataGenerator,
    WalkForwardResult,
)
from cryptobot.backtest.metrics import (
    calculate_metrics,
    monthly_returns,
    rolling_metrics,
    regime_metrics,
)
from cryptobot.backtest.report import (
    BacktestReport,
    generate_backtest_report,
    save_equity_curve_plot,
    save_drawdown_plot,
    create_tearsheet,
)
from cryptobot.backtest.optimizer import (
    BacktestOptimizer,
    OptimizationResult,
    create_param_space,
)

__all__ = [
    # Engine
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "TradeRecord",
    "run_vectorized_backtest",
    # Event engine
    "Strategy",
    "SimulatedBroker",
    "EventBacktestEngine",
    "run_event_backtest",
    # Validation
    "WalkForwardValidator",
    "MonteCarloValidator",
    "CPCVValidator",
    "SyntheticDataGenerator",
    "WalkForwardResult",
    # Metrics
    "calculate_metrics",
    "monthly_returns",
    "rolling_metrics",
    "regime_metrics",
    # Reporting
    "BacktestReport",
    "generate_backtest_report",
    "save_equity_curve_plot",
    "save_drawdown_plot",
    "create_tearsheet",
    # Optimization
    "BacktestOptimizer",
    "OptimizationResult",
    "create_param_space",
]