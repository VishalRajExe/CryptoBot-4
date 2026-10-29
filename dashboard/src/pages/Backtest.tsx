import { useState } from 'react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { EquityChart } from '@/components/EquityChart'

export function BacktestPage() {
  const [activeTab, setActiveTab] = useState('run')
  const [backtests, setBacktests] = useState<any[]>([])
  const [selectedBacktest, setSelectedBacktest] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const tabs = [
    { id: 'run', label: 'Run Backtest', icon: 'Play' },
    { id: 'optimize', label: 'Optimize', icon: 'Sliders' },
    { id: 'walkforward', label: 'Walk-Forward', icon: 'RotateCcw' },
    { id: 'history', label: 'History', icon: 'History' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-text">Backtest</h1>
          <p className="text-dark-muted">Test strategies on historical data</p>
        </div>
        <button className="btn-primary" onClick={() => setActiveTab('run')}>New Backtest</button>
      </div>

      <div className="border-b border-dark-border">
        <nav className="flex gap-1 px-4" aria-label="Tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-500'
                  : 'border-transparent text-dark-muted hover:text-dark-text hover:border-dark-border'
              )}
            >
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'run' && <BacktestForm onSubmit={handleSubmit} />}
      {activeTab === 'optimize' && <OptimizationForm />}
      {activeTab === 'walkforward' && <WalkForwardForm />}
      {activeTab === 'history' && <BacktestHistory backtests={backtests} onSelect={setSelectedBacktest} />}

      {selectedBacktest && <BacktestResultsModal backtest={selectedBacktest} onClose={() => setSelectedBacktest(null)} />}
    </div>
  )

  async function handleSubmit(data: any) {
    setLoading(true)
    try {
      const response = await api.runBacktest(data)
      setBacktests(prev => [response.data, ...prev])
      setSelectedBacktest(response.data)
    } catch (error) {
      console.error('Backtest failed:', error)
    } finally {
      setLoading(false)
    }
  }
}

function BacktestForm({ onSubmit }: { onSubmit: (data: any) => void }) {
  const [formData, setFormData] = useState({
    symbols: ['BTC/USDT', 'ETH/USDT'],
    timeframe: '1h',
    start_date: '',
    end_date: '',
    initial_cash: 100000,
    commission: 0.0005,
    slippage: 0.0002,
    strategy_type: 'trend_follow',
    strategy_params: {},
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value,
    }))
  }

  const handleSubmitForm = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <div className="p-4">
      <form onSubmit={handleSubmitForm} className="max-w-3xl mx-auto space-y-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-dark-text mb-4">Strategy Configuration</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Strategy</label>
                <select
                  name="strategy_type"
                  value={formData.strategy_type}
                  onChange={handleChange}
                  className="input"
                >
                  <option value="trend_follow">Trend Following</option>
                  <option value="mean_reversion">Mean Reversion</option>
                  <option value="momentum">Momentum</option>
                  <option value="funding_arbitrage">Funding Arbitrage</option>
                  <option value="grid_trading">Grid Trading</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Symbols (comma-separated)</label>
                <input
                  name="symbols"
                  type="text"
                  value={formData.symbols.join(', ')}
                  onChange={handleChange}
                  className="input"
                  placeholder="BTC/USDT, ETH/USDT, SOL/USDT"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Timeframe</label>
                <select name="timeframe" value={formData.timeframe} onChange={handleChange} className="input">
                  <option value="1m">1 Minute</option>
                  <option value="5m">5 Minutes</option>
                  <option value="15m">15 Minutes</option>
                  <option value="1h">1 Hour</option>
                  <option value="4h">4 Hours</option>
                  <option value="1d">1 Day</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Start Date</label>
                <input type="date" name="start_date" className="input" />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">End Date</label>
                <input type="date" name="end_date" className="input" />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Initial Capital ($)</label>
                <input type="number" name="initial_cash" defaultValue={100000} className="input" min={1000} />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Commission (bps)</label>
                <input type="number" name="commission" step="0.1" defaultValue={5} className="input" min={0} />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Slippage (bps)</label>
                <input type="number" name="slippage" step="0.1" defaultValue={2} className="input" min={0} />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-dark-border">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </form>
    </div>
  )
}

function OptimizationForm() {
  return (
    <div className="p-4">
      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Parameter Optimization</h3>
        <form className="max-w-2xl mx-auto space-y-6">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Strategy</label>
            <select className="input">
              <option value="">Select strategy</option>
              <option value="trend_follow">Trend Following</option>
              <option value="mean_reversion">Mean Reversion</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-text mb-4">Parameter Space</label>
            <div className="space-y-3">
              <ParameterRow name="fast_period" min={5} max={50} default={10} />
              <ParameterRow name="slow_period" min={10} max={200} default={30} />
              <ParameterRow name="adx_threshold" min={10} max={40} default={20} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1">Method</label>
              <select className="input">
                <option value="random">Random Search</option>
                <option value="bayesian">Bayesian Optimization</option>
                <option value="grid">Grid Search</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1">Trials</label>
              <input type="number" defaultValue={50} className="input" min={10} max={1000} />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1">Metric</label>
              <select className="input">
                <option value="sharpe_ratio">Sharpe Ratio</option>
                <option value="total_return_pct">Total Return</option>
                <option value="max_drawdown_pct">Max Drawdown (minimize)</option>
                <option value="profit_factor">Profit Factor</option>
              </select>
            </div>
          </div>

          <button type="submit" className="btn-primary w-full">Start Optimization</button>
        </form>
      </div>
    </div>
  )
}

function ParameterRow({ name, min, max, default: def }: { name: string; min: number; max: number; default: number }) {
  return (
    <div className="grid grid-cols-4 gap-4">
      <label className="text-sm text-dark-text capitalize">{name.replace('_', ' ')}</label>
      <input type="number" className="input" placeholder="Min" defaultValue={min} />
      <input type="number" className="input" placeholder="Max" defaultValue={max} />
      <select className="input">
        <option value="uniform">Uniform</option>
        <option value="loguniform">Log-Uniform</option>
        <option value="int">Integer</option>
      </select>
    </div>
  )
}

function WalkForwardForm() {
  return (
    <div className="p-4">
      <div className="card max-w-2xl mx-auto">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Walk-Forward Validation</h3>
        <form className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Strategy</label>
            <select className="input">
              <option value="">Select strategy</option>
              <option value="trend_follow">Trend Following</option>
              <option value="mean_reversion">Mean Reversion</option>
            </select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1">Train Window (days)</label>
              <input type="number" defaultValue={252} className="input" min={50} />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1">Test Window (days)</label>
              <input type="number" defaultValue={60} className="input" min={20} />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1">Step (days)</label>
              <input type="number" defaultValue={21} className="input" min={7} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-1">Anchor</label>
            <select className="input">
              <option value="expanding">Expanding</option>
              <option value="rolling">Rolling</option>
            </select>
          </div>
          <button type="submit" className="btn-primary w-full">Run Walk-Forward</button>
        </form>
      </div>
    </div>
  )
}

function BacktestHistory({ backtests, onSelect }: { backtests: any[]; onSelect: (b: any) => void }) {
  if (backtests.length === 0) {
    return (
      <div className="text-center py-12 text-dark-muted">
        <svg className="w-16 h-16 mx-auto mb-4 text-dark-border" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-lg font-medium mb-2">No backtests yet</p>
        <p className="text-dark-muted">Run your first backtest to see results here</p>
      </div>
    )
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Strategy</th>
            <th>Symbols</th>
            <th>Period</th>
            <th className="text-right">Return</th>
            <th className="text-right">Sharpe</th>
            <th className="text-right">Max DD</th>
            <th className="text-right">Trades</th>
            <th>Status</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {backtests.map(bt => (
            <tr key={bt.backtest_id} className="cursor-pointer hover:bg-dark-border/50" onClick={() => onSelect(bt)}>
              <td className="font-mono text-sm">{bt.backtest_id}</td>
              <td className="font-medium">{bt.request?.strategy_type || 'N/A'}</td>
              <td className="text-dark-muted text-sm">{bt.request?.symbols?.join(', ') || 'N/A'}</td>
              <td className="text-sm">
                {bt.request?.start_date ? new Date(bt.request.start_date).toLocaleDateString() : 'N/A'} -
                {bt.request?.end_date ? new Date(bt.request.end_date).toLocaleDateString() : 'N/A'}
              </td>
              <td className="text-right font-mono font-medium text-success-500">{bt.metrics?.total_return_pct?.toFixed(2) || 0}%</td>
              <td className="text-right font-mono">{bt.metrics?.sharpe_ratio?.toFixed(2) || 'N/A'}</td>
              <td className="text-right font-mono text-danger-500">{bt.metrics?.max_drawdown_pct?.toFixed(2) || 0}%</td>
              <td className="text-right text-sm">{bt.metrics?.total_trades || 0}</td>
              <td>
                <span className={cn('badge', bt.status === 'completed' ? 'badge-success' : bt.status === 'running' ? 'badge-warning' : 'badge-danger')}>
                  {bt.status}
                </span>
              </td>
              <td className="text-sm text-dark-muted">{new Date(bt.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BacktestResultsModal({ backtest, onClose }: { backtest: any; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-dark-card rounded-xl border border-dark-border max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-dark-border">
          <h3 className="text-lg font-semibold text-dark-text">Backtest Results: {backtest.backtest_id}</h3>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-dark-border transition-colors">
            <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <MetricCard label="Total Return" value={`${backtest.metrics?.total_return_pct?.toFixed(2) || 0}%`} positive={backtest.metrics?.total_return_pct >= 0} icon="TrendingUp" />
            <MetricCard label="Sharpe Ratio" value={backtest.metrics?.sharpe_ratio?.toFixed(2) || 'N/A'} icon="BarChart3" />
            <MetricCard label="Max Drawdown" value={`${backtest.metrics?.max_drawdown_pct?.toFixed(2) || 0}%`} positive={false} icon="TrendingDown" />
            <MetricCard label="Win Rate" value={`${backtest.metrics?.win_rate_pct?.toFixed(1) || 0}%`} icon="Percent" />
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Equity Curve</h3>
            <EquityChart accountId={null} />
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Trade Details</h3>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th className="text-right">Entry</th>
                    <th className="text-right">Exit</th>
                    <th className="text-right">PnL</th>
                    <th className="text-right">PnL %</th>
                    <th className="text-right">Hold (h)</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.trades?.slice(0, 20).map((trade: any, i: number) => (
                    <tr key={i}>
                      <td>{new Date(trade.entry_time).toLocaleString()}</td>
                      <td>{new Date(trade.exit_time).toLocaleString()}</td>
                      <td className="font-mono">{trade.symbol}</td>
                      <td>
                        <span className={cn('badge', trade.side === 'long' ? 'badge-success' : 'badge-danger')}>
                          {trade.side?.toUpperCase()}
                        </span>
                      </td>
                      <td className="text-right font-mono">${trade.entry_price?.toFixed(2)}</td>
                      <td className="text-right font-mono">${trade.exit_price?.toFixed(2)}</td>
                      <td className={cn('text-right font-mono font-medium', trade.pnl >= 0 ? 'text-success-500' : 'text-danger-500')}>
                        ${trade.pnl?.toFixed(2)}
                      </td>
                      <td className={cn('text-right font-mono font-medium', trade.pnl_pct >= 0 ? 'text-success-500' : 'text-danger-500')}>
                        {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct?.toFixed(2)}%
                      </td>
                      <td className="text-right text-sm">{trade.holding_period?.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-dark-border">
            <button onClick={onClose} className="btn-secondary">Close</button>
            <button className="btn-primary">Export Report</button>
          </div>
        </div>
      </div>
    </div>
  )
}