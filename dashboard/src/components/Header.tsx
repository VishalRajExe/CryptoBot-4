import { useStore } from '@/store'
import { cn } from '@/lib/utils'

interface HeaderProps {
  onMenuClick: () => void
  connected: boolean
}

export function Header({ onMenuClick, connected }: HeaderProps) {
  const { sidebarOpen, addNotification } = useStore()

  return (
    <header className={cn('h-16 bg-dark-card border-b border-dark-border flex items-center justify-between px-6', sidebarOpen ? 'ml-64' : 'ml-20')}>
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className={cn('p-2 rounded-lg hover:bg-dark-border transition-colors lg:hidden', sidebarOpen && 'hidden')}
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6 text-dark-text" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div className="flex-1" />

        {/* Connection Status */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium">
            <span className={cn('w-2 h-2 rounded-full', connected ? 'bg-success-500 animate-pulse' : 'bg-danger-500')} />
            <span className={cn(connected ? 'text-success-500' : 'text-danger-500')}>
              {connected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => addNotification({ type: 'info', message: 'Quick backtest started' })}
            className="p-2 rounded-lg hover:bg-dark-border transition-colors"
            title="Quick Backtest"
          >
            <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </button>

          <button
            onClick={() => addNotification({ type: 'info', message: 'Research analysis started' })}
            className="p-2 rounded-lg hover:bg-dark-border transition-colors"
            title="Run Research"
          >
            <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
        </div>
      </div>

      {/* User Menu */}
      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-bg border border-dark-border">
          <div className="w-2 h-2 rounded-full bg-success-500" />
          <span className="text-xs text-dark-muted">Paper Trading</span>
        </div>

        <div className="relative">
          <button className="p-2 rounded-lg hover:bg-dark-border transition-colors">
            <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 5.366 3.364 9.78 8 10.32V21h5l1.405-1.405z" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}