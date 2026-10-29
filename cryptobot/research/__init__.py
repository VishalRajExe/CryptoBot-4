"""
Research package.
"""

from cryptobot.research.graph import ResearchGraph, ResearchState
from cryptobot.research.analysts import (
    BaseAnalyst,
    MarketAnalyst,
    NewsAnalyst,
    OnchainAnalyst,
    SentimentAnalyst,
    MacroAnalyst,
    create_analyst_result,
)
from cryptobot.research.debate import DebateOrchestrator, RiskDebateOrchestrator
from cryptobot.research.memory import TradingMemoryLog
from cryptobot.research.settlement import SettlementEngine
from cryptobot.research.patterns import TechnicalAnalyzer, compute_signals, AdvancedPatternDetector, MissedTradeTracker, PatternType, MarketRegime
from cryptobot.research.models import KronosPredictor, KronosTool, get_kronos_tool
from cryptobot.research.tools import tool_registry, tool

__all__ = [
    "ResearchGraph",
    "ResearchState",
    "BaseAnalyst",
    "MarketAnalyst",
    "NewsAnalyst",
    "OnchainAnalyst",
    "SentimentAnalyst",
    "MacroAnalyst",
    "create_analyst_result",
    "DebateOrchestrator",
    "RiskDebateOrchestrator",
    "TradingMemoryLog",
    "SettlementEngine",
    "TechnicalAnalyzer",
    "compute_signals",
    "AdvancedPatternDetector",
    "MissedTradeTracker",
    "PatternType",
    "MarketRegime",
    "KronosPredictor",
    "KronosTool",
    "get_kronos_tool",
    "tool_registry",
    "tool",
]