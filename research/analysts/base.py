"""
Base analyst class and common utilities.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from cryptobot.research.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class BaseAnalyst(ABC):
    """Base class for all analysts."""

    def __init__(self, tool_registry: ToolRegistry, config: dict[str, Any] | None = None):
        self.tool_registry = tool_registry
        self.config = config or {}
        self.name = self.__class__.__name__.replace("Analyst", "").lower()

    @abstractmethod
    async def analyze(
        self,
        symbols: list[str],
        trade_date: str,
        portfolio_context: dict[str, Any] | None = None,
        memory_context: str | None = None,
    ) -> dict[str, Any]:
        """Perform analysis for given symbols."""
        pass

    def _get_tools(self, tool_names: list[str]) -> list[Callable]:
        """Get tools by name from registry."""
        tools = []
        for name in tool_names:
            tool = self.tool_registry.get(name)
            if tool:
                tools.append(tool)
            else:
                logger.warning(f"Tool not found: {name}")
        return tools

    def _build_prompt(
        self,
        symbols: list[str],
        trade_date: str,
        portfolio_context: dict[str, Any] | None,
        memory_context: str | None,
        specific_instructions: str,
    ) -> str:
        """Build standard analyst prompt."""
        portfolio_str = ""
        if portfolio_context:
            portfolio_str = f"\nCurrent Portfolio:\n{portfolio_context}"

        memory_str = ""
        if memory_context:
            memory_str = f"\nRelevant Past Decisions:\n{memory_context}"

        return f"""You are a {self.name} analyst for crypto trading.
Date: {trade_date}
Symbols: {', '.join(symbols)}
{portfolio_str}
{memory_str}

{specific_instructions}

Provide your analysis in structured format with:
1. Key findings per symbol
2. Confidence level (0-1)
3. Specific data points cited
4. Risk factors identified
5. Actionable signals (if any)
"""


class AnalystResult:
    """Structured result from an analyst."""

    def __init__(
        self,
        symbol: str,
        findings: dict[str, Any],
        confidence: float,
        signals: list[dict[str, Any]] | None = None,
        risks: list[str] | None = None,
        data_sources: list[str] | None = None,
    ):
        self.symbol = symbol
        self.findings = findings
        self.confidence = confidence
        self.signals = signals or []
        self.risks = risks or []
        self.data_sources = data_sources or []
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "findings": self.findings,
            "confidence": self.confidence,
            "signals": self.signals,
            "risks": self.risks,
            "data_sources": self.data_sources,
            "timestamp": self.timestamp,
        }


def create_analyst_result(
    symbol: str,
    findings: dict[str, Any],
    confidence: float,
    **kwargs,
) -> dict[str, Any]:
    """Helper to create analyst result dict."""
    return AnalystResult(
        symbol=symbol,
        findings=findings,
        confidence=confidence,
        **kwargs,
    ).to_dict()