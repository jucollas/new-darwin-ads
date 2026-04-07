import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format cents to currency display string.
 * 2350 → "$23.50"
 */
export const formatCurrency = (cents: number, currency: string = 'COP'): string => {
  const amount = cents / 100
  if (currency === 'COP') {
    return `$${Math.round(amount).toLocaleString('es-CO')}`
  }
  return `$${amount.toFixed(2)}`
}

/** Format CTR as percentage. 3.45 → "3.45%" */
export const formatPercent = (value: number): string => `${value.toFixed(2)}%`

/** Format ROAS. 2.5 → "2.50x" */
export const formatROAS = (value: number): string => `${value.toFixed(2)}x`
