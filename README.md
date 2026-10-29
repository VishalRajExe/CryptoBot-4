# Cryptobot - Unified Crypto Trading Bot

A fully integrated, intelligent trading system combining the best features from 16 open-source trading repositories into one cohesive, production-ready system.

## 🚀 Features

### 📊 Multi-Market Data Layer
- **Unified Data Fetcher** with L1/L2 caching and provenance tracking
- **Fallback Chains** per market type (Spot, Linear, Inverse, Options, Futures)
- **Exchange Adapters** for Binance, Bybit, OKX, Hyperliquid, Deribit, Coinbase, Kraken
- **CCXT Fallback** for 100+ additional exchanges
- **Point-in-Time Integrity** guards against lookahead bias

### 🤖 Multi-Agent Research
- **5 Specialized Analysts**: Market, News, Onchain, Sentiment, Macro
- **LangGraph Orchestration** with parallel execution
- **Bull/Bear Debate** + 3-way Risk Debate
- **Kronos Foundation Model** for candlestick forecasting
- **Decision Memory Log** with settlement & reflection

### 📈 Strategy & Portfolio
- **6 Built-in Strategies**: Trend Follow, Mean Reversion, Momentum, Funding Arb, Grid Trading, DCA
- **Portfolio Optimization**: HRP, NCO, Risk Parity, Mean-Risk, Black-Litterman
- **Signal Engine** combining technical, pattern, ML, and fundamental signals
- **Parameter Optimization**: Random, Bayesian, Grid search + Walk-Forward validation

### ⚡ Risk Management
- **Pre-trade Checks**: Position limits, correlation, drawdown, leverage
- **Circuit Breakers**: Flash crash, volatility spikes, spread widening
- **Kill Switches**: Daily loss, max drawdown, API error limits
- **Position Sizing**: Fixed fractional, Kelly, Vol-target, Risk parity

### 🔄 Execution & Paper Trading
- **Multi-Exchange OMS** with idempotency keys
- **Bracket/OCO Orders** with TP/SL/Trailing
- **Paper Engine** with realistic slippage, commission, funding
- **Alpaca Integration** for equities + crypto paper trading

### 📊 Backtesting
- **Vectorized Engine** (vectorbt-style) for 10k+ strategies/sec
- **Event-Driven Engine** (Nautilus/backtesting.py style) for production parity
- **Walk-Forward & CPCV** validation
- **Monte Carlo** simulation for robustness

### 🖥️ Dashboard & Monitoring
- **React 19 Terminal** with Security Hub, Strategy Lab, Backtest, Research
- **Real-time WebSocket** updates for positions, orders, PnL
- **Interactive Charts** (Plotly) with equity curves, drawdowns, order books
- **Strategy Lab** visual builder with parameter optimization

### 🧠 Continuous Learning
- **Decision Memory Log** with atomic writes
- **Post-hoc Settlement** with alpha attribution
- **Shadow Account** tracking per strategy/analyst
- **Periodic Retraining** of Kronos and strategy parameters

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CRYPTOBOT                                  │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│    DATA     │  RESEARCH   │  STRATEGY   │    EXECUTION        │
│   LAYER     │   LAYER     │   LAYER     │     LAYER           │
├─────────────┼─────────────┼─────────────┼─────────────────────┤
│ Loaders     │ Analysts    │ Signals     │ Engine              │
│ Registry    │ (LLM)       │ Generator   │ (Perp/Spot)         │
│             │             │             │                     │
│ Caliber     │ Memory      │ Portfolio   │ Risk                │
│ Tracking    │ Log         │ Optimizer   │ Manager             │
│             │             │             │                     │
│ Unified     │ Tool        │ Time        │ Order               │
│ Fetcher     │ Registry    │ Machine     │ Manager             │
└─────────────┴─────────────┴─────────────┴─────────────────────┘
        │                │                │                │
        └────────────────┴────────────────┴────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    BACKTESTING      DASHBOARD       ORCHESTRATION
    (Vectorized +    (React Terminal   (Paperclip-
     Event-Driven)    + WebSocket)     style Agent
                                         Mgmt)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for dashboard)
- Redis (optional, for L2 cache)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd cryptobot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install dashboard dependencies
cd dashboard
npm install
cd ..

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `config/exchanges.yaml` with your API keys (or set via environment variables):

```bash
export BINANCE_API_KEY=your_key
export BINANCE_API_SECRET=your_secret
export BYBIT_API_KEY=your_key
export BYBIT_API_SECRET=your_secret
# ... etc
```

Set LLM provider keys for research agents:

```bash
export OPENAI_API_KEY=your_key
# or
export ANTHROPIC_API_KEY=your_key
# or
export GOOGLE_API_KEY=your_key
```

### Running

```bash
# Start the bot (API + Dashboard + Paper Trading)
python -m cryptobot

# Or run components separately:
# API server only
uvicorn cryptobot.api.main:app --host 0.0.0.0 --port 8000

# Dashboard only
cd dashboard && npm run dev

# Paper trading only
python -m cryptobot.execution.paper
```

Access dashboard at `http://localhost:8080`

## 📁 Project Structure

```
cryptobot/
├── config/                 # Configuration files
│   ├── settings.py         # Main settings (Pydantic v2)
│   ├── exchanges.yaml      # Exchange configurations
│   ├── strategies.yaml     # Strategy templates
│   └── risk.yaml           # Risk management rules
├── cryptobot/              # Main package
│   ├── main.py             # Entry point
│   ├── config/             # Settings module
│   ├── data/               # Data layer
│   │   ├── models.py       # Data models with provenance
│   │   ├── fetcher.py      # Unified fetcher with cache
│   │   ├── pit.py          # Point-in-time guards
│   │   └── loaders/        # Exchange loaders with fallbacks
│   ├── research/           # Multi-agent research
│   │   ├── graph.py        # LangGraph orchestration
│   │   ├── analysts/       # 5 specialized analysts
│   │   ├── debate.py       # Bull/Bear + Risk debate
│   │   ├── memory.py       # Decision memory log
│   │   ├── settlement.py   # Post-hoc settlement
│   │   ├── patterns/       # Technical patterns
│   │   ├── models/         # Kronos wrapper
│   │   └── tools/          # Tool registry with permissions
│   ├── strategy/           # Strategy generation
│   │   └── generator.py    # Signal engine
│   ├── portfolio/          # Portfolio optimization
│   │   └── optimizer.py    # skfolio-based optimizer
│   ├── risk/               # Risk management
│   │   └── manager.py      # Pre-trade checks, circuit breakers
│   ├── execution/          # Order execution
│   │   ├── adapters/       # Exchange adapters
│   │   ├── oms.py          # Order management system
│   │   └── paper.py        # Paper trading engine
│   ├── backtest/           # Backtesting engines
│   │   ├── engine.py       # Vectorized backtest
│   │   ├── event_engine.py # Event-driven backtest
│   │   ├── validation.py   # Walk-forward, CPCV, Monte Carlo
│   │   ├── metrics.py      # Comprehensive metrics
│   │   ├── report.py       # HTML/JSON reports
│   │   └── optimizer.py    # Parameter optimization
│   └── api/                # FastAPI backend
│       ├── main.py         # FastAPI app
│       └── routes/         # API routes
├── dashboard/              # React 19 + TypeScript dashboard
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── store/          # Zustand state management
│   │   ├── lib/            # API client & utilities
│   │   └── App.tsx         # Main app
│   └── package.json
├── tests/                  # Test suite
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project config
└── main.py                 # Main entry point
```

## 🔧 Configuration

### Settings (`config/settings.py`)

All configuration via Pydantic v2 with environment variable support:

```python
from cryptobot.config.settings import settings

# Access settings
settings.paper_trading          # True/False
settings.default_exchange       # "binance"
settings.risk.max_position_pct  # 0.10 (10%)
settings.dashboard.port         # 8080
```

### Exchanges (`config/exchanges.yaml`)

```yaml
binance:
  name: "binance"
  api_key: "${BINANCE_API_KEY}"
  api_secret: "${BINANCE_API_SECRET}"
  testnet: true
  rate_limit: 1200
  markets: ["spot", "linear"]
```

### Strategies (`config/strategies.yaml`)

```yaml
trend_follow:
  name: "trend_follow"
  parameters:
    fast_period: 10
    slow_period: 30
    adx_threshold: 20
```

### Risk (`config/risk.yaml`)

```yaml
position_sizing:
  default_method: "vol_target"
  vol_target:
    target_daily_vol: 0.015

portfolio_limits:
  max_position_pct: 0.10
  max_drawdown_pct: 0.15
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cryptobot --cov-report=html

# Run specific test file
pytest tests/test_backtest.py -v

# Run integration tests
pytest tests/integration/ -v
```

## 📊 Dashboard Features

- **Security Hub**: Real-time price, order book, funding, news, onchain
- **Strategy Lab**: Visual builder, parameter optimization, walk-forward
- **Backtest**: Run, optimize, walk-forward with HTML reports
- **Research**: Multi-agent analysis with debate history
- **Positions**: Real-time PnL, risk metrics, close positions
- **Orders**: History, filters, bracket order creation
- **Settings**: Exchanges, risk, LLM, strategies configuration

## 🔐 Security

- **No Private Keys** in code - all via environment variables
- **Paper Trading First** - live trading requires explicit opt-in
- **Circuit Breakers** prevent runaway losses
- **Audit Trail** - every decision logged with provenance
- **Rate Limiting** per exchange with automatic backoff

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

This project integrates ideas and patterns from 16 exceptional open-source trading repositories:

- **Lean** (QuantConnect) - Event-driven architecture
- **NautilusTrader** - Production-grade Rust/Python engine
- **Freqtrade** - Strategy framework & hyperopt
- **Hummingbot** - V2 Controllers & Executors
- **TradingAgents** - Multi-agent LLM framework
- **Vibe-Trading** - Paper trading & multi-market backtest
- **OpenTerminalUI** - Research terminal & tool registry
- **Kronos** - Foundation model for candlesticks
- **Skfolio** - Portfolio optimization
- **VectorBT** - Vectorized backtesting at scale
- **Backtesting.py** - Simple event-driven backtest
- **Day-Trader-Skill** - Pattern scanner & time machine
- **OpenBB** - Unified data access
- **Paperclip** - Agent orchestration
- **Awesome-Systematic-Trading** - Curated resource list
- **Beebots** - AI trading experiment lessons

---

**⚠️ Disclaimer**: This software is for educational and research purposes. Trading cryptocurrencies involves substantial risk of loss. Past performance does not guarantee future results. Never trade with money you cannot afford to lose.