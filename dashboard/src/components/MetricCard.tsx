import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  value: string
  change?: number
  changeLabel?: string
  positive?: boolean
  icon: string
}

const icons: Record<string, React.ReactNode> = {
  Wallet: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
    </svg>
  ),
  TrendingUp: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  ),
  Percent: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.01 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  ),
  TrendingDown: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6" />
    </svg>
  ),
}

export function MetricCard({ label, value, change, changeLabel, positive, icon }: MetricCardProps) {
  const Icon = icons[icon] || icons.Wallet

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-dark-muted">{label}</p>
          <p className="text-2xl font-bold text-dark-text mt-1">{value}</p>
          {change !== undefined && (
            <div className="flex items-center gap-1 mt-2">
              <span className={cn(
                'text-sm font-medium',
                positive ? 'text-success-500' : 'text-danger-500'
              )}>
                {positive ? '+' : ''}{change.toFixed(2)}%
              </span>
              {changeLabel && (
                <span className="text-sm text-dark-muted">{changeLabel}</span>
              )}
            </div>
          )}
        </div>
        <div className="p-2 rounded-lg bg-primary-600/10 text-primary-500">
          {icons[icon]}
        </div>
      </div>
    </div>
  )
}