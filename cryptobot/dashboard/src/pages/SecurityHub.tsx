import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { MetricCard } from '@/components/MetricCard'
import { EquityChart } from '@/components/EquityChart'

export function SecurityHub() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')

  const tabs = [
    { id: 'overview', label: 'Overview', icon: 'LayoutDashboard' },
    { id: 'chart', label: 'Chart', icon: 'CandlestickChart' },
    { id: 'orderbook', label: 'Order Book', icon: 'List' },
    { id: 'trades', label: 'Recent Trades', icon: 'Activity' },
    { id: 'news', label: 'News', icon: 'Newspaper' },
    { id: 'funding', label: 'Funding', icon: 'DollarSign' },
    { id: 'onchain', label: 'Onchain', icon: 'Globe' },
  ]

  useEffect(() => {
    if (symbol) {
      loadData()
    }
  }, [symbol])

  const loadData = async () => {
    setLoading(true)
    try {
      // Fetch data from API
      const response = await api.get(`/market/${symbol}`)
      setData(response.data)
    } catch (error) {
      console.error('Failed to load security data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="text-center py-12 text-dark-muted">
        <h2 className="text-xl font-semibold mb-2">No data available for {symbol}</h2>
        <button onClick={() => navigate(-1)} className="btn-primary mt-4">Go Back</button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span className="badge badge-primary">{symbol}</span>
            <h1 className="text-2xl font-bold text-dark-text">{data.name || symbol}</h1>
            <span className="text-sm text-dark-muted">{data.exchange || 'Unknown'}</span>
          </div>
          <p className="text-dark-muted mt-1">Real-time market data and analysis</p>
        </div>
        <div className="flex items-center gap-2">
          <MetricCard
            label="Price"
            value={`$${data.price?.toLocaleString() || 'N/A'}`}
            change={data.change_24h_pct}
            positive={data.change_24h_pct >= 0}
          />
          <MetricCard
            label="24h Volume"
            value={`$${(data.volume_24h / 1e9).toFixed(2)}B`}
          />
        </div>
      </div>

      {/* Tabs */}
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

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="card">
              <h3 className="text-lg font-semibold text-dark-text mb-4">Key Statistics</h3>
              <div className="space-y-3">
                <StatRow label="24h High" value={`$${data.high_24h?.toLocaleString() || 'N/A'}`} />
                <StatRow label="24h Low" value={`$${data.low_24h?.toLocaleString() || 'N/A'}`} />
                <StatRow label="24h Change" value={`${data.change_24h_pct?.toFixed(2) || 'N/A'}%`} positive={data.change_24h_pct >= 0} />
                <StatRow label="Volume (24h)" value={`$${(data.volume_24h / 1e6).toFixed(2)}M`} />
                <StatRow label="Funding Rate" value={`${(data.funding_rate * 100).toFixed(4)}%`} />
                <StatRow label="Open Interest" value={`${(data.open_interest / 1e6).toFixed(2)}M`} />
              </div>
            </div>

            <div className="card">
              <h3 className="text-lg font-semibold text-dark-text mb-4">Order Book Summary</h3>
              <div className="space-y-2">
                <StatRow label="Spread" value={`${data.spread_bps?.toFixed(2) || 'N/A'} bps`} />
                <StatRow label="Bid Depth (1%)" value={`${(data.bid_depth_1pct / 1e3).toFixed(2)}K`} />
                <StatRow label="Ask Depth (1%)" value={`${(data.ask_depth_1pct / 1e3).toFixed(2)}K`} />
                <StatRow label="Imbalance" value={`${data.imbalance?.toFixed(2) || 'N/A'}`} positive={data.imbalance >= 0} />
              </div>
            </div>

            <div className="card">
              <h3 className="text-lg font-semibold text-dark-text mb-4">Quick Actions</h3>
              <div className="space-y-2">
                <button className="w-full btn-secondary justify-start">Open in Strategy Lab</button>
                <button className="w-full btn-secondary justify-start">Run Backtest</button>
                <button className="w-full btn-secondary justify-start">Run Research</button>
                <button className="w-full btn-primary justify-start">Place Order</button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'chart' && (
          <div className="card">
            <EquityChart accountId={null} />
          </div>
        )}

        {activeTab === 'orderbook' && (
          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Order Book Depth</h3>
            <OrderBookDepth asks={data.asks} bids={data.bids} />
          </div>
        )}

        {activeTab === 'trades' && (
          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Recent Trades</h3>
            <RecentTradesList trades={data.recent_trades} />
          </div>
        )}

        {activeTab === 'news' && (
          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Latest News</h3>
            <NewsFeed news={data.news} />
          </div>
        )}

        {activeTab === 'funding' && (
          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Funding Rate History</h3>
            <FundingChart history={data.funding_history} />
          </div>
        )}

        {activeTab === 'onchain' && (
          <div className="card">
            <h3 className="text-lg font-semibold text-dark-text mb-4">Onchain Metrics</h3>
            <OnchainMetrics data={data.onchain} />
          </div>
        )}
      </div>
    </div>
  )
}

function StatRow({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-dark-border/50 last:border-0">
      <span className="text-dark-muted">{label}</span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  )
}

function OrderBookDepth({ asks = [], bids = [] }) {
  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <h4 className="text-sm font-medium text-danger-500 mb-2">Asks</h4>
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {asks.slice(0, 20).map((ask: any, i: number) => (
            <div key={i} className="flex justify-between text-sm py-1 px-2 rounded bg-danger-500/5 hover:bg-danger-500/10 transition-colors">
              <span className="font-mono">${ask.price?.toLocaleString()}</span>
              <span className="text-danger-500">{ask.size?.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h4 className="text-sm font-medium text-success-500 mb-2">Bids</h4>
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {bids.slice(0, 20).map((bid: any, i: number) => (
            <div key={i} className="flex justify-between text-sm py-1 px-2 rounded bg-success-500/5 hover:bg-success-500/10 transition-colors">
              <span className="font-mono">${bid.price?.toLocaleString()}</span>
              <span className="text-success-500">{bid.size?.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function RecentTradesList({ trades = [] }) {
  if (!trades.length) return <p className="text-dark-muted text-center py-8">No recent trades</p>

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {trades.slice(0, 20).map((trade: any, i: number) => (
        <div key={i} className="flex items-center justify-between py-2 px-3 rounded bg-dark-bg border border-dark-border/50">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: trade.side === 'buy' ? '#10b981' : '#ef4444' }} />
            <span className="font-mono text-sm">{trade.price?.toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className={cn('font-medium', trade.side === 'buy' ? 'text-success-500' : 'text-danger-500')}>
              {trade.side?.toUpperCase()}
            </span>
            <span className="font-mono text-dark-muted">{trade.size}</span>
            <span className="text-dark-muted">{new Date(trade.time).toLocaleTimeString()}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function NewsFeed({ news = [] }) {
  if (!news.length) return <p className="text-dark-muted text-center py-8">No news available</p>

  return (
    <div className="space-y-4">
      {news.slice(0, 10).map((item: any, i: number) => (
        <div key={i} className="p-4 rounded-lg bg-dark-bg border border-dark-border/50 hover:border-dark-border transition-colors">
          <h4 className="font-medium text-dark-text mb-1">{item.title}</h4>
          <p className="text-sm text-dark-muted mb-2">{item.summary || item.content?.substring(0, 150)}...</p>
          <div className="flex items-center gap-3 text-xs text-dark-muted">
            <span>{item.source}</span>
            <span>{new Date(item.timestamp).toLocaleString()}</span>
            {item.sentiment && (
              <span className={cn('badge', item.sentiment > 0 ? 'badge-success' : item.sentiment < 0 ? 'badge-danger' : 'badge-warning')}>
                {item.sentiment > 0 ? 'Positive' : item.sentiment < 0 ? 'Negative' : 'Neutral'}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function FundingChart({ history = [] }) {
  if (!history.length) return <p className="text-dark-muted text-center py-8">No funding history</p>

  return (
    <div className="h-64">
      <div className="text-center text-dark-muted py-12">
        Funding rate chart would be rendered here with Plotly
      </div>
    </div>
  )
}

function OnchainMetrics({ data = {} }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <MetricCard label="Active Addresses" value={data.active_addresses?.toLocaleString() || 'N/A'} icon="Users" />
      <MetricCard label="Transaction Count" value={data.tx_count?.toLocaleString() || 'N/A'} icon="Activity" />
      <MetricCard label="Hash Rate" value={`${(data.hash_rate / 1e18).toFixed(2)} EH/s`} icon="Zap" />
      <MetricCard label="Difficulty" value={data.difficulty?.toLocaleString() || 'N/A'} icon="Shield" />
      <MetricCard label="MVRV Ratio" value={data.mvrv?.toFixed(2) || 'N/A'} icon="TrendingUp" />
      <MetricCard label="NUPL" value={data.nupl?.toFixed(2) || 'N/A'} icon="BarChart3" />
    </div>
  )
}