"""
Test imports to verify all modules load correctly.
"""

import pytest


def test_config_imports():
    """Test config module imports."""
    from cryptobot.config.settings import settings
    from cryptobot.config import config

    assert settings is not None
    assert config is not None


def test_data_imports():
    """Test data module imports."""
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

    # Test basic instantiation
    sym = Symbol(base="BTC", quote="USDT", exchange="binance")
    assert sym.base == "BTC"
    assert sym.quote == "USDT"

    candle = Candle(
        symbol=sym,
        timestamp="2024-01-01T00:00:00",
        open=50000,
        high=51000,
        low=49000,
        close=50500,
        volume=100,
    )
    assert candle.close == 50500


def test_research_imports():
    """Test research module imports."""
    from cryptobot.research import (
        ResearchGraph,
        MarketAnalyst,
        NewsAnalyst,
        OnchainAnalyst,
        SentimentAnalyst,
        MacroAnalyst,
        TechnicalAnalyzer,
        AdvancedPatternDetector,
        MissedTradeTracker,
        PatternType,
        MarketRegime,
        KronosPredictor,
        get_kronos_tool,
    )

    # Test pattern type enum
    assert PatternType.FVG_BULLISH.value == "fvg_bullish"
    assert MarketRegime.BULLISH.value == "bullish"


def test_strategy_imports():
    """Test strategy module imports."""
    from cryptobot.strategy import SignalEngine, StrategySignal

    engine = SignalEngine()
    assert engine is not None


def test_portfolio_imports():
    """Test portfolio module imports."""
    from cryptobot.portfolio import PortfolioOptimizer, FactorModelOptimizer, OptimizationResult

    optimizer = PortfolioOptimizer()
    assert optimizer is not None


def test_risk_imports():
    """Test risk module imports."""
    from cryptobot.risk import (
        PositionSizer,
        RiskManager,
        AdvancedRiskManager,
        PairLockManager,
        TrailingStopManager,
        TripleBarrierManager,
    )

    sizer = PositionSizer()
    manager = RiskManager()
    advanced = AdvancedRiskManager()
    assert sizer is not None
    assert manager is not None
    assert advanced is not None


def test_execution_imports():
    """Test execution module imports."""
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
    )

    order = Order(
        id="test",
        client_order_id="test",
        symbol=None,
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        quantity=1.0,
    )
    assert order.side == OrderSide.BUY


def test_backtest_imports():
    """Test backtest module imports."""
    from cryptobot.backtest import (
        BacktestEngine,
        BacktestConfig,
        BacktestResult,
        BacktestOptimizer,
        WalkForwardValidator,
    )

    engine = BacktestEngine()
    assert engine is not None


def test_execution_imports():
    """Test execution module imports."""
    from cryptobot.execution import PaperEngine, PaperAccount

    engine = PaperEngine()
    assert engine is not None


def test_integrations_imports():
    """Test integrations module imports."""
    from cryptobot.integrations import (
        TelegramBot,
        TelegramConfig,
        AlpacaAdapter,
        AlpacaPaperEngine,
    )

    config = TelegramConfig(bot_token="test", chat_id="123")
    assert config.bot_token == "test"


def test_main_import():
    """Test main package import."""
    import cryptobot

    assert cryptobot.__version__ == "0.1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])