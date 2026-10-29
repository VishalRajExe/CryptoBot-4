"""
Analysts package.
"""

from cryptobot.research.analysts.base import BaseAnalyst, AnalystResult, create_analyst_result
from cryptobot.research.analysts.market import MarketAnalyst
from cryptobot.research.analysts.news import NewsAnalyst
from cryptobot.research.analysts.onchain import OnchainAnalyst
from cryptobot.research.analysts.sentiment import SentimentAnalyst
from cryptobot.research.analysts.macro import MacroAnalyst

__all__ = [
    "BaseAnalyst",
    "AnalystResult",
    "create_analyst_result",
    "MarketAnalyst",
    "NewsAnalyst",
    "OnchainAnalyst",
    "SentimentAnalyst",
    "MacroAnalyst",
]