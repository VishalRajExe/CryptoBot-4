import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'

interface Account {
  account_id: string
  name: string
  equity: number
  total_equity: number
}

interface AccountSelectorProps {
  accounts: Account[]
  selectedAccount: string | null
  onChange: (accountId: string | null) => void
}

export function AccountSelector({ accounts, selectedAccount, onChange }: AccountSelectorProps) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selected = accounts.find(a => a.account_id === selectedAccount) || accounts[0]

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-card border border-dark-border',
          'hover:border-primary-500/50 transition-colors'
        )}
        aria-haspopup="true"
        aria-expanded={open}
      >
        <div className="w-2 h-2 rounded-full bg-success-500" />
        <span className="text-sm font-medium text-dark-text truncate max-w-[150px]">
          {selected?.name || 'Select Account'}
        </span>
        <svg className={cn('w-4 h-4 text-dark-muted transition-transform', open && 'rotate-180')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-56 bg-dark-card border border-dark-border rounded-lg shadow-lg py-1 z-50 animate-fade-in">
          {accounts.map(account => (
            <button
              key={account.account_id}
              onClick={() => {
                onChange(account.account_id)
                setOpen(false)
              }}
              className={cn(
                'w-full px-3 py-2 text-left text-sm transition-colors',
                selectedAccount === account.account_id
                  ? 'bg-primary-600/10 text-primary-500'
                  : 'text-dark-text hover:bg-dark-border'
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium truncate">{account.name}</span>
                <span className="text-xs text-dark-muted">
                  ${account.total_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}