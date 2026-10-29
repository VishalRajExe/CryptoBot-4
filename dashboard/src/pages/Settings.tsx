import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState('general')
  const [settings, setSettings] = useState<any>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const tabs = [
    { id: 'general', label: 'General', icon: 'Settings' },
    { id: 'exchanges', label: 'Exchanges', icon: 'Globe' },
    { id: 'risk', label: 'Risk Management', icon: 'Shield' },
    { id: 'strategies', label: 'Strategies', icon: 'BookOpen' },
    { id: 'llm', label: 'LLM Providers', icon: 'Brain' },
    { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
  ]

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    setLoading(true)
    try {
      const response = await api.getSettings()
      setSettings(response.data)
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 5000)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-text">Settings</h1>
          <p className="text-dark-muted">Configure your trading bot</p>
        </div>
      </div>

      {message && (
        <div className={cn('p-4 rounded-lg border', message.type === 'success' ? 'bg-success-500/10 border-success-500/20 text-success-500' : 'bg-danger-500/10 border-danger-500/20 text-danger-500')}>
          {message.text}
        </div>
      )}

      <div className="border-b border-dark-border">
        <nav className="flex gap-1 px-4 overflow-x-auto" aria-label="Settings tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
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

      <div className="max-w-4xl mx-auto p-4 space-y-6">
        {activeTab === 'general' && <GeneralSettings settings={settings} onSave={saveSettings} />}
        {activeTab === 'exchanges' && <ExchangeSettings settings={settings} onSave={saveSettings} />}
        {activeTab === 'risk' && <RiskSettings settings={settings} onSave={saveSettings} />}
        {activeTab === 'strategies' && <StrategySettings settings={settings} onSave={saveSettings} />}
        {activeTab === 'llm' && <LLMSettings settings={settings} onSave={saveSettings} />}
        {activeTab === 'dashboard' && <DashboardSettings settings={settings} onSave={saveSettings} />}
      </div>
    </div>
  )

  async function saveSettings(section: string, data: any) {
    setSaving(true)
    try {
      await api.updateSettings(section, data)
      setSettings(prev => ({ ...prev, [section]: data }))
      showMessage('success', `${section} settings saved`)
    } catch (error) {
      showMessage('error', 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }
}

function GeneralSettings({ settings, onSave }: { settings: any; onSave: (section: string, data: any) => void }) {
  const [formData, setFormData] = useState({
    app_name: settings.app_name || 'Cryptobot',
    environment: settings.environment || 'development',
    debug: settings.debug || false,
    log_level: settings.log_level || 'INFO',
    paper_trading: settings.paper_trading !== false,
    default_exchange: settings.default_exchange || 'binance',
    default_timeframe: settings.default_timeframe || '1h',
    lookback_bars: settings.lookback_bars || 500,
  })

  return (
    <form onSubmit={e => { e.preventDefault(); onSave('general', formData) }} className="space-y-6 max-w-2xl">
      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Application</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">App Name</label>
            <input name="app_name" value={formData.app_name} onChange={e => setFormData(prev => ({ ...prev, app_name: e.target.value }))} className="input" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Environment</label>
            <select name="environment" value={formData.environment} onChange={e => setFormData(prev => ({ ...prev, environment: e.target.value }))} className="input">
              <option value="development">Development</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Log Level</label>
            <select name="log_level" value={formData.log_level} onChange={e => setFormData(prev => ({ ...prev, log_level: e.target.value }))} className="input">
              <option value="DEBUG">Debug</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Default Exchange</label>
            <select name="default_exchange" value={formData.default_exchange} onChange={e => setFormData(prev => ({ ...prev, default_exchange: e.target.value }))} className="input">
              <option value="binance">Binance</option>
              <option value="bybit">Bybit</option>
              <option value="okx">OKX</option>
              <option value="hyperliquid">Hyperliquid</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Trading Mode</h3>
        <div className="space-y-4">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={formData.paper_trading}
              onChange={e => setFormData(prev => ({ ...prev, paper_trading: e.target.checked }))}
              className="h-4 w-4 rounded border-dark-border text-primary-600 focus:ring-primary-500"
            />
            <div>
              <p className="font-medium text-dark-text">Paper Trading Mode</p>
              <p className="text-sm text-dark-muted">Run in simulation mode without real funds</p>
            </div>
          </label>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Debug Mode</label>
            <input
              type="checkbox"
              checked={formData.debug}
              onChange={e => setFormData(prev => ({ ...prev, debug: e.target.checked }))}
              className="h-4 w-4 rounded border-dark-border text-primary-600 focus:ring-primary-500"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Default Timeframe</label>
              <select name="default_timeframe" value={formData.default_timeframe} onChange={e => setFormData(prev => ({ ...prev, default_timeframe: e.target.value }))} className="input">
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="1h">1 Hour</option>
                <option value="4h">4 Hours</option>
                <option value="1d">1 Day</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Lookback Bars</label>
              <input type="number" name="lookback_bars" value={formData.lookback_bars} onChange={e => setFormData(prev => ({ ...prev, lookback_bars: parseInt(e.target.value) }))} className="input" min={50} max={5000} />
            </div>
          </div>
        </div>
      </div>

      <button type="submit" className="btn-primary">Save General Settings</button>
    </form>
  )
}

function ExchangeSettings({ settings, onSave }: { settings: any; onSave: (section: string, data: any) => void }) {
  const exchanges = settings.exchanges || {}

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-dark-text">Exchange Connections</h2>
        <p className="text-sm text-dark-muted">Configure API keys and settings for each exchange</p>
      </div>

      {Object.entries(exchanges).map(([name, config]: [string, any]) => (
        <div key={name} className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="badge badge-info capitalize">{name}</span>
              <span className={cn('badge', config.enabled ? 'badge-success' : 'badge-danger')}>
                {config.enabled ? 'Enabled' : 'Disabled'}
              </span>
              <span className="badge badge-info">{config.testnet ? 'Testnet' : 'Live'}</span>
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={e => onSave('exchanges', { ...exchanges, [name]: { ...config, enabled: e.target.checked } })}
                className="h-4 w-4 rounded border-dark-border text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-dark-muted">Enable</span>
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Testnet</label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={config.testnet}
                  onChange={e => onSave('exchanges', { ...exchanges, [name]: { ...config, testnet: e.target.checked } })}
                  className="h-4 w-4 rounded border-dark-border text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-dark-muted">Use testnet</span>
              </label>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Rate Limit (req/min)</label>
              <input type="number" value={config.rate_limit} onChange={e => onSave('exchanges', { ...exchanges, [name]: { ...config, rate_limit: parseInt(e.target.value) } })} className="input" min={10} />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">API Key</label>
              <input type="password" placeholder="••••••••" className="input" disabled />
              <p className="text-xs text-dark-muted mt-1">Set via environment variable {name.toUpperCase()}_API_KEY</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">API Secret</label>
              <input type="password" placeholder="••••••••" className="input" disabled />
              <p className="text-xs text-dark-muted mt-1">Set via environment variable {name.toUpperCase()}_API_SECRET</p>
            </div>
            {config.passphrase && (
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Passphrase</label>
                <input type="password" placeholder="••••••••" className="input" disabled />
                <p className="text-xs text-dark-muted mt-1">Set via environment variable {name.toUpperCase()}_PASSPHRASE</p>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function RiskSettings({ settings, onSave }: { settings: any; onSave: (section: string, data: any) => void }) {
  const risk = settings.risk || {}
  const [formData, setFormData] = useState({
    max_position_pct: risk.max_position_pct || 0.1,
    max_portfolio_pct: risk.max_portfolio_pct || 0.8,
    max_daily_loss_pct: risk.max_daily_loss_pct || 0.05,
    max_drawdown_pct: risk.max_drawdown_pct || 0.15,
    max_leverage: risk.max_leverage || 3.0,
    min_risk_reward: risk.min_risk_reward || 1.5,
    kelly_fraction: risk.kelly_fraction || 0.25,
    correlation_limit: risk.correlation_limit || 0.7,
  })

  return (
    <form onSubmit={e => { e.preventDefault(); onSave('risk', formData) }} className="space-y-6 max-w-2xl">
      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Position Limits</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Max Position %</label>
            <input type="number" name="max_position_pct" value={formData.max_position_pct} onChange={e => setFormData(prev => ({ ...prev, max_position_pct: parseFloat(e.target.value) }))} className="input" step="0.01" min="0.01" max="1" />
            <p className="text-xs text-dark-muted mt-1">Maximum position size as % of equity</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Max Portfolio %</label>
            <input type="number" name="max_portfolio_pct" value={formData.max_portfolio_pct} onChange={e => setFormData(prev => ({ ...prev, max_portfolio_pct: parseFloat(e.target.value) }))} className="input" step="0.01" min="0.1" max="1" />
            <p className="text-xs text-dark-muted mt-1">Maximum total exposure as % of equity</p>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Loss Limits</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Max Daily Loss %</label>
            <input type="number" name="max_daily_loss_pct" value={formData.max_daily_loss_pct} onChange={e => setFormData(prev => ({ ...prev, max_daily_loss_pct: parseFloat(e.target.value) }))} className="input" step="0.01" min="0.01" max="0.5" />
            <p className="text-xs text-dark-muted mt-1">Stop trading if daily loss exceeds this</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Max Drawdown %</label>
            <input type="number" name="max_drawdown_pct" value={formData.max_drawdown_pct} onChange={e => setFormData(prev => ({ ...prev, max_drawdown_pct: parseFloat(e.target.value) }))} className="input" step="0.01" min="0.05" max="0.5" />
            <p className="text-xs text-dark-muted mt-1">Reduce positions if drawdown exceeds this</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Max Leverage</label>
            <input type="number" name="max_leverage" value={formData.max_leverage} onChange={e => setFormData(prev => ({ ...prev, max_leverage: parseFloat(e.target.value) }))} className="input" step="0.1" min="1" max="100" />
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Trade Parameters</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Min Risk/Reward</label>
            <input type="number" name="min_risk_reward" value={formData.min_risk_reward} onChange={e => setFormData(prev => ({ ...prev, min_risk_reward: parseFloat(e.target.value) }))} className="input" step="0.1" min="1" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Kelly Fraction</label>
            <input type="number" name="kelly_fraction" value={formData.kelly_fraction} onChange={e => setFormData(prev => ({ ...prev, kelly_fraction: parseFloat(e.target.value) }))} className="input" step="0.01" min="0.01" max="1" />
            <p className="text-xs text-dark-muted mt-1">Fraction of Kelly criterion to use</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Correlation Limit</label>
            <input type="number" name="correlation_limit" value={formData.correlation_limit} onChange={e => setFormData(prev => ({ ...prev, correlation_limit: parseFloat(e.target.value) }))} className="input" step="0.01" min="0" max="1" />
            <p className="text-xs text-dark-muted mt-1">Max correlation between positions</p>
          </div>
        </div>
      </div>

      <button type="submit" className="btn-primary w-full md:w-auto">Save Risk Settings</button>
    </form>
  )
}

function StrategySettings({ settings, onSave }: { settings: any; onSave: (section: string, data: any) => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-dark-text">Strategy Configurations</h2>
        <button className="btn-secondary text-sm">Import Strategy</button>
      </div>

      <div className="card">
        <p className="text-dark-muted mb-4">Strategy configurations are stored in YAML format. Edit the file directly or use the Strategy Lab to create new strategies.</p>
        <div className="p-4 bg-dark-bg rounded-lg border border-dark-border font-mono text-sm overflow-x-auto">
          {`# Example strategy configuration
trend_follow:
  name: "trend_follow"
  enabled: true
  parameters:
    fast_period: 10
    slow_period: 30
    adx_threshold: 20

mean_reversion:
  name: "mean_reversion"
  enabled: true
  parameters:
    bb_period: 20
    bb_std: 2.0
    rsi_period: 14
    rsi_oversold: 30
    rsi_overbought: 70`}
        </div>
      </div>
    </div>
  )
}

function LLMSettings({ settings, onSave }: { settings: any; onSave: (section: string, data: any) => void }) {
  const llm = settings.llm_providers || {}

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-dark-text">LLM Providers</h2>
        <p className="text-sm text-dark-muted">Configure AI models for research agents</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(llm).map(([key, config]: [string, any]) => (
          <div key={key} className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-dark-text capitalize">{key}</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Provider</label>
                <select className="input" disabled>
                  <option value={config.provider}>{config.provider}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Model</label>
                <input type="text" value={config.model} className="input" disabled />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Temperature</label>
                <input type="number" value={config.temperature} step="0.1" className="input" min={0} max={2} disabled />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">Max Tokens</label>
                <input type="number" value={config.max_tokens} className="input" min={100} disabled />
              </div>
              <div>
                <label className="block text-sm font-medium text-dark-text mb-2">API Key</label>
                <input type="password" placeholder="••••••••" className="input" disabled />
                <p className="text-xs text-dark-muted mt-1">Set via environment variable</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function DashboardSettings({ settings, onSave }: { settings: any; onSave: (section: string, data: any) => void }) {
  const dashboard = settings.dashboard || {}
  const [formData, setFormData] = useState({
    host: dashboard.host || '0.0.0.0',
    port: dashboard.port || 8080,
    ws_port: dashboard.ws_port || 8081,
    auth_enabled: dashboard.auth_enabled || false,
  })

  return (
    <form onSubmit={e => { e.preventDefault(); onSave('dashboard', formData) }} className="space-y-6 max-w-xl">
      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Server</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Host</label>
            <input name="host" value={formData.host} onChange={e => setFormData(prev => ({ ...prev, host: e.target.value }))} className="input" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">Port</label>
            <input type="number" name="port" value={formData.port} onChange={e => setFormData(prev => ({ ...prev, port: parseInt(e.target.value) }))} className="input" min={1000} max={65535} />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-text mb-2">WebSocket Port</label>
            <input type="number" name="ws_port" value={formData.ws_port} onChange={e => setFormData(prev => ({ ...prev, ws_port: parseInt(e.target.value) }))} className="input" min={1000} max={65535} />
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-dark-text mb-4">Authentication</h3>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={formData.auth_enabled}
            onChange={e => setFormData(prev => ({ ...prev, auth_enabled: e.target.checked }))}
            className="h-4 w-4 rounded border-dark-border text-primary-600 focus:ring-primary-500"
          />
          <div>
            <p className="font-medium text-dark-text">Enable Authentication</p>
            <p className="text-sm text-dark-muted">Require login to access dashboard</p>
          </div>
        </label>
      </div>

      <button type="submit" className="btn-primary w-full md:w-auto">Save Dashboard Settings</button>
    </form>
  )
}