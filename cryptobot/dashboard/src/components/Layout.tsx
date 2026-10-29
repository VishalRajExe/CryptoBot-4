import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useStore } from '@/store'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { NotificationContainer } from './NotificationContainer'
import { cn } from '@/lib/utils'

export function Layout() {
  const { sidebarOpen, toggleSidebar, connected, activeTab, setActiveTab } = useStore()
  const location = useLocation()

  const navigation = [
    { href: '/dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
    { href: '/strategy-lab', label: 'Strategy Lab', icon: 'FlaskConical' },
    { href: '/backtest', label: 'Backtest', icon: 'BarChart3' },
    { href: '/research', label: 'Research', icon: 'Search' },
    { href: '/positions', label: 'Positions', icon: 'Wallet' },
    { href: '/orders', label: 'Orders', icon: 'FileText' },
    { href: '/settings', label: 'Settings', icon: 'Settings' },
  ]

  const icons: Record<string, React.ReactNode> = {
    LayoutDashboard: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
    FlaskConical: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14.042a1 1 0 011.414.343l2.293 2.293a1 1 0 01-1.414 1.414l-1.646-1.647a4 4 0 01-5.88-5.484 3.5 3.5 0 00.027-4.997 5 5 0 019.129 1.41l.006.057a1 1 0 01-.72.89 2 2 0 01-2.139.531 1 1 0 01-.613-.082 6.994 6.994 0 01-2.534-1.916 3 3 0 10-1.993-2.59 3.02 3.02 0 00-3.61.547 2.22 2.22 0 00.084.382 4 4 0 012.25 5.584.5.5 0 00.5.5h4a.5.5 0 00.5-.5V5a.5.5 0 00-.5-.5h-4a.5.5 0 00-.5.5v4a.5.5 0 01-.5.5h-1" />
      </svg>
    ),
    BarChart3: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    Search: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
    Wallet: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
    FileText: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    Settings: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  }

  return (
    <div className="min-h-screen bg-dark-bg flex">
      <Sidebar navigation={navigation} icons={icons} />
      <div className={cn('flex-1 flex flex-col transition-all duration-300', sidebarOpen ? 'ml-64' : 'ml-20')}>
        <Header onMenuClick={toggleSidebar} connected={connected} />
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
      <NotificationContainer />
    </div>
  )
}