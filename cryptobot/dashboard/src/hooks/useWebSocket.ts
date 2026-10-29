import { useEffect, useRef, useCallback } from 'react'
import { useStore } from '@/store'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const { addNotification, setConnected, addResearchResult, updateResearchResult, addBacktestResult } = useStore()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`

    wsRef.current = new WebSocket(wsUrl)

    wsRef.current.onopen = () => {
      console.log('WebSocket connected')
      setConnected(true)
    }

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch (e) {
        console.error('WebSocket message parse error:', e)
      }
    }

    wsRef.current.onclose = () => {
      console.log('WebSocket disconnected')
      setConnected(false)
      scheduleReconnect()
    }

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }, [setConnected])

  const handleMessage = (data: any) => {
    switch (data.type) {
      case 'research_completed':
        addResearchResult({
          research_id: data.data.research_id,
          status: 'completed',
          symbols: data.data.symbols,
          trade_date: new Date().toISOString().split('T')[0],
          final_decision: data.data.decision,
          analyses: {},
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        })
        addNotification({
          type: 'success',
          message: `Research completed for ${data.data.symbols.join(', ')}`
        })
        break

      case 'backtest_completed':
        addBacktestResult({
          backtest_id: data.data.backtest_id,
          status: 'completed',
          metrics: data.data.metrics,
          equity_curve: data.data.equity_curve,
          trades: data.data.trades || [],
          created_at: new Date().toISOString(),
        })
        addNotification({
          type: 'success',
          message: `Backtest completed: ${data.data.backtest_id}`
        })
        break

      case 'order_update':
        // Update orders in store
        break

      case 'position_update':
        // Update positions in store
        break

      case 'alert':
        addNotification({
          type: data.data.severity || 'info',
          message: data.data.message
        })
        break

      default:
        console.log('Unknown WebSocket message:', data)
    }
  }

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    reconnectTimeoutRef.current = setTimeout(() => {
      connect()
    }, 3000)
  }, [connect])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { connect, disconnect }
}