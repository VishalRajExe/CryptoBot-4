"""
Multi-agent research framework using LangGraph.
Adapted from TradingAgents' TradingAgentsGraph with crypto-specific analysts.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from cryptobot.research.analysts.market import MarketAnalyst
from cryptobot.research.analysts.news import NewsAnalyst
from cryptobot.research.analysts.onchain import OnchainAnalyst
from cryptobot.research.analysts.sentiment import SentimentAnalyst
from cryptobot.research.analysts.macro import MacroAnalyst
from cryptobot.research.debate import DebateOrchestrator, RiskDebateOrchestrator
from cryptobot.research.memory import TradingMemoryLog
from cryptobot.research.settlement import SettlementEngine
from cryptobot.research.tools.registry import ToolRegistry
from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


class ResearchState(TypedDict):
    """State for the research graph."""

    # Input
    symbols: list[str]
    trade_date: str
    portfolio_context: dict[str, Any] | None

    # Analyst outputs
    market_analysis: dict[str, Any] | None
    news_analysis: dict[str, Any] | None
    onchain_analysis: dict[str, Any] | None
    sentiment_analysis: dict[str, Any] | None
    macro_analysis: dict[str, Any] | None

    # Debate outputs
    bull_case: str | None
    bear_case: str | None
    debate_history: list[dict[str, Any]]

    # Trader decision
    trader_decision: dict[str, Any] | None

    # Risk management
    risk_assessment: dict[str, Any] | None
    risk_debate: list[dict[str, Any]]

    # Final decision
    final_decision: dict[str, Any] | None

    # Memory
    memory_context: str | None
    settled_decisions: list[dict[str, Any]] | None

    # Metadata
    errors: list[str]
    current_step: str
    start_time: datetime


class ResearchGraph:
    """
    Main orchestrator for multi-agent crypto research.

    Flow:
    1. Parallel Analysts (Market, News, Onchain, Sentiment, Macro)
    2. Bull/Bear Researchers Debate
    3. Trader Decision
    4. Risk Management 3-way Debate (Aggressive/Conservative/Neutral)
    5. Portfolio Manager Final Decision
    6. Memory Logging & Settlement
    """

    def __init__(
        self,
        selected_analysts: tuple[str, ...] = ("market", "news", "onchain", "sentiment", "macro"),
        debug: bool = False,
        config: dict[str, Any] | None = None,
        checkpoint_enabled: bool = True,
    ):
        self.debug = debug
        self.config = config or {}
        self.selected_analysts = selected_analysts
        self.checkpoint_enabled = checkpoint_enabled

        # Initialize components
        self.memory_log = TradingMemoryLog(self.config.get("memory_log_path"))
        self.settlement_engine = SettlementEngine()
        self.tool_registry = ToolRegistry()

        # Analysts
        self.analysts = {
            "market": MarketAnalyst(self.tool_registry, self.config.get("market_analyst", {})),
            "news": NewsAnalyst(self.tool_registry, self.config.get("news_analyst", {})),
            "onchain": OnchainAnalyst(self.tool_registry, self.config.get("onchain_analyst", {})),
            "sentiment": SentimentAnalyst(self.tool_registry, self.config.get("sentiment_analyst", {})),
            "macro": MacroAnalyst(self.tool_registry, self.config.get("macro_analyst", {})),
        }

        # Debate orchestrators
        self.debate_orchestrator = DebateOrchestrator(
            max_rounds=self.config.get("max_debate_rounds", 3),
        )
        self.risk_debate_orchestrator = RiskDebateOrchestrator(
            max_rounds=self.config.get("max_risk_rounds", 2),
        )

        # Build graph
        self.graph = self._build_graph()
        self._checkpointer = None
        if checkpoint_enabled:
            self._init_checkpointer()

    def _init_checkpointer(self) -> None:
        """Initialize SQLite checkpointer for resume capability."""
        checkpoint_dir = Path(self.config.get("checkpoint_dir", "./checkpoints"))
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._checkpointer = SqliteSaver.from_conn_string(
            str(checkpoint_dir / "research_graph.db")
        )

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        graph = StateGraph(ResearchState)

        # Add nodes
        graph.add_node("initialize", self._initialize_node)
        graph.add_node("market_analyst", self._market_analyst_node)
        graph.add_node("news_analyst", self._news_analyst_node)
        graph.add_node("onchain_analyst", self._onchain_analyst_node)
        graph.add_node("sentiment_analyst", self._sentiment_analyst_node)
        graph.add_node("macro_analyst", self._macro_analyst_node)
        graph.add_node("load_memory", self._load_memory_node)
        graph.add_node("bull_researcher", self._bull_researcher_node)
        graph.add_node("bear_researcher", self._bear_researcher_node)
        graph.add_node("synthesize_debate", self._synthesize_debate_node)
        graph.add_node("trader", self._trader_node)
        graph.add_node("risk_aggressive", self._risk_aggressive_node)
        graph.add_node("risk_conservative", self._risk_conservative_node)
        graph.add_node("risk_neutral", self._risk_neutral_node)
        graph.add_node("synthesize_risk", self._synthesize_risk_node)
        graph.add_node("portfolio_manager", self._portfolio_manager_node)
        graph.add_node("save_memory", self._save_memory_node)
        graph.add_node("settle_decisions", self._settle_decisions_node)

        # Define edges - parallel analysts
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "load_memory")

        # Fan-out to analysts (only selected ones)
        for analyst in self.selected_analysts:
            graph.add_edge("load_memory", f"{analyst}_analyst")

        # Fan-in after analysts
        analyst_nodes = [f"{a}_analyst" for a in self.selected_analysts]
        for node in analyst_nodes:
            graph.add_edge(node, "bull_researcher")

        # Debate flow
        graph.add_edge("bull_researcher", "bear_researcher")
        graph.add_edge("bear_researcher", "synthesize_debate")
        graph.add_edge("synthesize_debate", "trader")
        graph.add_edge("trader", "risk_aggressive")
        graph.add_edge("risk_aggressive", "risk_conservative")
        graph.add_edge("risk_conservative", "risk_neutral")
        graph.add_edge("risk_neutral", "synthesize_risk")
        graph.add_edge("synthesize_risk", "portfolio_manager")
        graph.add_edge("portfolio_manager", "save_memory")
        graph.add_edge("save_memory", "settle_decisions")
        graph.add_edge("settle_decisions", END)

        return graph.compile(checkpointer=self._checkpointer)

    # Node implementations
    async def _initialize_node(self, state: ResearchState) -> ResearchState:
        """Initialize state with inputs."""
        state["errors"] = []
        state["debate_history"] = []
        state["risk_debate"] = []
        state["current_step"] = "initialize"
        state["start_time"] = datetime.utcnow()
        return state

    async def _load_memory_node(self, state: ResearchState) -> ResearchState:
        """Load relevant memory from past decisions."""
        state["current_step"] = "load_memory"
        try:
            # Get memory for each symbol
            memory_parts = []
            for symbol in state["symbols"]:
                memory = self.memory_log.get_recent(symbol, limit=5)
                if memory:
                    memory_parts.append(f"=== {symbol} ===\n{memory}")

            # Get settled decisions for learning
            settled = self.settlement_engine.get_pending_settlement()
            state["settled_decisions"] = settled

            state["memory_context"] = "\n\n".join(memory_parts) if memory_parts else "No prior memory."
        except Exception as e:
            logger.error(f"Memory load error: {e}")
            state["errors"].append(f"Memory load: {e}")
            state["memory_context"] = "Memory unavailable."
        return state

    async def _run_analyst(self, state: ResearchState, analyst_name: str) -> ResearchState:
        """Run a single analyst."""
        state["current_step"] = f"{analyst_name}_analyst"
        analyst = self.analysts.get(analyst_name)
        if not analyst:
            state["errors"].append(f"Unknown analyst: {analyst_name}")
            return state

        try:
            result = await analyst.analyze(
                symbols=state["symbols"],
                trade_date=state["trade_date"],
                portfolio_context=state.get("portfolio_context"),
                memory_context=state.get("memory_context"),
            )
            state[f"{analyst_name}_analysis"] = result
        except Exception as e:
            logger.error(f"{analyst_name} analyst error: {e}")
            state["errors"].append(f"{analyst_name} analyst: {e}")
            state[f"{analyst_name}_analysis"] = {"error": str(e)}
        return state

    async def _market_analyst_node(self, state: ResearchState) -> ResearchState:
        return await self._run_analyst(state, "market")

    async def _news_analyst_node(self, state: ResearchState) -> ResearchState:
        return await self._run_analyst(state, "news")

    async def _onchain_analyst_node(self, state: ResearchState) -> ResearchState:
        return await self._run_analyst(state, "onchain")

    async def _sentiment_analyst_node(self, state: ResearchState) -> ResearchState:
        return await self._run_analyst(state, "sentiment")

    async def _macro_analyst_node(self, state: ResearchState) -> ResearchState:
        return await self._run_analyst(state, "macro")

    async def _bull_researcher_node(self, state: ResearchState) -> ResearchState:
        """Bull researcher argues for long positions."""
        state["current_step"] = "bull_researcher"
        try:
            bull_case = await self.debate_orchestrator.bull_argument(
                symbols=state["symbols"],
                analyses={k: v for k, v in state.items() if k.endswith("_analysis")},
                trade_date=state["trade_date"],
            )
            state["bull_case"] = bull_case
            state["debate_history"].append({"role": "bull", "content": bull_case})
        except Exception as e:
            logger.error(f"Bull researcher error: {e}")
            state["errors"].append(f"Bull researcher: {e}")
        return state

    async def _bear_researcher_node(self, state: ResearchState) -> ResearchState:
        """Bear researcher argues against / for short positions."""
        state["current_step"] = "bear_researcher"
        try:
            bear_case = await self.debate_orchestrator.bear_argument(
                symbols=state["symbols"],
                analyses={k: v for k, v in state.items() if k.endswith("_analysis")},
                bull_case=state.get("bull_case"),
                trade_date=state["trade_date"],
            )
            state["bear_case"] = bear_case
            state["debate_history"].append({"role": "bear", "content": bear_case})
        except Exception as e:
            logger.error(f"Bear researcher error: {e}")
            state["errors"].append(f"Bear researcher: {e}")
        return state

    async def _synthesize_debate_node(self, state: ResearchState) -> ResearchState:
        """Synthesize bull/bear debate into consensus view."""
        state["current_step"] = "synthesize_debate"
        try:
            synthesis = await self.debate_orchestrator.synthesize(
                bull_case=state.get("bull_case"),
                bear_case=state.get("bear_case"),
                analyses={k: v for k, v in state.items() if k.endswith("_analysis")},
            )
            state["debate_synthesis"] = synthesis
        except Exception as e:
            logger.error(f"Debate synthesis error: {e}")
            state["errors"].append(f"Debate synthesis: {e}")
        return state

    async def _trader_node(self, state: ResearchState) -> ResearchState:
        """Trader makes initial decision based on research."""
        state["current_step"] = "trader"
        try:
            decision = await self.debate_orchestrator.trader_decision(
                symbols=state["symbols"],
                debate_synthesis=state.get("debate_synthesis"),
                analyses={k: v for k, v in state.items() if k.endswith("_analysis")},
                portfolio_context=state.get("portfolio_context"),
            )
            state["trader_decision"] = decision
        except Exception as e:
            logger.error(f"Trader error: {e}")
            state["errors"].append(f"Trader: {e}")
        return state

    async def _risk_aggressive_node(self, state: ResearchState) -> ResearchState:
        """Aggressive risk persona - favors taking risk."""
        state["current_step"] = "risk_aggressive"
        try:
            assessment = await self.risk_debate_orchestrator.aggressive_assessment(
                decision=state.get("trader_decision"),
                analyses={k: v for k, v in state.items() if k.endswith("_analysis")},
            )
            state["risk_debate"].append({"persona": "aggressive", "assessment": assessment})
        except Exception as e:
            logger.error(f"Risk aggressive error: {e}")
            state["errors"].append(f"Risk aggressive: {e}")
        return state

    async def _risk_conservative_node(self, state: ResearchState) -> ResearchState:
        """Conservative risk persona - avoids risk."""
        state["current_step"] = "risk_conservative"
        try:
            assessment = await self.risk_debate_orchestrator.conservative_assessment(
                decision=state.get("trader_decision"),
                analyses={k: v for k, v in state.items() if k.endswith("_analysis")},
            )
            state["risk_debate"].append({"persona": "conservative", "assessment": assessment})
        except Exception as e:
            logger.error(f"Risk conservative error: {e}")
            state["errors"].append(f"Risk conservative: {e}")
        return state

    async def _risk_neutral_node(self, state: ResearchState) -> ResearchState:
        """Neutral risk persona - balanced view."""
        state["current_step"] = "risk_neutral"
        try:
            assessment = await self.risk_debate_orchestrator.neutral_assessment(
                decision=state.get("trader_decision"),
                aggressive=state["risk_debate"][0]["assessment"] if state["risk_debate"] else None,
                conservative=state["risk_debate"][1]["assessment"] if len(state["risk_debate"]) > 1 else None,
            )
            state["risk_debate"].append({"persona": "neutral", "assessment": assessment})
        except Exception as e:
            logger.error(f"Risk neutral error: {e}")
            state["errors"].append(f"Risk neutral: {e}")
        return state

    async def _synthesize_risk_node(self, state: ResearchState) -> ResearchState:
        """Synthesize risk debate into final risk assessment."""
        state["current_step"] = "synthesize_risk"
        try:
            risk_assessment = await self.risk_debate_orchestrator.synthesize(
                debate=state["risk_debate"],
                decision=state.get("trader_decision"),
            )
            state["risk_assessment"] = risk_assessment
        except Exception as e:
            logger.error(f"Risk synthesis error: {e}")
            state["errors"].append(f"Risk synthesis: {e}")
        return state

    async def _portfolio_manager_node(self, state: ResearchState) -> ResearchState:
        """Portfolio manager makes final decision."""
        state["current_step"] = "portfolio_manager"
        try:
            final = await self.debate_orchestrator.portfolio_manager_decision(
                trader_decision=state.get("trader_decision"),
                risk_assessment=state.get("risk_assessment"),
                debate_synthesis=state.get("debate_synthesis"),
                portfolio_context=state.get("portfolio_context"),
                memory_context=state.get("memory_context"),
            )
            state["final_decision"] = final
        except Exception as e:
            logger.error(f"Portfolio manager error: {e}")
            state["errors"].append(f"Portfolio manager: {e}")
        return state

    async def _save_memory_node(self, state: ResearchState) -> ResearchState:
        """Save decision to memory log."""
        state["current_step"] = "save_memory"
        try:
            if state.get("final_decision"):
                for symbol in state["symbols"]:
                    self.memory_log.append_decision(
                        symbol=symbol,
                        date=state["trade_date"],
                        decision=state["final_decision"],
                        analyses={k: v for k, v in state.items() if k.endswith("_analysis")},
                        debate_history=state.get("debate_history", []),
                        risk_debate=state.get("risk_debate", []),
                    )
        except Exception as e:
            logger.error(f"Memory save error: {e}")
            state["errors"].append(f"Memory save: {e}")
        return state

    async def _settle_decisions_node(self, state: ResearchState) -> ResearchState:
        """Settle past decisions with realized outcomes."""
        state["current_step"] = "settle_decisions"
        try:
            settled = await self.settlement_engine.settle_pending()
            state["settled_decisions"] = settled
        except Exception as e:
            logger.error(f"Settlement error: {e}")
            state["errors"].append(f"Settlement: {e}")
        return state

    # Public API
    async def run(
        self,
        symbols: list[str],
        trade_date: str | None = None,
        portfolio_context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> ResearchState:
        """
        Run the research graph.

        Args:
            symbols: List of symbols to analyze
            trade_date: Date for analysis (YYYY-MM-DD), defaults to today
            portfolio_context: Current portfolio positions
            thread_id: Checkpoint thread ID for resume

        Returns:
            Final state with decision
        """
        trade_date = trade_date or datetime.utcnow().strftime("%Y-%m-%d")

        initial_state: ResearchState = {
            "symbols": symbols,
            "trade_date": trade_date,
            "portfolio_context": portfolio_context,
            "market_analysis": None,
            "news_analysis": None,
            "onchain_analysis": None,
            "sentiment_analysis": None,
            "macro_analysis": None,
            "bull_case": None,
            "bear_case": None,
            "debate_history": [],
            "trader_decision": None,
            "risk_assessment": None,
            "risk_debate": [],
            "final_decision": None,
            "memory_context": None,
            "settled_decisions": None,
            "errors": [],
            "current_step": "",
            "start_time": datetime.utcnow(),
        }

        config = {"configurable": {"thread_id": thread_id or f"research_{trade_date}_{'_'.join(symbols)}"}}

        result = await self.graph.ainvoke(initial_state, config=config)
        return result

    async def run_stream(
        self,
        symbols: list[str],
        trade_date: str | None = None,
        portfolio_context: dict[str, Any] | None = None,
    ) -> Callable[[], ResearchState]:
        """Run graph and yield intermediate states."""
        # Implementation for streaming updates
        pass