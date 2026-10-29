import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatNumber(num: number, decimals: number = 2): string {
  if (num >= 1e9) return (num / 1e9).toFixed(decimals) + 'B'
  if (num >= 1e6) return (num / 1e6).toFixed(decimals) + 'M'
  if (num >= 1e3) return (num / 1e3).toFixed(decimals) + 'K'
  return num.toFixed(decimals)
}

export function formatCurrency(num: number, currency: string = 'USD', decimals: number = 2): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num)
}

export function formatPercent(num: number, decimals: number = 2): string {
  const sign = num >= 0 ? '+' : ''
  return `${sign}${num.toFixed(decimals)}%`
}

export function formatDate(date: string | Date, options: Intl.DateTimeFormatOptions = {}): string {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...options,
  })
}

export function formatTime(date: string | Date): string {
  return new Date(date).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatDateTime(date: string | Date): string {
  return new Date(date).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function calculatePnL(entryPrice: number, exitPrice: number, quantity: number, side: 'long' | 'short'): number {
  if (side === 'long') {
    return (exitPrice - entryPrice) * quantity
  } else {
    return (entryPrice - exitPrice) * quantity
  }
}

export function calculatePnLPercent(entryPrice: number, exitPrice: number, side: 'long' | 'short'): number {
  if (side === 'long') {
    return ((exitPrice - entryPrice) / entryPrice) * 100
  } else {
    return ((entryPrice - exitPrice) / entryPrice) * 100
  }
}

export function calculatePositionSize(
  equity: number,
  riskPercent: number,
  entryPrice: number,
  stopLossPrice: number
): number {
  const riskAmount = equity * (riskPercent / 100)
  const riskPerUnit = Math.abs(entryPrice - stopLossPrice)
  if (riskPerUnit === 0) return 0
  return riskAmount / riskPerUnit
}

export function calculateLeverage(notional: number, margin: number): number {
  if (margin === 0) return 0
  return notional / margin
}

export function calculateLiquidationPrice(
  entryPrice: number,
  leverage: number,
  side: 'long' | 'short',
  maintenanceMargin: number = 0.05
): number {
  if (side === 'long') {
    return entryPrice * (1 - 1 / leverage + maintenanceMargin)
  } else {
    return entryPrice * (1 + 1 / leverage - maintenanceMargin)
  }
}

export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => inThrottle = false, limit)
    }
  }
}

export function generateId(): string {
  return Math.random().toString(36).substring(2, 10)
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

export function parseJwt(token: string): any {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join('')
    )
    return JSON.parse(jsonPayload)
  } catch (e) {
    return null
  }
}

export function isTokenExpired(token: string): boolean {
  const decoded = parseJwt(token)
  if (!decoded || !decoded.exp) return true
  return Date.now() >= decoded.exp * 1000
}