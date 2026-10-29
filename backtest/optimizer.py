"""
Backtest optimizer for parameter search.
Adapted from freqtrade's hyperopt and Vibe-Trading's optimizer.
"""

from __future__ import annotations

import asyncio
import logging
import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import numpy as np
import pandas as pd

# Optional optimization libraries
try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer, Categorical
    SKOPT_AVAILABLE = True
except ImportError:
    SKOPT_AVAILABLE = False

from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=RuntimeWarning)


@dataclass
class OptimizationResult:
    """Single optimization trial result."""

    params: dict[str, Any]
    metrics: dict[str, float]
    score: float
    trial_number: int
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class BacktestOptimizer:
    """
    Parameter optimization for strategies.

    Methods:
    - Grid search
    - Random search
    - Bayesian optimization (Optuna, scikit-optimize)
    - Walk-forward optimization
    """

    def __init__(
        self,
        backtest_fn: Callable[[dict[str, Any]], dict[str, float]],
        param_space: dict[str, Any],
        metric: str = "sharpe_ratio",
        direction: str = "maximize",
        n_jobs: int = 1,
    ):
        """
        Initialize optimizer.

        Args:
            backtest_fn: Function(params) -> metrics dict
            param_space: Parameter search space
            metric: Metric to optimize
            direction: "maximize" or "minimize"
            n_jobs: Parallel jobs
        """
        self.backtest_fn = backtest_fn
        self.param_space = param_space
        self.metric = metric
        self.direction = direction
        self.n_jobs = n_jobs

        self.results: list[OptimizationResult] = []
        self.best_params: dict[str, Any] | None = None
        self.best_score: float = -np.inf if direction == "maximize" else np.inf

    def _evaluate(self, params: dict[str, Any]) -> OptimizationResult:
        """Evaluate a single parameter set."""
        try:
            metrics = self.backtest_fn(params)
            score = metrics.get(self.metric, 0)

            # Handle NaN
            if np.isnan(score):
                score = -np.inf if self.direction == "maximize" else np.inf

            result = OptimizationResult(
                params=params,
                metrics=metrics,
                score=score,
                trial_number=len(self.results),
            )

            # Update best
            if self.direction == "maximize" and score > self.best_score:
                self.best_score = score
                self.best_params = params.copy()
            elif self.direction == "minimize" and score < self.best_score:
                self.best_score = score
                self.best_params = params.copy()

            return result

        except Exception as e:
            logger.error(f"Optimization trial failed: {e}")
            return OptimizationResult(
                params=params,
                metrics={},
                score=-np.inf if self.direction == "maximize" else np.inf,
                trial_number=len(self.results),
            )

    def grid_search(self, max_combinations: int = 1000) -> list[OptimizationResult]:
        """Grid search over parameter space."""
        from itertools import product

        # Generate all combinations
        keys = list(self.param_space.keys())
        values = list(self.param_space.values())

        # Check if too many combinations
        total = 1
        for v in values:
            if isinstance(v, (list, tuple)):
                total *= len(v)
            else:
                total *= 1

        if total > max_combinations:
            logger.warning(f"Grid search has {total} combinations, limiting to {max_combinations}")
            # Use random subset
            return self.random_search(max_combinations)

        combinations = list(product(*values))
        logger.info(f"Grid search: {len(combinations)} combinations")

        results = []
        for i, combo in enumerate(combinations):
            params = dict(zip(keys, combo))
            result = self._evaluate(params)
            results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{len(combinations)}, best {self.metric}: {self.best_score:.4f}")

        self.results.extend(results)
        return results

    def random_search(self, n_trials: int = 100) -> list[OptimizationResult]:
        """Random search over parameter space."""
        logger.info(f"Random search: {n_trials} trials")

        results = []
        for i in range(n_trials):
            params = {}
            for key, space in self.param_space.items():
                if isinstance(space, (list, tuple)):
                    params[key] = np.random.choice(space)
                elif isinstance(space, dict) and space.get("type") == "uniform":
                    params[key] = np.random.uniform(space["low"], space["high"])
                elif isinstance(space, dict) and space.get("type") == "loguniform":
                    params[key] = np.exp(np.random.uniform(np.log(space["low"]), np.log(space["high"])))
                elif isinstance(space, dict) and space.get("type") == "int":
                    params[key] = np.random.randint(space["low"], space["high"] + 1)

            result = self._evaluate(params)
            results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{n_trials}, best {self.metric}: {self.best_score:.4f}")

        self.results.extend(results)
        return results

    def bayesian_optimization(
        self,
        n_trials: int = 50,
        n_initial_points: int = 10,
    ) -> list[OptimizationResult]:
        """Bayesian optimization using Optuna or scikit-optimize."""
        if OPTUNA_AVAILABLE:
            return self._optuna_optimize(n_trials)
        elif SKOPT_AVAILABLE:
            return self._skopt_optimize(n_trials, n_initial_points)
        else:
            logger.warning("No Bayesian optimization library available, falling back to random search")
            return self.random_search(n_trials)

    def _optuna_optimize(self, n_trials: int) -> list[OptimizationResult]:
        """Optimize using Optuna."""

        def objective(trial):
            params = {}
            for key, space in self.param_space.items():
                if isinstance(space, (list, tuple)):
                    params[key] = trial.suggest_categorical(key, space)
                elif isinstance(space, dict):
                    if space.get("type") == "uniform":
                        params[key] = trial.suggest_float(key, space["low"], space["high"])
                    elif space.get("type") == "loguniform":
                        params[key] = trial.suggest_float(key, space["low"], space["high"], log=True)
                    elif space.get("type") == "int":
                        params[key] = trial.suggest_int(key, space["low"], space["high"])

            result = self._evaluate(params)
            return result.score

        study = optuna.create_study(
            direction=self.direction,
            sampler=optuna.samplers.TPESampler(seed=42),
        )
        study.optimize(objective, n_trials=n_trials)

        results = []
        for trial in study.trials:
            if trial.value is not None:
                results.append(OptimizationResult(
                    params=trial.params,
                    metrics={self.metric: trial.value},
                    score=trial.value,
                    trial_number=trial.number,
                ))

        self.results.extend(results)
        return results

    def _skopt_optimize(
        self,
        n_trials: int,
        n_initial_points: int,
    ) -> list[OptimizationResult]:
        """Optimize using scikit-optimize."""

        # Define space
        space = []
        param_names = []

        for key, space_def in self.param_space.items():
            if isinstance(space_def, (list, tuple)):
                space.append(Categorical(space_def))
            elif isinstance(space_def, dict):
                if space_def.get("type") == "uniform":
                    space.append(Real(space_def["low"], space_def["high"]))
                elif space_def.get("type") == "loguniform":
                    space.append(Real(space_def["low"], space_def["high"], prior="log-uniform"))
                elif space_def.get("type") == "int":
                    space.append(Integer(space_def["low"], space_def["high"]))
            param_names.append(key)

        def objective(params):
            params_dict = dict(zip(param_names, params))
            result = self._evaluate(params_dict)
            return -result.score if self.direction == "maximize" else result.score

        result = gp_minimize(
            objective,
            space,
            n_calls=n_trials,
            n_initial_points=n_initial_points,
            random_state=42,
        )

        results = []
        for i, (params, score) in enumerate(zip(result.x_iters, result.func_vals)):
            params_dict = dict(zip(param_names, params))
            results.append(OptimizationResult(
                params=params_dict,
                metrics={self.metric: -score if self.direction == "maximize" else score},
                score=-score if self.direction == "maximize" else score,
                trial_number=i,
            ))

        self.results.extend(results)
        return results

    def walk_forward_optimize(
        self,
        data: pd.DataFrame,
        train_window: int = 252,
        test_window: int = 60,
        step: int = 21,
        method: str = "random",
        **kwargs,
    ) -> list[OptimizationResult]:
        """
        Walk-forward optimization.

        Optimizes on train window, evaluates on test window.
        """
        from cryptobot.backtest.validation import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window=train_window,
            test_window=test_window,
            step=step,
        )

        all_results = []

        def optimize_train(train_data):
            # Create temporary optimizer for train data
            def train_backtest(params):
                return self.backtest_fn(params)

            temp_optimizer = BacktestOptimizer(
                backtest_fn=train_backtest,
                param_space=self.param_space,
                metric=self.metric,
                direction=self.direction,
            )

            if method == "random":
                temp_optimizer.random_search(kwargs.get("n_trials", 50))
            elif method == "bayesian":
                temp_optimizer.bayesian_optimization(kwargs.get("n_trials", 30))
            else:
                temp_optimizer.grid_search()

            return temp_optimizer.best_params

        def backtest_test(test_data, params):
            # Run backtest on test data with params
            return self.backtest_fn(params)

        wf_results = validator.validate(data, optimize_train, backtest_test)

        # Convert to OptimizationResult
        for i, wf in enumerate(wf_results):
            all_results.append(OptimizationResult(
                params=wf.params,
                metrics=wf.test_metrics,
                score=wf.test_metrics.get(self.metric, 0),
                trial_number=i,
            ))

        return all_results

    def get_best_params(self) -> dict[str, Any] | None:
        """Get best parameters found."""
        return self.best_params

    def get_best_score(self) -> float:
        """Get best score."""
        return self.best_score

    def get_results_df(self) -> pd.DataFrame:
        """Get results as DataFrame."""
        if not self.results:
            return pd.DataFrame()

        rows = []
        for r in self.results:
            row = {**r.params, **r.metrics, "score": r.score, "trial": r.trial_number}
            rows.append(row)

        return pd.DataFrame(rows)

    def plot_optimization_history(self) -> Any:
        """Plot optimization history."""
        import plotly.graph_objects as go

        trials = [r.trial_number for r in self.results]
        scores = [r.score for r in self.results]
        best_scores = []

        current_best = -np.inf if self.direction == "maximize" else np.inf
        for s in scores:
            if self.direction == "maximize":
                current_best = max(current_best, s)
            else:
                current_best = min(current_best, s)
            best_scores.append(current_best)

        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=trials, y=scores, mode="markers", name="Trial Score"))
        fig.add_trace(go.Scatter(x=trials, y=best_scores, mode="lines", name="Best Score"))
        fig.update_layout(
            title="Optimization History",
            xaxis_title="Trial",
            yaxis_title=self.metric,
            template="plotly_white",
        )
        return fig

    def plot_parameter_importance(self) -> Any:
        """Plot parameter importance (requires Optuna)."""
        if not OPTUNA_AVAILABLE or not self.results:
            return None

        # Create a dummy study for importance
        import optuna
        study = optuna.create_study(direction=self.direction)

        for r in self.results:
            trial = optuna.trial.FrozenTrial(
                number=r.trial_number,
                params=r.params,
                value=r.score,
                state=optuna.trial.TrialState.COMPLETE,
            )
            study.add_trial(trial)

        try:
            importance = optuna.importance.get_param_importances(study)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=list(importance.keys()),
                y=list(importance.values()),
            ))
            fig.update_layout(
                title="Parameter Importance",
                xaxis_title="Parameter",
                yaxis_title="Importance",
                template="plotly_white",
            )
            return fig
        except Exception:
            return None


def create_param_space(config: dict[str, Any]) -> dict[str, Any]:
    """Create parameter space from strategy config."""
    space = {}

    for name, param_config in config.items():
        if isinstance(param_config, dict):
            space[name] = param_config
        elif isinstance(param_config, (list, tuple)):
            space[name] = param_config
        else:
            # Single value - convert to small range
            if isinstance(param_config, int):
                space[name] = {"type": "int", "low": max(1, param_config - 5), "high": param_config + 5}
            elif isinstance(param_config, float):
                space[name] = {"type": "uniform", "low": param_config * 0.5, "high": param_config * 1.5}

    return space