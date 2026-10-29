"""
Portfolio optimizer using skfolio.
Adapted from skfolio's MeanRisk, HierarchicalRiskParity, NestedClustersOptimization, etc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

# skfolio imports (optional - will work if installed)
try:
    from skfolio.optimization import (
        MeanRisk,
        HierarchicalRiskParity,
        NestedClustersOptimization,
        RiskBudgeting,
        MaximumDiversification,
        DistributionallyRobustCVaR,
        BenchmarkTracker,
        ObjectiveFunction,
        RiskMeasure,
    )
    from skfolio.prior import EmpiricalPrior, BlackLitterman
    from skfolio.moments import (
        DenoiseCovariance,
        DetoneCovariance,
        LedoitWolf,
        GerberCovariance,
        ShrunkCovariance,
    )
    from skfolio.distance import PearsonDistance
    from skfolio.cluster import HierarchicalClustering
    SKFOLIO_AVAILABLE = True
except ImportError:
    SKFOLIO_AVAILABLE = False
    logging.warning("skfolio not installed. Portfolio optimization will use fallback.")

from cryptobot.data.models import Symbol
from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Portfolio optimization result."""

    weights: dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    objective_value: float
    method: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": self.weights,
            "expected_return": self.expected_return,
            "expected_risk": self.expected_risk,
            "sharpe_ratio": self.sharpe_ratio,
            "objective_value": self.objective_value,
            "method": self.method,
            "metadata": self.metadata,
        }


class PortfolioOptimizer:
    """
    Portfolio optimizer with multiple methods.

    Methods:
    - Mean-Risk (Markowitz, CVaR, EVaR, etc.)
    - Hierarchical Risk Parity (HRP)
    - Hierarchical Equal Risk Contribution (HERC)
    - Nested Clusters Optimization (NCO)
    - Risk Budgeting / Risk Parity
    - Maximum Diversification
    - Distributionally Robust CVaR
    - Black-Litterman
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.default_method = self.config.get("method", "mean_risk")
        self.risk_measure = self.config.get("risk_measure", "variance")
        self.objective = self.config.get("objective", "maximize_ratio")

    def optimize(
        self,
        returns: pd.DataFrame,
        method: str | None = None,
        risk_measure: str | None = None,
        objective: str | None = None,
        constraints: dict[str, Any] | None = None,
        prior_estimator: str | None = None,
        views: dict[str, float] | None = None,
    ) -> OptimizationResult:
        """
        Optimize portfolio weights.

        Args:
            returns: DataFrame of asset returns (columns=assets, index=dates)
            method: Optimization method
            risk_measure: Risk measure to use
            objective: Objective function
            constraints: Additional constraints
            prior_estimator: Prior estimator for returns/covariance
            views: Black-Litterman views

        Returns:
            OptimizationResult with weights and metrics
        """
        if not SKFOLIO_AVAILABLE:
            return self._fallback_optimize(returns, method, constraints)

        method = method or self.default_method
        risk_measure = risk_measure or self.risk_measure
        objective = objective or self.objective

        # Prepare prior estimator
        prior = self._create_prior(prior_estimator, views)

        # Create optimizer
        optimizer = self._create_optimizer(
            method=method,
            risk_measure=risk_measure,
            objective=objective,
            prior=prior,
            constraints=constraints,
        )

        # Fit
        optimizer.fit(returns)

        # Extract results
        weights = optimizer.weights_
        if isinstance(weights, np.ndarray):
            weights = dict(zip(returns.columns, weights))

        # Calculate metrics
        port_returns = (returns * pd.Series(weights)).sum(axis=1)
        expected_return = port_returns.mean() * 252  # Annualized
        expected_risk = port_returns.std() * np.sqrt(252)
        sharpe = expected_return / expected_risk if expected_risk > 0 else 0

        return OptimizationResult(
            weights=weights,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=sharpe,
            objective_value=sharpe,  # Simplified
            method=method,
            metadata={
                "n_assets": len(returns.columns),
                "n_observations": len(returns),
                "constraints": constraints,
                "prior": prior_estimator,
            },
        )

    def _create_prior(
        self,
        prior_estimator: str | None,
        views: dict[str, float] | None,
    ):
        """Create prior estimator."""
        if not SKFOLIO_AVAILABLE:
            return None

        if prior_estimator == "black_litterman" and views:
            return BlackLitterman(views=views)
        elif prior_estimator == "denoised":
            return EmpiricalPrior(covariance_estimator=DenoiseCovariance())
        elif prior_estimator == "detoned":
            return EmpiricalPrior(covariance_estimator=DetoneCovariance())
        elif prior_estimator == "gerber":
            return EmpiricalPrior(covariance_estimator=GerberCovariance())
        elif prior_estimator == "ledoit_wolf":
            return EmpiricalPrior(covariance_estimator=LedoitWolf())
        elif prior_estimator == "shrunk":
            return EmpiricalPrior(covariance_estimator=ShrunkCovariance())

        return EmpiricalPrior()

    def _create_optimizer(
        self,
        method: str,
        risk_measure: str,
        objective: str,
        prior,
        constraints: dict | None,
    ):
        """Create optimizer instance."""
        if not SKFOLIO_AVAILABLE:
            return None

        # Map risk measure
        rm_map = {
            "variance": RiskMeasure.VARIANCE,
            "cvar": RiskMeasure.CVAR,
            "evar": RiskMeasure.EVAR,
            "max_drawdown": RiskMeasure.MAX_DRAWDOWN,
            "cdar": RiskMeasure.CDAR,
            "ulcer_index": RiskMeasure.ULCER_INDEX,
            "semi_variance": RiskMeasure.SEMI_VARIANCE,
        }

        # Map objective
        obj_map = {
            "minimize_risk": ObjectiveFunction.MINIMIZE_RISK,
            "maximize_return": ObjectiveFunction.MAXIMIZE_RETURN,
            "maximize_utility": ObjectiveFunction.MAXIMIZE_UTILITY,
            "maximize_ratio": ObjectiveFunction.MAXIMIZE_RATIO,
        }

        rm = rm_map.get(risk_measure, RiskMeasure.VARIANCE)
        obj = obj_map.get(objective, ObjectiveFunction.MAXIMIZE_RATIO)

        common_kwargs = {
            "risk_measure": rm,
            "objective_function": obj,
            "prior_estimator": prior,
        }

        # Add constraints
        if constraints:
            if "min_weights" in constraints:
                common_kwargs["min_weights"] = constraints["min_weights"]
            if "max_weights" in constraints:
                common_kwargs["max_weights"] = constraints["max_weights"]
            if "budget" in constraints:
                common_kwargs["budget"] = constraints["budget"]
            if "transaction_costs" in constraints:
                common_kwargs["transaction_costs"] = constraints["transaction_costs"]
            if "groups" in constraints:
                common_kwargs["groups"] = constraints["groups"]

        if method == "mean_risk":
            return MeanRisk(**common_kwargs)
        elif method == "hrp":
            return HierarchicalRiskParity(
                risk_measure=rm,
                distance_estimator=PearsonDistance(),
                hierarchical_clustering=HierarchicalClustering(),
                **{k: v for k, v in common_kwargs.items() if k != "objective_function"},
            )
        elif method == "herc":
            from skfolio.optimization import HierarchicalEqualRiskContribution
            return HierarchicalEqualRiskContribution(
                risk_measure=rm,
                distance_estimator=PearsonDistance(),
                **{k: v for k, v in common_kwargs.items() if k != "objective_function"},
            )
        elif method == "nco":
            return NestedClustersOptimization(
                inner_estimator=MeanRisk(risk_measure=rm, **common_kwargs),
                outer_estimator=RiskBudgeting(risk_measure=rm, **common_kwargs),
            )
        elif method == "risk_budgeting":
            return RiskBudgeting(risk_measure=rm, **common_kwargs)
        elif method == "max_diversification":
            return MaximumDiversification(**common_kwargs)
        elif method == "dr_cvar":
            return DistributionallyRobustCVaR(**common_kwargs)
        elif method == "benchmark_tracker":
            return BenchmarkTracker(**common_kwargs)

        return MeanRisk(**common_kwargs)

    def _fallback_optimize(
        self,
        returns: pd.DataFrame,
        method: str | None,
        constraints: dict | None,
    ) -> OptimizationResult:
        """Fallback optimization using simple methods."""
        n = len(returns.columns)

        if method == "hrp" or method == "equal_weight":
            # Equal weight
            weights = {col: 1.0 / n for col in returns.columns}
        elif method == "inverse_vol":
            # Inverse volatility weighting
            vols = returns.std()
            inv_vols = 1.0 / vols
            weights = (inv_vols / inv_vols.sum()).to_dict()
        elif method == "risk_parity":
            # Simple risk parity (inverse variance)
            vars_ = returns.var()
            inv_vars = 1.0 / vars_
            weights = (inv_vars / inv_vars.sum()).to_dict()
        else:
            # Mean-variance (simplified)
            mean_rets = returns.mean()
            cov = returns.cov()
            # Simple maximum Sharpe (no constraints)
            try:
                inv_cov = np.linalg.pinv(cov.values)
                ones = np.ones(n)
                weights_arr = inv_cov @ mean_rets.values
                weights_arr = weights_arr / weights_arr.sum()
                weights = dict(zip(returns.columns, weights_arr))
            except Exception:
                weights = {col: 1.0 / n for col in returns.columns}

        # Apply constraints
        if constraints:
            if "max_weights" in constraints:
                max_w = constraints["max_weights"]
                if isinstance(max_w, (int, float)):
                    for k in weights:
                        weights[k] = min(weights[k], max_w)
                elif isinstance(max_w, dict):
                    for k, v in max_w.items():
                        if k in weights:
                            weights[k] = min(weights[k], v)

        # Renormalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        port_returns = (returns * pd.Series(weights)).sum(axis=1)
        expected_return = port_returns.mean() * 252
        expected_risk = port_returns.std() * np.sqrt(252)
        sharpe = expected_return / expected_risk if expected_risk > 0 else 0

        return OptimizationResult(
            weights=weights,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=sharpe,
            objective_value=sharpe,
            method=method or "fallback",
            metadata={"fallback": True},
        )

    def optimize_walk_forward(
        self,
        returns: pd.DataFrame,
        train_window: int = 252,
        test_window: int = 60,
        step: int = 21,
        **kwargs,
    ) -> list[OptimizationResult]:
        """Walk-forward optimization."""
        results = []
        n = len(returns)

        for start in range(0, n - train_window - test_window + 1, step):
            train_end = start + train_window
            test_end = min(train_end + test_window, n)

            train_data = returns.iloc[start:train_end]
            test_data = returns.iloc[train_end:test_end]

            if len(train_data) < 30:
                continue

            try:
                result = self.optimize(train_data, **kwargs)
                result.metadata["train_start"] = train_data.index[0]
                result.metadata["train_end"] = train_data.index[-1]
                result.metadata["test_start"] = test_data.index[0]
                result.metadata["test_end"] = test_data.index[-1]
                results.append(result)
            except Exception as e:
                logger.warning(f"Walk-forward step failed: {e}")

        return results


class FactorModelOptimizer:
    """
    Factor model-based portfolio optimization.
    Adapted from skfolio's CharacteristicsFactorModel and TimeSeriesFactorModel.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def optimize_with_factors(
        self,
        returns: pd.DataFrame,
        factor_returns: pd.DataFrame | None = None,
        characteristics: pd.DataFrame | None = None,
        method: str = "time_series",
    ) -> OptimizationResult:
        """
        Optimize using factor models.

        Args:
            returns: Asset returns
            factor_returns: Factor returns (for time-series model)
            characteristics: Asset characteristics (for cross-sectional model)
            method: "time_series" or "characteristics"

        Returns:
            OptimizationResult
        """
        if not SKFOLIO_AVAILABLE:
            return PortfolioOptimizer()._fallback_optimize(returns, "mean_risk", None)

        if method == "time_series" and factor_returns is not None:
            # Time-series factor model
            from skfolio.prior import TimeSeriesFactorModel
            prior = TimeSeriesFactorModel()
            optimizer = MeanRisk(prior_estimator=prior)
            optimizer.fit(returns, factors=factor_returns)
        elif method == "characteristics" and characteristics is not None:
            # Cross-sectional characteristics model
            from skfolio.prior import CharacteristicsFactorModel
            from skfolio.factor_exposure import (
                GlobalFactor,
                FixedWeightedFactor,
                OneHotCategoricalFactors,
            )
            # This would need more setup
            prior = EmpiricalPrior()
            optimizer = MeanRisk(prior_estimator=prior)
            optimizer.fit(returns)
        else:
            optimizer = MeanRisk()
            optimizer.fit(returns)

        weights = optimizer.weights_
        if isinstance(weights, np.ndarray):
            weights = dict(zip(returns.columns, weights))

        port_returns = (returns * pd.Series(weights)).sum(axis=1)
        expected_return = port_returns.mean() * 252
        expected_risk = port_returns.std() * np.sqrt(252)
        sharpe = expected_return / expected_risk if expected_risk > 0 else 0

        return OptimizationResult(
            weights=weights,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=sharpe,
            objective_value=sharpe,
            method=f"factor_{method}",
            metadata={"n_factors": factor_returns.shape[1] if factor_returns is not None else 0},
        )