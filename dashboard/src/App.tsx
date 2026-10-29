import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { SecurityHub } from '@/pages/SecurityHub'
import { StrategyLab } from '@/pages/StrategyLab'
import { BacktestPage } from '@/pages/Backtest'
import { ResearchPage } from '@/pages/Research'
import { PositionsPage } from '@/pages/Positions'
import { OrdersPage } from '@/pages/Orders'
import { SettingsPage } from '@/pages/Settings'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useStore } from '@/store'

function App() {
  const { connect } = useWebSocket()
  const { setConnected } = useStore()

  // Initialize WebSocket connection
  useEffect(() => {
    connect()
    setConnected(true)
    return () => {
      setConnected(false)
    }
  }, [connect, setConnected])

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="security/:symbol" element={<SecurityHub />} />
        <Route path="strategy-lab" element={<StrategyLab />} />
        <Route path="backtest" element={<BacktestPage />} />
        <Route path="research" element={<ResearchPage />} />
        <Route path="positions" element={<PositionsPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default App