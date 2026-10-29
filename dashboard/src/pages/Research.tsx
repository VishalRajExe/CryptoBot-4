import { useState } from 'react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

export function ResearchPage() {
  const [activeTab, setActiveTab] = useState('analyze')
  const [researchHistory, setResearchHistory] = useState<any[]>([])
  const [selectedResearch, setSelectedResearch] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const tabs = [
    { id: 'analyze', label: 'New Analysis', icon: 'Search' },
    { id: 'history', label: 'History', icon: 'History' },
    { id: 'memory', label: 'Memory Log', icon: 'BookOpen' },
    { id: 'settlement', label: 'Settlement', icon: 'CheckCircle' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-text">Research</h1>
          <p className="text-dark-muted">Multi-agent market analysis and decision making</p>
        </div>
        <button className="btn-primary" onClick={() => setActiveTab('analyze')}>New Analysis</button>
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

      {activeTab === 'analyze' && <ResearchForm onSubmit={handleSubmit} />}
      {activeTab === 'history' && <ResearchHistory research={researchHistory} onSelect={setSelectedResearch} />}
      {activeTab === 'memory' && <MemoryLog />}
      {activeTab === 'settlement' && <SettlementView />}

      {selectedResearch && <ResearchDetailModal research={selectedResearch} onClose={() => setSelectedResearch(null)} />}
    </div>
  )

  async function handleSubmit(data: any) {
    setLoading(true)
    try {
      const response = await api.runResearch(data)
      // Research runs in background, will update via WebSocket
    } catch (error) {
      console.error('Research failed:', error)
    } finally {
      setLoading(false)
    }
  }
}

function ResearchForm({ onSubmit }: { onSubmit: (data: any) => void }) {
  const [formData, setFormData] = useState({
    symbols: ['BTC/USDT', 'ETH/USDT'],
    trade_date: new Date().toISOString().split('T')[0],
    portfolio_context: null,
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      symbols: formData.symbols.split(',').map(s => s.trim()),
      trade_date: formData.trade_date,
      portfolio_context: formData.portfolio_context ? JSON.parse(formData.portfolio_context) : null,
    })
  }

  return (
    <div className="p-4">
      <form onSubmit={handleSubmit} className="max-w-3xl mx-auto space-y-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-dark-text mb-4">Analysis Configuration</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Symbols (comma-separated)</label>
              <input
                name="symbols"
                type="text"
                value={formData.symbols}
                onChange={e => setFormData(prev => ({ ...prev, symbols: e.target.value }))}
                className="input"
                placeholder="BTC/USDT, ETH/USDT, SOL/USDT"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Trade Date</label>
              <input
                name="trade_date"
                type="date"
                value={formData.trade_date}
                onChange={e => setFormData(prev => ({ ...prev, trade_date: e.target.value }))}
                className="input"
                max={new Date().toISOString().split('T')[0]}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-text mb-2">Portfolio Context (JSON, optional)</label>
              <textarea
                name="portfolio_context"
                value={formData.portfolio_context || ''}
                onChange={e => setFormData(prev => ({ ...prev, portfolio_context: e.target.value }))}
                className="input font-mono text-sm"
                rows={4}
                placeholder='{"cash": 50000, "positions": [{"symbol": "BTC/USDT", "quantity": 0.5, "entry_price": 45000}]}'
              />
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-dark-text mb-4">Analysts to Include</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {[
              { id: 'market', name: 'Market Analyst', desc: 'Technical analysis, order flow, funding rates', enabled: true },
              { id: 'news', name: 'News Analyst', desc: 'Crypto news, macro events', enabled: true },
              { id: 'onchain', name: 'Onchain Analyst', desc: 'Whale alerts, exchange flows, TVL', enabled: true },
              { id: 'sentiment', name: 'Sentiment Analyst', desc: 'Fear & Greed, funding rates, OI', enabled: true },
              { id: 'macro', name: 'Macro Analyst', desc: 'FRED data, DXY, yields, correlations', enabled: true },
            ].map(analyst => (
              <label key={analyst.id} className="flex items-start gap-3 p-4 rounded-lg border border-dark-border/50 hover:border-primary-500/50 transition-colors cursor-pointer">
                <input
                  type="checkbox"
                  defaultChecked={analyst.enabled}
                  className="mt-1 h-4 w-4 rounded border-dark-border text-primary-600 focus:ring-primary-500"
                />
                <div>
                  <p className="font-medium text-dark-text">{analyst.name}</p>
                  <p className="text-sm text-dark-muted mt-1">{analyst.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? 'Starting Analysis...' : 'Run Analysis'}
        </button>
      </form>
    </div>
  )
}

function ResearchHistory({ research, onSelect }: { research: any[]; onSelect: (r: any) => void }) {
  if (research.length === 0) {
    return (
      <div className="text-center py-12 text-dark-muted">
        <svg className="w-16 h-16 mx-auto mb-4 text-dark-border" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <p className="text-lg font-medium mb-2">No research analyses yet</p>
        <p className="text-dark-muted">Run your first analysis to see results here</p>
      </div>
    )
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Symbols</th>
            <th>Date</th>
            <th>Status</th>
            <th>Decision</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {research.map(r => (
            <tr key={r.research_id} className="cursor-pointer hover:bg-dark-border/50" onClick={() => onSelect(r)}>
              <td className="font-mono text-sm">{r.research_id}</td>
              <td className="font-mono text-sm">{r.symbols?.join(', ') || 'N/A'}</td>
              <td>{r.trade_date}</td>
              <td>
                <span className={cn('badge', r.status === 'completed' ? 'badge-success' : r.status === 'running' ? 'badge-warning' : 'badge-danger')}>
                  {r.status}
                </span>
              </td>
              <td className="text-dark-muted">
                {r.final_decision?.final_orders?.length > 0
                  ? `${r.final_decision.final_orders.length} orders`
                  : 'Hold'}
              </td>
              <td className="text-sm text-dark-muted">{new Date(r.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MemoryLog() {
  return (
    <div className="p-4">
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-dark-text">Decision Memory Log</h3>
          <button className="btn-secondary text-sm">Export</button>
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="p-4 bg-dark-bg rounded-lg border border-dark-border/50">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <p className="font-medium text-dark-text">BTC/USDT:binance:linear | 2024-01-15</p>
                  <p className="text-sm text-dark-muted">Long 0.5 BTC @ $45,200 | SL: $44,000 | TP: $47,500</p>
                </div>
                <span className="badge badge-success">Profitable</span>
              </div>
              <div className="text-sm text-dark-muted">
                <p>Entry: Market Analyst bullish on EMA crossover + positive funding</p>
                <p>Exit: Take profit hit at $47,500 | Realized PnL: +$1,150 (+2.5%)</p>
                <p>Reflection: Trend continuation worked well. Consider tighter SL for volatile conditions.</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function SettlementView() {
  return (
    <div className="p-4">
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-dark-text">Decision Settlement</h3>
          <button className="btn-primary" onClick={() => {}}>Settle Pending</button>
        </div>
        <div className="space-y-4">
          <div className="p-4 bg-dark-bg rounded-lg border border-dark-border/50">
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="font-medium text-dark-text">ETH/USDT:binance:linear | 2024-01-10</p>
                <p className="text-sm text-dark-muted">Short 10 ETH @ $2,300 | SL: $2,400 | TP: $2,150</p>
              </div>
              <span className="badge badge-warning">Pending</span>
            </div>
            <p className="text-sm text-dark-muted">Settlement in 3 days (7-day holding period)</p>
          </div>
          <div className="p-4 bg-dark-bg rounded-lg border border-dark-border/50">
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="font-medium text-dark-text">BTC/USDT:binance:linear | 2024-01-05</p>
                <p className="text-sm text-dark-muted">Long 0.1 BTC @ $43,000 | SL: $41,500 | TP: $46,000</p>
              </div>
              <span className="badge badge-success">Settled</span>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-dark-muted">Realized PnL</p>
                <p className="font-medium text-success-500">+$280 (+0.65%)</p>
              </div>
              <div>
                <p className="text-dark-muted">Alpha vs BTC</p>
                <p className="font-medium text-success-500">+0.12%</p>
              </div>
              <div>
                <p className="text-dark-muted">Reflection</p>
                <p className="font-medium">Trend followed through. SL was not hit.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ResearchDetailModal({ research, onClose }: { research: any; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-dark-card rounded-xl border border-dark-border max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-dark-border">
          <h3 className="text-lg font-semibold text-dark-text">Research: {research.research_id}</h3>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-dark-border transition-colors">
            <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-dark-muted">Status</p>
              <p className="font-medium">{research.status}</p>
            </div>
            <div>
              <p className="text-sm text-dark-muted">Symbols</p>
              <p className="font-mono text-sm">{research.symbols?.join(', ') || 'N/A'}</p>
            </div>
            <div>
              <p className="text-sm text-dark-muted">Trade Date</p>
              <p className="font-mono text-sm">{research.trade_date}</p>
            </div>
          </div>

          {research.analyses && (
            <div>
              <h3 className="text-lg font-semibold text-dark-text mb-4">Analyst Outputs</h3>
              <div className="space-y-4">
                {Object.entries(research.analyses).map(([key, analysis]) => (
                  <div key={key} className="p-4 bg-dark-bg rounded-lg border border-dark-border/50">
                    <h4 className="font-medium text-dark-text capitalize mb-2">{key.replace('_', ' ')}</h4>
                    <pre className="text-sm text-dark-muted whitespace-pre-wrap max-h-64 overflow-y-auto">
                      {JSON.stringify(analysis, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

          {research.final_decision && (
            <div>
              <h3 className="text-lg font-semibold text-dark-text mb-4">Final Decision</h3>
              <pre className="p-4 bg-dark-bg rounded-lg border border-dark-border/50 text-sm text-dark-muted whitespace-pre-wrap max-h-96 overflow-y-auto">
                {JSON.stringify(research.final_decision, null, 2)}
              </pre>
            </div>
          )}

          {research.debate_history && (
            <div>
              <h3 className="text-lg font-semibold text-dark-text mb-4">Debate History</h3>
              <div className="space-y-3">
                {research.debate_history.map((d: any, i: number) => (
                  <div key={i} className="p-3 bg-dark-bg rounded-lg border border-dark-border/50">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="badge badge-info">{d.role}</span>
                      <span className="text-xs text-dark-muted">{new Date().toLocaleTimeString()}</span>
                    </div>
                    <p className="text-sm text-dark-text">{d.content?.substring(0, 200)}...</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-dark-border">
            <button onClick={onClose} className="btn-secondary">Close</button>
            <button className="btn-primary">Export JSON</button>
          </div>
        </div>
      </div>
    </div>
  )
}