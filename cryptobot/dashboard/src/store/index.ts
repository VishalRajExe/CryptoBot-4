import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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
  equity: number
  total_equity: number
  available_balance: number
  positions: Position[]
  open_orders: number
  trades_today: number
}

interface Order {
  id: string
  client_order_id: string
  symbol: string
  side: string
  type: string
  quantity: number
  price: number | null
  stop_price: number | null
  status: string
  filled_quantity: number
  avg_fill_price: number | null
  commission: number
  created_at: string
  updated_at: string
}

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
  return_pct: number
}

interface ResearchResult {
  research_id: string
  status: string
  symbols: string[]
  trade_date: string
  final_decision: any
  analyses: any
  created_at: string
  completed_at: string | null
}

interface BacktestResult {
  backtest_id: string
  status: string
  metrics: any
  equity_curve: any
  trades: Trade[]
  created_at: string
}

interface AppState {
  // Connection
  connected: boolean
  setConnected: (connected: boolean) => void

  // Accounts & Positions
  accounts: Account[]
  setAccounts: (accounts: Account[]) => void
  selectedAccount: string | null
  setSelectedAccount: (accountId: string | null) => void

  // Orders
  orders: Order[]
  setOrders: (orders: Order[]) => void

  // Research
  researchResults: ResearchResult[]
  setResearchResults: (results: ResearchResult[]) => void
  addResearchResult: (result: ResearchResult) => void
  updateResearchResult: (id: string, updates: Partial<ResearchResult>) => void

  // Backtest
  backtestResults: BacktestResult[]
  setBacktestResults: (results: BacktestResult[]) => void
  addBacktestResult: (result: BacktestResult) => void

  // UI State
  sidebarOpen: boolean
  toggleSidebar: () => void
  activeTab: string
  setActiveTab: (tab: string) => void

  // Notifications
  notifications: Array<{ id: string; type: 'success' | 'error' | 'warning' | 'info'; message: string }>
  addNotification: (notification: { type: 'success' | 'error' | 'warning' | 'info'; message: string }) => void
  removeNotification: (id: string) => void
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Connection
      connected: false,
      setConnected: (connected) => set({ connected }),

      // Accounts & Positions
      accounts: [],
      setAccounts: (accounts) => set({ accounts }),
      selectedAccount: null,
      setSelectedAccount: (selectedAccount) => set({ selectedAccount }),

      // Orders
      orders: [],
      setOrders: (orders) => set({ orders }),

      // Research
      researchResults: [],
      setResearchResults: (results) => set({ researchResults: results }),
      addResearchResult: (result) => set((state) => ({
        researchResults: [result, ...state.researchResults].slice(0, 50)
      })),
      updateResearchResult: (id, updates) => set((state) => ({
        researchResults: state.researchResults.map(r =>
          r.research_id === id ? { ...r, ...updates } : r
        )
      })),

      // Backtest
      backtestResults: [],
      setBacktestResults: (results) => set({ backtestResults: results }),
      addBacktestResult: (result) => set((state) => ({
        backtestResults: [result, ...state.backtestResults].slice(0, 50)
      })),

      // UI State
      sidebarOpen: true,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      activeTab: 'dashboard',
      setActiveTab: (tab) => set({ activeTab: tab }),

      // Notifications
      notifications: [],
      addNotification: (notification) => set((state) => ({
        notifications: [
          { id: Date.now().toString(), ...notification },
          ...state.notifications
        ].slice(0, 10)
      })),
      removeNotification: (id) => set((state) => ({
        notifications: state.notifications.filter(n => n.id !== id)
      })),
    }),
    {
      name: 'cryptobot-store',
      partialize: (state) => ({
        selectedAccount: state.selectedAccount,
        activeTab: state.activeTab,
        sidebarOpen: state.sidebarOpen,
      }),
    }
  )
)