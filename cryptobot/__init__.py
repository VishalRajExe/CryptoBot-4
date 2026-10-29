"""
Cryptobot - Unified Crypto Trading Bot

A fully integrated, intelligent trading system combining the best features
from 16 open-source trading repositories into one cohesive system.
"""

__version__ = "0.1.0"
__author__ = "Cryptobot Team"
__email__ = "team@cryptobot.dev"

from cryptobot.config.settings import settings, load_settings
from cryptobot.config import config

from cryptobot.data import (
    Symbol,
    Candle,
    OrderBook,
    Trade,
    Ticker,
    FundingRate,
    MarketData,
    MarketType,
    DataSource,
    DataCaliber,
    Provenance,
    UnifiedFetcher,
    get_fetcher,
    close_fetcher,
    PITValidator,
)

from cryptobot.research import (
    ResearchGraph,
    MarketAnalyst,
    NewsAnalyst,
    OnchainAnalyst,
    SentimentAnalyst,
    MacroAnalyst,
    DebateOrchestrator,
    RiskDebateOrchestrator,
    TradingMemoryLog,
    SettlementEngine,
    TechnicalAnalyzer,
    AdvancedPatternDetector,
    MissedTradeTracker,
    PatternType,
    MarketRegime,
    KronosPredictor,
    get_kronos_tool,
)

from cryptobot.strategy import SignalEngine, StrategySignal

from cryptobot.portfolio import PortfolioOptimizer, FactorModelOptimizer, OptimizationResult

from cryptobot.risk import (
    PositionSizer,
    RiskManager,
    CircuitBreaker,
    KillSwitch,
    AdvancedRiskManager,
    PairLockManager,
    TrailingStopManager,
    TripleBarrierManager,
    VolatilityCircuitBreaker,
    CircuitBreakerManager,
)

from cryptobot.execution import (
    ExchangeAdapter,
    Order,
    OrderStatus,
    OrderSide,
    OrderType,
    TimeInForce,
    Position,
    Balance,
    OrderManager,
    PaperEngine,
    PaperAccount,
)

from cryptobot.backtest import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    EventBacktestEngine,
    Strategy,
    WalkForwardValidator,
    MonteCarloValidator,
    CPCVValidator,
    BacktestOptimizer,
    calculate_metrics,
    generate_backtest_report,
)

from cryptobot.integrations import (
    TelegramBot,
    TelegramConfig,
    start_telegram_bot,
    AlpacaAdapter,
    AlpacaPaperEngine,
    create_alpaca_engine,
)

__all__ = [
    # Config
    "settings",
    "load_settings",
    "config",
    # Data
    "Symbol",
    "Candle",
    "OrderBook",
    "Trade",
    "Ticker",
    "FundingRate",
    "MarketData",
    "MarketType",
    "DataSource",
    "DataCaliber",
    "Provenance",
    "UnifiedFetcher",
    "get_fetcher",
    "close_fetcher",
    "PITValidator",
    # Research
    "ResearchGraph",
    "MarketAnalyst",
    "NewsAnalyst",
    "OnchainAnalyst",
    "SentimentAnalyst",
    "MacroAnalyst",
    "DebateOrchestrator",
    "RiskDebateOrchestrator",
    "TradingMemoryLog",
    "SettlementEngine",
    "TechnicalAnalyzer",
    "AdvancedPatternDetector",
    "MissedTradeTracker",
    "PatternType",
    "MarketRegime",
    "KronosPredictor",
    "get_kronos_tool",
    # Strategy
    "SignalEngine",
    "StrategySignal",
    # Portfolio
    "PortfolioOptimizer",
    "FactorModelOptimizer",
    "OptimizationResult",
    # Risk
    "PositionSizer",
    "RiskManager",
    "CircuitBreaker",
    "KillSwitch",
    "AdvancedRiskManager",
    "PairLockManager",
    "TrailingStopManager",
    "TripleBarrierManager",
    "VolatilityCircuitBreaker",
    "CircuitBreakerManager",
    # Execution
    "ExchangeAdapter",
    "Order",
    "OrderStatus",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "Position",
    "Balance",
    "OrderManager",
    "PaperEngine",
    "PaperAccount",
    # Backtest
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "EventBacktestEngine",
    "Strategy",
    "WalkForwardValidator",
    "MonteCarloValidator",
    "CPCVValidator",
    "BacktestOptimizer",
    "calculate_metrics",
    "generate_backtest_report",
    # Integrations
    "TelegramBot",
    "TelegramConfig",
    "start_telegram_bot",
    "AlpacaAdapter",
    "AlpacaPaperEngine",
    "create_alpaca_engine",
]