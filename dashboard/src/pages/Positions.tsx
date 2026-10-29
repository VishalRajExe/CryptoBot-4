import { useState, useEffect } from 'react'
import { PositionsTable } from '@/components/PositionsTable'
import { api } from '@/lib/api'

export function PositionsPage() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadPositions()
  }, [])

  const loadPositions = async () => {
    setLoading(true)
    try {
      const response = await api.getPositions()
      setAccounts(response.data || [])
    } catch (error) {
      console.error('Failed to load positions:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-text">Positions</h1>
          <p className="text-dark-muted">Open positions and unrealized PnL</p>
        </div>
        <button className="btn-secondary" onClick={loadPositions} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="card p-6">
        <PositionsTable accounts={accounts} selectedAccount={selectedAccount} />
      </div>
    </div>
  )
}

