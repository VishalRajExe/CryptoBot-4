"""
Walk-forward and robustness testing.
Adapted from skfolio's model_selection and Vibe-Trading's backtest validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

import numpy as np
import pandas as pd

# Try to import skfolio for advanced CV
try:
    from skfolio.model_selection import (
        WalkForward,
        CombinatorialPurgedCV,
        MultipleRandomizedCV,
    )
    SKFOLIO_CV_AVAILABLE = True
except ImportError:
    SKFOLIO_CV_AVAILABLE = False

from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardResult:
    """Single walk-forward window result."""

    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_metrics: dict[str, float]
    test_metrics: dict[str, float]
    params: dict[str, Any]
    equity_curve: pd.Series | None = None


class WalkForwardValidator:
    """
    Walk-forward validation for strategy robustness.

    Splits data into sequential train/test windows,
    optimizes on train, evaluates on test.
    """

    def __init__(
        self,
        train_window: int = 252,  # days
        test_window: int = 60,    # days
        step: int = 21,           # days (monthly rebalance)
        min_train_size: int = 100,
        anchor: str = "expanding",  # "expanding" or "rolling"
    ):
        self.train_window = train_window
        self.test_window = test_window
        self.step = step
        self.min_train_size = min_train_size
        self.anchor = anchor

    def split(self, data: pd.DataFrame) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Generate walk-forward splits.

        Returns:
            List of (train_data, test_data) tuples
        """
        n = len(data)
        splits = []

        start = 0
        while start + self.train_window + self.test_window <= n:
            train_end = start + self.train_window
            test_end = min(train_end + self.test_window, n)

            if self.anchor == "expanding":
                train_data = data.iloc[:train_end]
            else:  # rolling
                train_data = data.iloc[start:train_end]

            test_data = data.iloc[train_end:test_end]

            if len(train_data) >= self.min_train_size and len(test_data) > 0:
                splits.append((train_data, test_data))

            start += self.step

        return splits

    def validate(
        self,
        data: pd.DataFrame,
        optimize_fn: Callable[[pd.DataFrame], dict[str, Any]],
        backtest_fn: Callable[[pd.DataFrame, dict[str, Any]], dict[str, float]],
    ) -> list[WalkForwardResult]:
        """
        Run walk-forward validation.

        Args:
            data: Full dataset
            optimize_fn: Function(train_data) -> optimal_params
            backtest_fn: Function(test_data, params) -> metrics

        Returns:
            List of WalkForwardResult
        """
        splits = self.split(data)
        results = []

        for i, (train_data, test_data) in enumerate(splits):
            logger.info(f"Walk-forward window {i+1}/{len(splits)}: "
                       f"train={len(train_data)}, test={len(test_data)}")

            try:
                # Optimize on train
                params = optimize_fn(train_data)

                # Backtest on train (in-sample)
                train_metrics = backtest_fn(train_data, params)

                # Backtest on test (out-of-sample)
                test_metrics = backtest_fn(test_data, params)

                # Equity curve
                equity = backtest_fn(test_data, params, return_equity=True)

                results.append(WalkForwardResult(
                    train_start=train_data.index[0],
                    train_end=train_data.index[-1],
                    test_start=test_data.index[0],
                    test_end=test_data.index[-1],
                    train_metrics=train_metrics,
                    test_metrics=test_metrics,
                    params=params,
                    equity_curve=equity,
                ))

            except Exception as e:
                logger.error(f"Walk-forward window {i} failed: {e}")

        return results

    def aggregate_results(self, results: list[WalkForwardResult]) -> dict[str, Any]:
        """Aggregate walk-forward results."""
        if not results:
            return {}

        test_metrics_keys = results[0].test_metrics.keys()

        aggregated = {}
        for key in test_metrics_keys:
            values = [r.test_metrics[key] for r in results]
            aggregated[key] = {
                "mean": np.mean(values),
                "std": np.std(values),
                "min": np.min(values),
                "max": np.max(values),
                "sharpe": np.mean(values) / np.std(values) if np.std(values) > 0 else 0,
            }

        # Consistency
        positive_windows = sum(1 for r in results if r.test_metrics.get("total_return_pct", 0) > 0)
        aggregated["consistency"] = positive_windows / len(results) * 100

        # Stability (low variance in params)
        param_keys = results[0].params.keys()
        for key in param_keys:
            values = [r.params[key] for r in results]
            aggregated[f"param_{key}_stability"] = 1 - np.std(values) / (np.mean(values) + 1e-8)

        return aggregated


class MonteCarloValidator:
    """
    Monte Carlo simulation for strategy robustness.

    Resamples returns to generate distribution of outcomes.
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        block_size: int = 1,  # For block bootstrap
        confidence_level: float = 0.95,
    ):
        self.n_simulations = n_simulations
        self.block_size = block_size
        self.confidence_level = confidence_level

    def simulate(
        self,
        returns: pd.Series,
        initial_cash: float = 100000.0,
    ) -> dict[str, Any]:
        """
        Run Monte Carlo simulation on return series.

        Args:
            returns: Strategy return series
            initial_cash: Starting capital

        Returns:
            Simulation statistics
        """
        n = len(returns)
        if n < 10:
            return {}

        # Block bootstrap for autocorrelation
        n_blocks = max(1, n // self.block_size)
        block_returns = []

        for i in range(0, n, self.block_size):
            block = returns.iloc[i:i + self.block_size]
            if len(block) > 0:
                block_returns.append(block)

        if not block_returns:
            return {}

        # Simulate
        final_values = []
        max_drawdowns = []
        worst_drawdowns = []

        for _ in range(self.n_simulations):
            # Sample blocks with replacement
            sampled = np.random.choice(len(block_returns), size=n_blocks, replace=True)
            sim_returns = pd.concat([block_returns[i] for i in sampled]).values[:n]

            # Equity curve
            equity = (1 + sim_returns).cumprod() * initial_cash

            # Metrics
            final_values.append(equity[-1])
            dd = (equity - equity.cummax()) / equity.cummax()
            max_drawdowns.append(dd.min() * 100)

        alpha = (1 - self.confidence_level) / 2
        return {
            "final_value_mean": np.mean(final_values),
            "final_value_median": np.median(final_values),
            "final_value_ci": [
                np.percentile(final_values, alpha * 100),
                np.percentile(final_values, (1 - alpha) * 100),
            ],
            "max_dd_mean": np.mean(max_drawdowns),
            "max_dd_ci": [
                np.percentile(max_drawdowns, alpha * 100),
                np.percentile(max_drawdowns, (1 - alpha) * 100),
            ],
            "prob_profit": sum(1 for v in final_values if v > initial_cash) / self.n_simulations * 100,
            "prob_ruin": sum(1 for v in final_values if v < initial_cash * 0.5) / self.n_simulations * 100,
        }


class CPCVValidator:
    """
    Combinatorial Purged Cross-Validation.
    Adapted from skfolio's CombinatorialPurgedCV.
    """

    def __init__(
        self,
        n_folds: int = 10,
        n_test_folds: int = 2,
        purge_gap: int = 0,
        embargo_pct: float = 0.01,
    ):
        self.n_folds = n_folds
        self.n_test_folds = n_test_folds
        self.purge_gap = purge_gap
        self.embargo_pct = embargo_pct

    def split(self, data: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
        """
        Generate CPCV splits.

        Returns:
            List of (train_indices, test_indices) tuples
        """
        if not SKFOLIO_CV_AVAILABLE:
            logger.warning("skfolio not available, using simple time series split")
            return self._simple_split(data)

        cv = CombinatorialPurgedCV(
            n_folds=self.n_folds,
            n_test_folds=self.n_test_folds,
            purge_gap=self.purge_gap,
            embargo_pct=self.embargo_pct,
        )
        return list(cv.split(data))

    def _simple_split(self, data: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
        """Fallback simple time series split."""
        n = len(data)
        fold_size = n // self.n_folds
        splits = []

        for i in range(self.n_folds - self.n_test_folds + 1):
            train_end = (i + self.n_folds - self.n_test_folds) * fold_size
            test_start = train_end
            test_end = min(test_start + self.n_test_folds * fold_size, n)

            train_idx = np.arange(train_end)
            test_idx = np.arange(test_start, test_end)

            splits.append((train_idx, test_idx))

        return splits

    def validate(
        self,
        data: pd.DataFrame,
        optimize_fn: Callable[[pd.DataFrame], dict[str, Any]],
        backtest_fn: Callable[[pd.DataFrame, dict[str, Any]], dict[str, float]],
    ) -> dict[str, Any]:
        """Run CPCV validation."""
        splits = self.split(data)
        all_test_metrics = []

        for train_idx, test_idx in splits:
            train_data = data.iloc[train_idx]
            test_data = data.iloc[test_idx]

            try:
                params = optimize_fn(train_data)
                metrics = backtest_fn(test_data, params)
                all_test_metrics.append(metrics)
            except Exception as e:
                logger.error(f"CPCV fold failed: {e}")

        if not all_test_metrics:
            return {}

        # Aggregate
        keys = all_test_metrics[0].keys()
        aggregated = {}
        for key in keys:
            values = [m[key] for m in all_test_metrics]
            aggregated[key] = {
                "mean": np.mean(values),
                "std": np.std(values),
                "sharpe": np.mean(values) / np.std(values) if np.std(values) > 0 else 0,
            }

        return aggregated


class SyntheticDataGenerator:
    """
    Generate synthetic market data for stress testing.
    Adapted from skfolio's VineCopula and Vibe-Trading's synthetic data.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        np.random.seed(random_state)

    def generate_copula(
        self,
        returns: pd.DataFrame,
        n_samples: int = 10000,
        copula_type: str = "vine",
    ) -> pd.DataFrame:
        """
        Generate synthetic returns using copula.

        Args:
            returns: Historical returns
            n_samples: Number of synthetic samples
            copula_type: "vine", "gaussian", "student"

        Returns:
            Synthetic returns DataFrame
        """
        # Simple approach: fit multivariate distribution and sample
        # For production, use skfolio's VineCopula

        mean = returns.mean().values
        cov = returns.cov().values

        if copula_type == "gaussian":
            synthetic = np.random.multivariate_normal(mean, cov, n_samples)
        elif copula_type == "student":
            # Student-t with 5 dof
            dof = 5
            synthetic = np.random.multivariate_t(mean, cov, dof, n_samples)
        else:
            # Vine copula approximation - use Gaussian for now
            synthetic = np.random.multivariate_normal(mean, cov, n_samples)

        return pd.DataFrame(synthetic, columns=returns.columns)

    def generate_regime_data(
        self,
        returns: pd.DataFrame,
        n_regimes: int = 3,
        n_samples: int = 10000,
    ) -> pd.DataFrame:
        """
        Generate synthetic data with regime switching.
        """
        # Fit HMM or GMM for regimes
        from sklearn.mixture import GaussianMixture

        gmm = GaussianMixture(n_components=n_regimes, random_state=self.random_state)
        gmm.fit(returns)

        synthetic = gmm.sample(n_samples)[0]
        return pd.DataFrame(synthetic, columns=returns.columns)

    def stress_test_scenarios(self) -> dict[str, dict[str, float]]:
        """Predefined stress test scenarios."""
        return {
            "crypto_crash_2022": {
                "btc_return": -0.65,
                "eth_return": -0.68,
                "alt_return": -0.80,
                "correlation": 0.95,
                "vol_mult": 3.0,
            },
            "covid_crash_2020": {
                "btc_return": -0.50,
                "eth_return": -0.55,
                "alt_return": -0.70,
                "correlation": 0.90,
                "vol_mult": 4.0,
            },
            "flash_crash_2010": {
                "btc_return": -0.30,
                "eth_return": -0.35,
                "alt_return": -0.50,
                "correlation": 0.98,
                "vol_mult": 5.0,
            },
            "custom_50pct_drop": {
                "btc_return": -0.50,
                "eth_return": -0.50,
                "alt_return": -0.60,
                "correlation": 0.85,
                "vol_mult": 2.5,
            },
        }

    def apply_scenario(
        self,
        returns: pd.DataFrame,
        scenario: str,
    ) -> pd.DataFrame:
        """Apply stress scenario to returns."""
        scenarios = self.stress_test_scenarios()
        if scenario not in scenarios:
            raise ValueError(f"Unknown scenario: {scenario}")

        params = scenarios[scenario]
        stressed = returns.copy()

        # Simple stress application
        for col in stressed.columns:
            if "BTC" in col.upper():
                stressed[col] *= params["vol_mult"]
            elif "ETH" in col.upper():
                stressed[col] *= params["vol_mult"]
            else:
                stressed[col] *= params["vol_mult"] * 1.2

        return stressed