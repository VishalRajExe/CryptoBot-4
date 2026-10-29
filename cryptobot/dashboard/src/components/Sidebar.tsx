import { NavLink, useLocation } from 'react-router-dom'
import { useStore } from '@/store'
import { cn } from '@/lib/utils'

interface NavigationItem {
  href: string
  label: string
  icon: string
}

interface SidebarProps {
  navigation: NavigationItem[]
  icons: Record<string, React.ReactNode>
}

export function Sidebar({ navigation, icons }: SidebarProps) {
  const { sidebarOpen, activeTab, setActiveTab } = useStore()
  const location = useLocation()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-dark-card border-r border-dark-border transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-20'
      )}
    >
      <div className="flex flex-col h-full">
        {/* Logo */}
        <div className={cn('flex items-center justify-between h-16 px-4 border-b border-dark-border', !sidebarOpen && 'justify-center')}>
          <NavLink to="/dashboard" className="flex items-center gap-2" title="Cryptobot">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            {sidebarOpen && (
              <span className="font-bold text-lg text-dark-text">Cryptobot</span>
            )}
          </NavLink>
          <button
            onClick={() => useStore.getState().toggleSidebar()}
            className={cn('p-2 rounded-lg hover:bg-dark-border transition-colors', !sidebarOpen && 'mx-auto')}
            aria-label="Toggle sidebar"
          >
            <svg className="w-5 h-5 text-dark-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sidebarOpen ? 'M11 19l-7-7 7-7m8 14l-7-7 7-7' : 'M13 5l7 7-7 7M5 5l7 7-7 7'} />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href || location.pathname.startsWith(item.href + '/')
            const Icon = icons[item.icon]

            return (
              <NavLink
                key={item.href}
                to={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary-600/20 text-primary-400'
                    : 'text-dark-muted hover:bg-dark-border hover:text-dark-text',
                  !sidebarOpen && 'justify-center px-2'
                )}
                title={sidebarOpen ? undefined : item.label}
                onClick={() => setActiveTab(item.href)}
              >
                <span className={cn('flex-shrink-0', !sidebarOpen && 'mx-auto')}>
                  {Icon}
                </span>
                {sidebarOpen && <span className="flex-1 truncate">{item.label}</span>}
              </NavLink>
            )
          })}

          {/* Quick Actions */}
          {sidebarOpen && (
            <div className="border-t border-dark-border pt-4 mt-4">
              <h3 className="px-3 text-xs font-semibold text-dark-muted uppercase tracking-wider mb-3">
                Quick Actions
              </h3>
              <QuickActions />
            )}
          }
        </nav>

        {/* Status Bar */}
        <div className={cn('p-3 border-t border-dark-border', !sidebarOpen && 'px-2')}>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success-500 animate-pulse" />
            {sidebarOpen && <span className="text-xs text-success-500">Connected</span>}
          </div>
        </div>
      </div>
    </aside>
  )
}

function QuickActions() {
  return (
    <div className="space-y-1 px-3">
      <button className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-dark-muted hover:bg-dark-border hover:text-dark-text transition-colors">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        <span>New Strategy</span>
      </button>
      <button className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-dark-muted hover:bg-dark-border hover:text-dark-text transition-colors">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <span>Run Backtest</span>
      </button>
      <button className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-dark-muted hover:bg-dark-border hover:text-dark-text transition-colors">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <span>Run Research</span>
      </button>
    </div>
  )
}