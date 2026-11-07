import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/utils/cn'

export type BadgeTone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger'

const tones: Record<BadgeTone, string> = {
  neutral: 'bg-surface-2 text-ink-2 border-line',
  primary: 'bg-primary-soft text-primary-ink border-primary/20',
  success: 'bg-success-soft text-success border-success/25',
  warning: 'bg-warning-soft text-warning border-warning-line',
  danger: 'bg-danger-soft text-danger border-danger/25',
}

export function Badge({ tone = 'neutral', icon: Icon, children, className }: { tone?: BadgeTone; icon?: LucideIcon; children: ReactNode; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium', tones[tone], className)}>
      {Icon && <Icon className="size-3.5" aria-hidden />}
      {children}
    </span>
  )
}

export function ProgressBar({ value, max = 100, label, tone = 'primary', className }: { value: number; max?: number; label: string; tone?: 'primary' | 'success' | 'warning' | 'danger'; className?: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const fill = { primary: 'bg-primary', success: 'bg-success', warning: 'bg-warning', danger: 'bg-danger' }[tone]
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(value * 10) / 10}
      className={cn('h-2 w-full overflow-hidden rounded-full bg-line', className)}
    >
      <div className={cn('h-full rounded-full transition-[width] duration-500', fill)} style={{ width: `${pct}%` }} />
    </div>
  )
}
