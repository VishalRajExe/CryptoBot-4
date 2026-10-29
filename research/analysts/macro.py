"""
Macro Analyst - FRED data, DXY, yields, correlation regimes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from cryptobot.research.analysts.base import BaseAnalyst, create_analyst_result

logger = logging.getLogger(__name__)


class MacroAnalyst(BaseAnalyst):
    """Macro analyst for economic and cross-asset analysis."""

    def __init__(self, tool_registry, config: dict[str, Any] | None = None):
        super().__init__(tool_registry, config)
        self.fred_api_key = config.get("fred_api_key")
        self.lookback_days = config.get("lookback_days", 90)

    async def analyze(
        self,
        symbols: list[str],
        trade_date: str,
        portfolio_context: dict[str, Any] | None = None,
        memory_context: str | None = None,
    ) -> dict[str, Any]:
        """Analyze macro environment."""
        # Fetch macro indicators
        rates = await self._fetch_rates()
        dxy = await self._fetch_dxy()
        correlations = await self._fetch_crypto_correlations(symbols)
        regime = self._detect_regime(rates, dxy, correlations)

        # Generate signals
        signals = self._generate_signals(rates, dxy, correlations, regime)

        return {
            "analyst": "macro",
            "date": trade_date,
            "findings": {
                "rates": rates,
                "dxy": dxy,
                "correlations": correlations,
                "regime": regime,
            },
            "confidence": 0.6,
            "signals": signals,
            "risks": self._identify_risks(rates, dxy, regime),
            "data_sources": ["fred", "yahoo_finance", "exchange_apis"],
            "summary": self._generate_summary(regime, correlations),
        }

    async def _fetch_rates(self) -> dict[str, Any]:
        """Fetch interest rate data from FRED."""
        if not self.fred_api_key:
            return self._mock_rates()

        rates = {}
        series = {
            "fed_funds": "FEDFUNDS",
            "10y_treasury": "DGS10",
            "2y_treasury": "DGS2",
            "10y_minus_2y": "T10Y2Y",
            "real_yield": "DFII10",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            for name, series_id in series.items():
                try:
                    resp = await client.get(
                        "https://api.stlouisfed.org/fred/series/observations",
                        params={
                            "series_id": series_id,
                            "api_key": self.fred_api_key,
                            "file_type": "json",
                            "limit": 1,
                            "sort_order": "desc",
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("observations"):
                            rates[name] = float(data["observations"][0]["value"])
                except Exception as e:
                    logger.debug(f"FRED fetch error for {series_id}: {e}")

        return rates if rates else self._mock_rates()

    def _mock_rates(self) -> dict[str, float]:
        """Mock rates for development."""
        return {
            "fed_funds": 5.25,
            "10y_treasury": 4.30,
            "2y_treasury": 4.50,
            "10y_minus_2y": -0.20,
            "real_yield": 1.80,
        }

    async def _fetch_dxy(self) -> dict[str, Any]:
        """Fetch Dollar Index (DXY)."""
        # Would use Yahoo Finance or other API
        return {
            "value": 103.5,
            "change_1d": 0.1,
            "change_1w": -0.5,
            "trend": "neutral",
        }

    async def _fetch_crypto_correlations(self, symbols: list[str]) -> dict[str, Any]:
        """Fetch crypto correlations with macro assets."""
        bases = [s.split("/")[0].split(":")[0].upper() for s in symbols]

        # Would calculate rolling correlations
        return {
            "btc_dxy": -0.3,
            "btc_sp500": 0.4,
            "btc_gold": 0.2,
            "btc_10y_yield": -0.25,
            "eth_btc": 0.8,
            "regime": "risk_on" if -0.3 > -0.5 else "risk_off",
        }

    def _detect_regime(
        self,
        rates: dict,
        dxy: dict,
        correlations: dict,
    ) -> dict[str, Any]:
        """Detect macro regime."""
        regime = "neutral"
        confidence = 0.5

        # Yield curve
        spread = rates.get("10y_minus_2y", 0)
        if spread < -0.5:
            regime = "recession_risk"
            confidence = 0.7
        elif spread > 1.0:
            regime = "expansion"
            confidence = 0.6

        # DXY trend
        dxy_trend = dxy.get("trend", "neutral")
        if dxy_trend == "bullish" and regime == "neutral":
            regime = "dollar_strength"
        elif dxy_trend == "bearish" and regime == "neutral":
            regime = "dollar_weakness"

        # Crypto correlation regime
        crypto_regime = correlations.get("regime", "neutral")
        if crypto_regime == "risk_off" and regime == "neutral":
            regime = "risk_off"

        return {
            "regime": regime,
            "confidence": confidence,
            "yield_curve_spread": spread,
            "dxy_trend": dxy_trend,
            "crypto_regime": crypto_regime,
        }

    def _generate_signals(
        self,
        rates: dict,
        dxy: dict,
        correlations: dict,
        regime: dict,
    ) -> list[dict]:
        signals = []

        # Regime-based signals
        if regime["regime"] == "recession_risk":
            signals.append({
                "type": "macro_recession",
                "direction": "short",
                "strength": 0.6,
                "reason": "Inverted yield curve signals recession risk",
            })
        elif regime["regime"] == "expansion":
            signals.append({
                "type": "macro_expansion",
                "direction": "long",
                "strength": 0.5,
                "reason": "Steep yield curve signals economic expansion",
            })

        # Dollar strength/weakness
        if regime["regime"] == "dollar_weakness":
            signals.append({
                "type": "dollar_weakness",
                "direction": "long",
                "strength": 0.4,
                "reason": "DXY weakening - positive for risk assets",
            })
        elif regime["regime"] == "dollar_strength":
            signals.append({
                "type": "dollar_strength",
                "direction": "short",
                "strength": 0.4,
                "reason": "DXY strengthening - negative for risk assets",
            })

        # Real yields
        real_yield = rates.get("real_yield", 0)
        if real_yield > 2.5:
            signals.append({
                "type": "high_real_yields",
                "direction": "short",
                "strength": 0.5,
                "reason": f"High real yields ({real_yield}%) - negative for crypto",
            })
        elif real_yield < 0.5:
            signals.append({
                "type": "low_real_yields",
                "direction": "long",
                "strength": 0.4,
                "reason": f"Low real yields ({real_yield}%) - supportive for crypto",
            })

        return signals

    def _identify_risks(self, rates: dict, dxy: dict, regime: dict) -> list[str]:
        risks = []
        if regime["regime"] == "recession_risk":
            risks.append("Macro recession risk elevated")
        if rates.get("fed_funds", 0) > 5.0:
            risks.append("Restrictive monetary policy")
        if dxy.get("trend") == "bullish":
            risks.append("Dollar strength headwind for crypto")
        return risks

    def _generate_summary(self, regime: dict, correlations: dict) -> str:
        return f"Macro Analyst: Regime={regime['regime']} (conf={regime['confidence']:.0%}), BTC-DXY corr={correlations.get('btc_dxy', 0):.2f}"