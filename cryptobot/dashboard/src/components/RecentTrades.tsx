import { cn } from '@/lib/utils'

interface Trade {
  entry_time: string
  exit_time: string
  symbol: string
  side: string
  entry_price: number
  exit_price: number
  quantity: number
  pnl: number
  pnl_pct: number
  commission: number
  slippage: number
  holding_period: number
}

interface Account {
  trades: Trade[]
}

interface RecentTradesProps {
  accounts: Account[]
}

export function RecentTrades({ accounts }: RecentTradesProps) {
  const trades = accounts
    .flatMap(acc => acc.trades.map(t => ({ ...t })))
    .sort((a, b) => new Date(b.exit_time).getTime() - new Date(a.exit_time).getTime())
    .slice(0, 10)

  if (trades.length === 0) {
    return (
      <div className="text-center py-8 text-dark-muted">
        <svg className="w-12 h-12 mx-auto mb-3 text-dark-border" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p>No recent trades</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {trades.map((trade, idx) => (
        <div key={`${trade.symbol}-${trade.exit_time}-${idx}`} className="flex items-center justify-between p-3 rounded-lg bg-dark-bg border border-dark-border/50 hover:border-dark-border transition-colors">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: trade.pnl >= 0 ? '#10b981' : '#ef4444' }} />
            <div>
              <p className="font-mono text-sm font-medium">{trade.symbol}</p>
              <p className="text-xs text-dark-muted">
                {new Date(trade.entry_time).toLocaleDateString()} → {new Date(trade.exit_time).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className={cn(
              'font-medium',
              trade.pnl >= 0 ? 'text-success-500' : 'text-danger-500'
            )}>
              {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
            </span>
            <span className={cn(
              trade.pnl_pct >= 0 ? 'text-success-500' : 'text-danger-500'
            )}>
              ({trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(2)}%)
            </span>
            <span className="text-dark-muted">{trade.holding_period.toFixed(1)}h</span>
          </div>
        </div>
      ))}
    </div>
  )
}