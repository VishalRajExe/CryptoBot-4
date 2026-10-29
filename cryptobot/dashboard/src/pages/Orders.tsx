import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

export function OrdersPage() {
  const [orders, setOrders] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    account_id: '',
    symbol: '',
    status: '',
  })
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    loadOrders()
  }, [filters])

  const loadOrders = async () => {
    setLoading(true)
    try {
      const response = await api.getOrders(filters)
      setOrders(response.data)
    } catch (error) {
      console.error('Failed to load orders:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-text">Orders</h1>
          <p className="text-dark-muted">Order management and history</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>New Order</button>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <select
            value={filters.account_id}
            onChange={e => setFilters(prev => ({ ...prev, account_id: e.target.value }))}
            className="input"
          >
            <option value="">All Accounts</option>
            <option value="acc_1">Default Account</option>
          </select>
          <input
            type="text"
            placeholder="Symbol (e.g., BTC/USDT)"
            value={filters.symbol}
            onChange={e => setFilters(prev => ({ ...prev, symbol: e.target.value }))}
            className="input"
          />
          <select
            value={filters.status}
            onChange={e => setFilters(prev => ({ ...prev, status: e.target.value }))}
            className="input"
          >
            <option value="">All Statuses</option>
            <option value="NEW">New</option>
            <option value="PENDING">Pending</option>
            <option value="PARTIALLY_FILLED">Partially Filled</option>
            <option value="FILLED">Filled</option>
            <option value="CANCELLED">Cancelled</option>
            <option value="REJECTED">Rejected</option>
          </select>
          <button
            onClick={() => setFilters({ account_id: '', symbol: '', status: '' })}
            className="btn-secondary"
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* Orders Table */}
      <div className="card">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
          </div>
        ) : orders.length === 0 ? (
          <div className="text-center py-12 text-dark-muted">
            <svg className="w-16 h-16 mx-auto mb-4 text-dark-border" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p>No orders found</p>
          </div>
        ) : (
          <>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Client ID</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Type</th>
                    <th className="text-right">Qty</th>
                    <th className="text-right">Price</th>
                    <th className="text-right">Filled</th>
                    <th className="text-right">Avg Fill</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map(order => (
                    <tr key={order.id} className="hover:bg-dark-border/50">
                      <td className="font-mono text-xs">{order.id.slice(0, 12)}...</td>
                      <td className="font-mono text-xs text-dark-muted">{order.client_order_id?.slice(0, 16)}...</td>
                      <td className="font-mono text-sm">{order.symbol}</td>
                      <td>
                        <span className={cn('badge', order.side === 'buy' ? 'badge-success' : 'badge-danger')}>
                          {order.side.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-info text-xs">{order.type}</span>
                      </td>
                      <td className="text-right font-mono text-sm">{order.quantity}</td>
                      <td className="text-right font-mono text-sm">
                        {order.price ? `$${order.price.toLocaleString()}` : 'Market'}
                      </td>
                      <td className="text-right font-mono text-sm">{order.filled_quantity}</td>
                      <td className="text-right font-mono text-sm">
                        {order.avg_fill_price ? `$${order.avg_fill_price.toLocaleString()}` : '-'}
                      </td>
                      <td>
                        <span className={cn('badge',
                          order.status === 'FILLED' ? 'badge-success' :
                          order.status === 'CANCELLED' ? 'badge-danger' :
                          order.status === 'REJECTED' ? 'badge-danger' :
                          order.status === 'PENDING' || order.status === 'PARTIALLY_FILLED' ? 'badge-warning' :
                          'badge-info'
                        )}>
                          {order.status}
                        </span>
                      </td>
                      <td className="text-sm text-dark-muted">{new Date(order.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {orders.length >= 100 && (
              <div className="p-4 border-t border-dark-border text-center text-dark-muted">
                Showing latest 100 orders. Use filters to narrow results.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}