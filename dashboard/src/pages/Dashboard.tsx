import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { MetricCard } from '@/components/MetricCard'
import { EquityChart } from '@/components/EquityChart'
import { PositionsTable } from '@/components/PositionsTable'
import { RecentTrades } from '@/components/RecentTrades'
import { AccountSelector } from '@/components/AccountSelector'

export function Dashboard() {
  const { accounts, setAccounts, selectedAccount, setSelectedAccount, connected, addNotification } = useStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAccounts()
    if (connected) {
      // Auto-refresh every 30 seconds
      const interval = setInterval(loadAccounts, 30000)
      return () => clearInterval(interval)
    }
  }, [connected])

  const loadAccounts = async () => {
    try {
      const response = await api.getPositions()
      setAccounts(response.data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    } finally {
      setLoading(false)
    }
  }

  const totalEquity = accounts.reduce((sum, acc) => sum + acc.total_equity, 0)
  const totalPnL = accounts.reduce((sum, acc) => {
    const pnl = acc.positions.reduce((p, pos) => p + pos.unrealized_pnl, 0)
    return sum + pnl
  }, 0)
  const totalPnLPct = totalEquity > 0 ? (totalPnL / (totalEquity - totalPnL)) * 100 : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-text">Dashboard</h1>
          <p className="text-dark-muted">Portfolio overview and performance</p>
        </div>
        <AccountSelector
          accounts={accounts}
          selectedAccount={selectedAccount}
          onChange={setSelectedAccount}
        />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Equity"
          value={`$${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon="Wallet"
        />
        <MetricCard
          label="Unrealized PnL"
          value={`$${totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          change={totalPnLPct}
          changeLabel="vs invested"
          positive={totalPnL >= 0}
          icon="TrendingUp"
        />
        <MetricCard
          label="Total PnL %"
          value={`${totalPnLPct >= 0 ? '+' : ''}${totalPnLPct.toFixed(2)}%`}
          positive={totalPnL >= 0}
          icon="Percent"
        />
        <MetricCard
          label="Active Positions"
          value={accounts.reduce((sum, acc) => sum + acc.positions.length, 0).toString()}
          icon="Wallet"
        />
      </div>

      {/* Charts & Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Chart */}
        <div className="lg:col-span-2">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-dark-text">Equity Curve</h2>
              <div className="flex items-center gap-2">
                <select className="input w-auto py-1">
                  <option value="1D">1D</option>
                  <option value="1W" selected>1W</option>
                  <option value="1M">1M</option>
                  <option value="3M">3M</option>
                  <option value="1Y">1Y</option>
                </select>
              </div>
            </div>
            <EquityChart accountId={selectedAccount} />
          </div>
        </div>

        {/* Right Panel */}
        <div className="space-y-6">
          {/* Positions */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-dark-text">Open Positions</h2>
              <span className="badge badge-info">
                {accounts.reduce((sum, acc) => sum + acc.positions.length, 0)} active
              </span>
            </div>
            <PositionsTable accounts={accounts} selectedAccount={selectedAccount} />
          </div>

          {/* Recent Trades */}
          <div className="card">
            <h2 className="text-lg font-semibold text-dark-text mb-4">Recent Trades</h2>
            <RecentTrades accounts={accounts} />
          </div>
        </div>
      </div>
    </div>
  )
}