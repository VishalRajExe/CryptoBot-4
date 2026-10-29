import { useStore } from '@/store'
import { cn } from '@/lib/utils'

interface Position {
  symbol: string
  quantity: number
  entry_price: number
  mark_price: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  leverage: number
  margin: number
  side: 'long' | 'short'
  updated_at: string
}

interface Account {
  account_id: string
  name: string
  positions: Position[]
}

interface PositionsTableProps {
  accounts: Account[]
  selectedAccount: string | null
}

export function PositionsTable({ accounts, selectedAccount }: PositionsTableProps) {
  const positions = accounts
    .filter(acc => !selectedAccount || acc.account_id === selectedAccount)
    .flatMap(acc => acc.positions.map(pos => ({ ...pos, account_id: acc.account_id, account_name: acc.name })))

  if (positions.length === 0) {
    return (
      <div className="text-center py-8 text-dark-muted">
        <svg className="w-12 h-12 mx-auto mb-3 text-dark-border" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
        <p>No open positions</p>
      </div>
    )
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Side</th>
            <th className="text-right">Qty</th>
            <th className="text-right">Entry</th>
            <th className="text-right">Mark</th>
            <th className="text-right">PnL</th>
            <th className="text-right">PnL %</th>
            <th className="text-right">Leverage</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos, idx) => (
            <tr key={`${pos.account_id}-${pos.symbol}-${idx}`}>
              <td className="font-mono font-medium">{pos.symbol}</td>
              <td>
                <span className={cn(
                  'badge',
                  pos.side === 'long' ? 'badge-success' : 'badge-danger'
                )}>
                  {pos.side.toUpperCase()}
                </span>
              </td>
              <td className="text-right font-mono text-sm">{pos.quantity.toFixed(4)}</td>
              <td className="text-right font-mono text-sm">${pos.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
              <td className="text-right font-mono text-sm">${pos.mark_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
              <td className={cn('text-right font-mono text-sm font-medium', pos.unrealized_pnl >= 0 ? 'text-success-500' : 'text-danger-500')}>
                ${pos.unrealized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
              <td className={cn('text-right font-mono text-sm font-medium', pos.unrealized_pnl_pct >= 0 ? 'text-success-500' : 'text-danger-500')}>
                {pos.unrealized_pnl_pct >= 0 ? '+' : ''}{pos.unrealized_pnl_pct.toFixed(2)}%
              </td>
              <td className="text-right text-sm">{pos.leverage}x</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}