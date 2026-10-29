import { useState } from 'react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

export function StrategyLab() {
  const [activeTab, setActiveTab] = useState('builder')
  const [strategies, setStrategies] = useState<any[]>([])
  const [selectedStrategy, setSelectedStrategy] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const tabs = [
    { id: 'builder', label: 'Strategy Builder', icon: 'FlaskConical' },
    { id: 'backtest', label: 'Backtest', icon: 'BarChart3' },
    { id: 'optimizer', label: 'Optimizer', icon: 'Sliders' },
    { id: 'library', label: 'Library', icon: 'BookOpen' },
  ]

  const builtInStrategies = [
    {
      id: 'trend_follow',
      name: 'Trend Following',
      description: 'Multi-timeframe EMA crossover with ADX filter',
      category: 'Trend',
      parameters: {
        fast_period: { type: 'int', default: 10, min: 5, max: 50 },
        slow_period: { type: 'int', default: 30, min: 10, max: 200 },
        adx_threshold: { type: 'int', default: 20, min: 10, max: 40 },
      },
    },
    {
      id: 'mean_reversion',
      name: 'Mean Reversion',
      description: 'Bollinger Bands + RSI oversold/overbought',
      category: 'Mean Reversion',
      parameters: {
        bb_period: { type: 'int', default: 20, min: 10, max: 50 },
        bb_std: { type: 'float', default: 2.0, min: 1.0, max: 3.0 },
        rsi_period: { type: 'int', default: 14, min: 7, max: 30 },
        rsi_oversold: { type: 'int', default: 30, min: 10, max: 40 },
        rsi_overbought: { type: 'int', default: 70, min: 60, max: 90 },
      },
    },
    {
      id: 'funding_arbitrage',
      name: 'Funding Arbitrage',
      description: 'Capture funding rate differentials across exchanges',
      category: 'Arbitrage',
      parameters: {
        min_funding_diff: { type: 'float', default: 0.0001, min: 0, max: 0.01 },
        max_leverage: { type: 'float', default: 2.0, min: 1, max: 10 },
      },
    },
    {
      id: 'momentum',
      name: 'Cross-sectional Momentum',
      description: 'Top N momentum assets with volatility targeting',
      category: 'Momentum',
      parameters: {
        lookback_days: { type: 'int', default: 30, min: 7, max: 90 },
        top_n: { type: 'int', default: 10, min: 5, max: 50 },
        target_vol: { type: 'float', default: 0.15, min: 0.05, max: 0.5 },
      },
    },
    {
      id: 'grid_trading',
      name: 'Grid Trading',
      description: 'Automated grid orders for ranging markets',
      category: 'Market Making',
      parameters: {
        grid_levels: { type: 'int', default: 20, min: 5, max: 100 },
        grid_spacing: { type: 'float', default: 0.005, min: 0.001, max: 0.02 },
        base_order_size: { type: 'float', default: 0.02, min: 0.005, max: 0.1 },
      },
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-text">Strategy Lab</h1>
          <p className="text-dark-muted">Build, test, and deploy trading strategies</p>
        </div>
        <button className="btn-primary" onClick={() => setSelectedStrategy(null)}>New Strategy</button>
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

      {activeTab === 'builder' && <StrategyBuilder strategies={builtInStrategies} onSelect={setSelectedStrategy} />}
      {activeTab === 'backtest' && <StrategyBacktest />}
      {activeTab === 'optimizer' && <StrategyOptimizer />}
      {activeTab === 'library' && <StrategyLibrary strategies={builtInStrategies} onSelect={setSelectedStrategy} />}

      {selectedStrategy && <StrategyDetailModal strategy={selectedStrategy} onClose={() => setSelectedStrategy(null)} />}
    </div>
  )
}

function StrategyBuilder({ strategies, onSelect }: { strategies: any[]; onSelect: (s: any) => void }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-4">
      <div className="lg:col-span-2 space-y-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-dark-text mb-4">Create New Strategy</h3>
          <form className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Strategy Name</label>
              <input type="text" className="input" placeholder="My Custom Strategy" />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Base Template</label>
              <select className="input">
                <option value="">Start from scratch</option>
                {builtInStrategies.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Description</label>
              <textarea className="input" rows={3} placeholder="Describe your strategy logic..." />
            </div>
            <button type="submit" className="btn-primary w-full">Create Strategy</button>
          </form>
        </div>

        {selectedStrategy && (
          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Parameters</h3>
            <div className="space-y-4">
              {Object.entries(selectedStrategy.parameters || {}).map(([key, param]: [string, any]) => (
                <div key={key} className="flex items-center gap-4">
                  <label className="w-48 text-sm text-dark-text capitalize">{key.replace('_', ' ')}</label>
                  <div className="flex-1 flex items-center gap-2">
                    {param.type === 'int' && (
                      <>
                        <input
                          type="range"
                          min={param.min}
                          max={param.max}
                          defaultValue={param.default}
                          className="flex-1"
                        />
                        <input
                          type="number"
                          min={param.min}
                          max={param.max}
                          defaultValue={param.default}
                          className="input w-20 text-center"
                        />
                      </>
                    )}
                    {param.type === 'float' && (
                      <>
                        <input
                          type="range"
                          min={param.min}
                          max={param.max}
                          step="0.001"
                          defaultValue={param.default}
                          className="flex-1"
                        />
                        <input
                          type="number"
                          min={param.min}
                          max={param.max}
                          step="0.001"
                          defaultValue={param.default}
                          className="input w-24 text-center"
                        />
                      </>
                    )}
                    <span className="text-xs text-dark-muted w-20 text-right">{param.default}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="card">
          <h3 className="text-lg font-semibold text-dark-text mb-4">Logic Builder</h3>
          <div className="space-y-3 p-4 bg-dark-bg rounded-lg border border-dark-border">
            <p className="text-sm text-dark-muted text-center py-8">Visual logic builder coming soon</p>
            <p className="text-xs text-dark-muted text-center">Drag and drop conditions, indicators, and actions to build your strategy logic</p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-dark-text">Built-in Strategies</h3>
        <div className="grid gap-4">
          {builtInStrategies.map(strategy => (
            <StrategyCard key={strategy.id} strategy={strategy} onClick={onSelect} />
          ))}
        </div>
      </div>
    </div>
  )
}

function StrategyCard({ strategy, onClick }: { strategy: any; onClick: (s: any) => void }) {
  return (
    <div
      onClick={() => onClick(strategy)}
      className="card cursor-pointer hover:border-primary-500/50 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div>
          <h4 className="font-semibold text-dark-text">{strategy.name}</h4>
          <p className="text-sm text-dark-muted mt-1">{strategy.description}</p>
          <span className="badge badge-info mt-2">{strategy.category}</span>
        </div>
        <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
      <div className="mt-4 pt-4 border-t border-dark-border">
        <h5 className="text-xs font-medium text-dark-muted mb-2">Parameters</h5>
        <div className="flex flex-wrap gap-2">
          {Object.entries(strategy.parameters).map(([key, param]: [string, any]) => (
            <span key={key} className="badge badge-info text-xs">
              {key}: {param.default}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function StrategyBacktest() {
  return (
    <div className="p-4">
      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Run Backtest</h3>
        <form className="space-y-4 max-w-2xl">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Strategy</label>
              <select className="input">
                <option value="">Select strategy</option>
                {builtInStrategies.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Symbols</label>
              <input type="text" className="input" placeholder="BTC/USDT, ETH/USDT, SOL/USDT" />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Timeframe</label>
              <select className="input">
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="1h" selected>1 Hour</option>
                <option value="4h">4 Hours</option>
                <option value="1d">1 Day</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Period</label>
              <div className="flex gap-2">
                <input type="date" className="input" />
                <span className="self-center text-dark-muted">to</span>
                <input type="date" className="input" />
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Advanced Settings</label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-dark-text mb-1">Initial Capital</label>
                <input type="number" className="input" defaultValue={100000} />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-1">Commission (bps)</label>
                <input type="number" className="input" defaultValue={5} step={0.1} />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-1">Slippage (bps)</label>
                <input type="number" className="input" defaultValue={2} step={0.1} />
              </div>
            </div>
          </div>
          <button type="submit" className="btn-primary w-full">Run Backtest</button>
        </form>
      </div>
    </div>
  )
}

function StrategyOptimizer() {
  return (
    <div className="p-4">
      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Parameter Optimization</h3>
        <form className="space-y-4 max-w-2xl">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Strategy to Optimize</label>
            <select className="input">
              <option value="">Select strategy</option>
              {builtInStrategies.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Parameter Space</label>
            <div className="space-y-3">
              {Object.entries(builtInStrategies[0]?.parameters || {}).map(([key, param]: [string, any]) => (
                <div key={key} className="grid grid-cols-4 gap-4">
                  <label className="col-span-1 text-sm text-dark-text capitalize">{key}</label>
                  <input type="number" className="input col-span-1" placeholder="Min" />
                  <input type="number" className="input col-span-1" placeholder="Max" />
                  <select className="input col-span-1">
                    <option value="uniform">Uniform</option>
                    <option value="loguniform">Log-Uniform</option>
                  </select>
                </div>
              ))}
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
              <input type="number" className="input" defaultValue={50} />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1">Metric</label>
              <select className="input">
                <option value="sharpe_ratio">Sharpe Ratio</option>
                <option value="total_return_pct">Total Return</option>
                <option value="max_drawdown_pct">Max Drawdown</option>
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

function StrategyLibrary({ strategies, onSelect }: { strategies: any[]; onSelect: (s: any) => void }) {
  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-dark-text">Strategy Library</h3>
        <input type="text" className="input w-64" placeholder="Search strategies..." />
      </div>
      <div className="grid gap-4">
        {strategies.map(strategy => (
          <StrategyCard key={strategy.id} strategy={strategy} onClick={onSelect} />
        ))}
      </div>
    </div>
  )
}

function StrategyDetailModal({ strategy, onClose }: { strategy: any; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-dark-card rounded-xl border border-dark-border max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-dark-border">
          <h3 className="text-lg font-semibold text-dark-text">{strategy.name}</h3>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-dark-border transition-colors">
            <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6 space-y-6">
          <p className="text-dark-muted">{strategy.description}</p>
          <span className="badge badge-info">{strategy.category}</span>
          <div>
            <h4 className="font-semibold text-dark-text mb-3">Parameters</h4>
            <div className="grid gap-3">
              {Object.entries(strategy.parameters).map(([key, param]: [string, any]) => (
                <div key={key} className="flex items-center justify-between p-3 bg-dark-bg rounded-lg border border-dark-border">
                  <div>
                    <label className="text-sm font-medium text-dark-text capitalize">{key.replace('_', ' ')}</label>
                    <p className="text-xs text-dark-muted">Default: {param.default} | Range: {param.min} - {param.max}</p>
                  </div>
                  <input
                    type="range"
                    min={param.min}
                    max={param.max}
                    defaultValue={param.default}
                    className="w-48"
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-dark-border">
            <button onClick={onClose} className="btn-secondary">Close</button>
            <button className="btn-primary">Save as Custom</button>
          </div>
        </div>
      </div>
    </div>
  )
}