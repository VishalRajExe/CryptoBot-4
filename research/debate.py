"""
Debate orchestration for multi-agent research.
Adapted from TradingAgents' debate structure and OpenTerminalUI's debate orchestrator.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


class DebateOrchestrator:
    """
    Orchestrates bull/bear researcher debate and trader/risk decisions.
    """

    def __init__(
        self,
        max_rounds: int = 3,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o",
        temperature: float = 0.3,
    ):
        self.max_rounds = max_rounds
        self.llm = self._create_llm(llm_provider, llm_model, temperature)

    def _create_llm(self, provider: str, model: str, temperature: float):
        """Create LLM instance based on provider."""
        if provider == "openai":
            return ChatOpenAI(model=model, temperature=temperature)
        elif provider == "anthropic":
            return ChatAnthropic(model=model, temperature=temperature)
        elif provider == "google":
            return ChatGoogleGenerativeAI(model=model, temperature=temperature)
        else:
            # Default to OpenAI
            return ChatOpenAI(model="gpt-4o", temperature=temperature)

    async def bull_argument(
        self,
        symbols: list[str],
        analyses: dict[str, Any],
        trade_date: str,
    ) -> str:
        """Generate bull case argument."""
        prompt = self._build_bull_prompt(symbols, analyses, trade_date)
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        return response.content

    async def bear_argument(
        self,
        symbols: list[str],
        analyses: dict[str, Any],
        bull_case: str | None,
        trade_date: str,
    ) -> str:
        """Generate bear case argument."""
        prompt = self._build_bear_prompt(symbols, analyses, bull_case, trade_date)
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        return response.content

    async def synthesize(
        self,
        bull_case: str | None,
        bear_case: str | None,
        analyses: dict[str, Any],
    ) -> dict[str, Any]:
        """Synthesize bull/bear debate into consensus."""
        prompt = f"""Synthesize the following debate into a consensus view:

BULL CASE:
{bull_case or 'No bull case provided'}

BEAR CASE:
{bear_case or 'No bear case provided'}

ANALYSES:
{json.dumps(analyses, default=str, indent=2)}

Provide:
1. Consensus direction (bullish/bearish/neutral)
2. Key agreements between bull/bear
3. Key disagreements
4. Confidence level (0-1)
5. Most important risk factors
6. Recommended position sizing approach
"""
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])

        # Parse structured response
        return self._parse_synthesis(response.content)

    async def trader_decision(
        self,
        symbols: list[str],
        debate_synthesis: dict[str, Any] | None,
        analyses: dict[str, Any],
        portfolio_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Trader makes initial decision."""
        prompt = f"""You are a professional crypto trader making a decision.

SYMBOLS: {', '.join(symbols)}
PORTFOLIO: {json.dumps(portfolio_context, default=str) if portfolio_context else 'Empty'}

DEBATE SYNTHESIS:
{json.dumps(debate_synthesis, default=str, indent=2) if debate_synthesis else 'None'}

ANALYSES:
{json.dumps(analyses, default=str, indent=2)}

Provide your decision as JSON:
{{
    "decisions": [
        {{
            "symbol": "SYMBOL",
            "action": "buy|sell|hold",
            "size_pct": 0.05,
            "entry_price": 0,
            "stop_loss": 0,
            "take_profit": 0,
            "reasoning": "...",
            "confidence": 0.7
        }}
    ],
    "overall_thesis": "...",
    "risk_budget_used": 0.15
}}"""
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        return self._parse_json_response(response.content)

    async def portfolio_manager_decision(
        self,
        trader_decision: dict[str, Any] | None,
        risk_assessment: dict[str, Any] | None,
        debate_synthesis: dict[str, Any] | None,
        portfolio_context: dict[str, Any] | None,
        memory_context: str | None,
    ) -> dict[str, Any]:
        """Portfolio manager makes final decision."""
        prompt = f"""You are a Portfolio Manager making final allocation decisions.

TRADER DECISION:
{json.dumps(trader_decision, default=str, indent=2) if trader_decision else 'None'}

RISK ASSESSMENT:
{json.dumps(risk_assessment, default=str, indent=2) if risk_assessment else 'None'}

DEBATE SYNTHESIS:
{json.dumps(debate_synthesis, default=str, indent=2) if debate_synthesis else 'None'}

PORTFOLIO CONTEXT:
{json.dumps(portfolio_context, default=str, indent=2) if portfolio_context else 'Empty'}

MEMORY CONTEXT:
{memory_context or 'No relevant memory'}

Provide final decision as JSON:
{{
    "final_orders": [
        {{
            "symbol": "SYMBOL",
            "action": "buy|sell|hold",
            "size_pct": 0.05,
            "size_usd": 5000,
            "order_type": "market|limit",
            "limit_price": 0,
            "stop_loss": 0,
            "take_profit": 0,
            "time_in_force": "GTC",
            "priority": 1
        }}
    ],
    "rejected_trades": ["SYMBOL"],
    "portfolio_adjustments": {{}},
    "rationale": "...",
    "risk_limits_ok": true
}}"""
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        return self._parse_json_response(response.content)

    def _build_bull_prompt(
        self,
        symbols: list[str],
        analyses: dict[str, Any],
        trade_date: str,
    ) -> str:
        return f"""You are a BULL researcher arguing FOR long positions in crypto.

DATE: {trade_date}
SYMBOLS: {', '.join(symbols)}

ANALYSES FROM RESEARCH TEAM:
{json.dumps(analyses, default=str, indent=2)}

Your task: Build the strongest possible case for BUYING each symbol.
Focus on:
1. Positive technical setups
2. Favorable onchain metrics
3. Positive news catalysts
4. Macro tailwinds
5. Sentiment extremes that favor upside
6. Risk/reward asymmetries

Structure your argument:
- Per-symbol bull thesis (2-3 paragraphs each)
- Common themes across symbols
- Position sizing rationale
- Key risks you're accepting (and why they're manageable)
- Confidence level per symbol (0-1)

Be persuasive but intellectually honest. Acknowledge risks but explain why upside dominates.
"""

    def _build_bear_prompt(
        self,
        symbols: list[str],
        analyses: dict[str, Any],
        bull_case: str | None,
        trade_date: str,
    ) -> str:
        return f"""You are a BEAR researcher arguing AGAINST long positions / FOR short positions in crypto.

DATE: {trade_date}
SYMBOLS: {', '.join(symbols)}

ANALYSES FROM RESEARCH TEAM:
{json.dumps(analyses, default=str, indent=2)}

BULL CASE TO REFUTE:
{bull_case or 'No bull case provided'}

Your task: Build the strongest possible case for SELLING/SHORTING each symbol.
Focus on:
1. Technical breakdown risks
2. Negative onchain signals
3. Bearish news/regulatory risks
4. Macro headwinds
5. Sentiment extremes that favor downside
6. Asymmetric downside risks

Structure your argument:
- Per-symbol bear thesis (2-3 paragraphs each)
- Direct rebuttals to bull case points
- Position sizing rationale for shorts
- Key risks of being short (and why they're manageable)
- Confidence level per symbol (0-1)

Be persuasive but intellectually honest. Acknowledge upside but explain why downside dominates.
"""

    def _parse_synthesis(self, content: str) -> dict[str, Any]:
        """Parse synthesis response."""
        try:
            # Try to extract JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except Exception:
            pass
        return {
            "consensus": "neutral",
            "agreements": [],
            "disagreements": [],
            "confidence": 0.5,
            "risks": [],
            "sizing_approach": "standard",
            "raw": content,
        }

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except Exception:
            pass
        return {"error": "Failed to parse response", "raw": content}


class RiskDebateOrchestrator:
    """
    Three-way risk debate: Aggressive, Conservative, Neutral.
    Adapted from TradingAgents' risk management debate.
    """

    def __init__(
        self,
        max_rounds: int = 2,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o",
        temperature: float = 0.2,
    ):
        self.max_rounds = max_rounds
        self.llm = DebateOrchestrator(
            max_rounds=max_rounds,
            llm_provider=llm_provider,
            llm_model=llm_model,
            temperature=temperature,
        ).llm

    async def aggressive_assessment(
        self,
        decision: dict[str, Any] | None,
        analyses: dict[str, Any],
    ) -> dict[str, Any]:
        """Aggressive risk persona - favors taking risk."""
        prompt = f"""You are an AGGRESSIVE risk manager. Your job is to argue WHY the trade should proceed.

TRADER DECISION:
{json.dumps(decision, default=str, indent=2) if decision else 'None'}

ANALYSES:
{json.dumps(analyses, default=str, indent=2)}

Argue for:
- Why position sizing should be MAXIMUM allowed
- Why stop losses can be WIDER
- Why correlation/concentration limits can be STRETCHED
- Why the opportunity cost of NOT trading exceeds risk
- Specific risk mitigations that make this acceptable

Output JSON with: approved (bool), max_size_pct, stop_loss_pct, key_arguments[], concerns[]
"""
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        return self._parse_json_response(response.content)

    async def conservative_assessment(
        self,
        decision: dict[str, Any] | None,
        analyses: dict[str, Any],
    ) -> dict[str, Any]:
        """Conservative risk manager - argues against risk."""
        prompt = f"""You are a CONSERVATIVE risk manager. Your job is to PROTECT CAPITAL.

TRADER DECISION:
{json.dumps(decision, default=str, indent=2) if decision else 'None'}

ANALYSES:
{json.dumps(analyses, default=str, indent=2)}

Argue for:
- Why position sizing should be MINIMUM or ZERO
- Why stop losses should be TIGHTER
- Why correlation/concentration limits must be STRICT
- What scenarios could cause MAXIMUM LOSS
- Why the risk/reward is UNFAVORABLE

Output JSON with: approved (bool), max_size_pct, stop_loss_pct, key_arguments[], concerns[]
"""
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        return self._parse_json_response(response.content)

    async def neutral_assessment(
        self,
        decision: dict[str, Any] | None,
        aggressive: dict[str, Any] | None,
        conservative: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Neutral risk manager - balances both views."""
        prompt = f"""You are a NEUTRAL risk manager. Balance aggressive and conservative views.

TRADER DECISION:
{json.dumps(decision, default=str, indent=2) if decision else 'None'}

AGGRESSIVE VIEW:
{json.dumps(aggressive, default=str, indent=2) if aggressive else 'None'}

CONSERVATIVE VIEW:
{json.dumps(conservative, default=str, indent=2) if conservative else 'None'}

Provide balanced assessment:
- Final approved size (between aggressive max and conservative max)
- Final stop loss (between aggressive wide and conservative tight)
- Key conditions for approval
- Monitoring requirements
- Exit criteria

Output JSON with: approved (bool), final_size_pct, final_stop_pct, conditions[], monitoring[]
"""
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        return self._parse_json_response(response.content)

    async def synthesize(
        self,
        debate: list[dict[str, Any]],
        decision: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Synthesize risk debate into final assessment."""
        aggressive = next((d["assessment"] for d in debate if d["persona"] == "aggressive"), None)
        conservative = next((d["assessment"] for d in debate if d["persona"] == "conservative"), None)
        neutral = next((d["assessment"] for d in debate if d["persona"] == "neutral"), None)

        if neutral:
            return neutral

        # Fallback synthesis
        return {
            "approved": aggressive.get("approved", False) and conservative.get("approved", False),
            "final_size_pct": (aggressive.get("max_size_pct", 0) + conservative.get("max_size_pct", 0)) / 2,
            "final_stop_pct": (aggressive.get("stop_loss_pct", 0) + conservative.get("stop_loss_pct", 0)) / 2,
            "conditions": list(set(
                aggressive.get("key_arguments", []) + conservative.get("key_arguments", [])
            )),
            "monitoring": ["Price action", "Volume", "Funding rates", "News"],
        }