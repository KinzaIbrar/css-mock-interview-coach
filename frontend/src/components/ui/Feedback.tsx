import type { ReactNode } from 'react'
import { AlertCircle, CheckCircle2, Info, Loader2, TriangleAlert, type LucideIcon } from 'lucide-react'
import { cn } from '@/utils/cn'
import { Button } from './Button'

type Tone = 'info' | 'success' | 'warning' | 'danger'

const tones: Record<Tone, { box: string; icon: LucideIcon; iconColor: string }> = {
  info: { box: 'border-primary/25 bg-primary-soft text-primary-ink', icon: Info, iconColor: 'text-primary' },
  success: { box: 'border-success/25 bg-success-soft text-ink', icon: CheckCircle2, iconColor: 'text-success' },
  warning: { box: 'border-warning-line bg-warning-soft text-ink', icon: TriangleAlert, iconColor: 'text-warning' },
  danger: { box: 'border-danger/30 bg-danger-soft text-ink', icon: AlertCircle, iconColor: 'text-danger' },
}

interface AlertProps {
  tone?: Tone
  title?: string
  children?: ReactNode
  action?: ReactNode
  className?: string
  /** Use "alert" for errors that need immediate attention, "status" otherwise. */
  live?: 'alert' | 'status' | 'off'
}

/** Icon + text + colour: status is never communicated by colour alone. */
export function Alert({ tone = 'info', title, children, action, className, live = 'status' }: AlertProps) {
  const t = tones[tone]
  const Icon = t.icon
  return (
    <div
      role={live === 'off' ? undefined : live}
      className={cn('flex gap-3 rounded-control border px-4 py-3 text-sm', t.box, className)}
    >
      <Icon className={cn('mt-0.5 size-4 shrink-0', t.iconColor)} aria-hidden />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && 'mt-0.5', 'text-ink-2')}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function Spinner({ label = 'Loading', className }: { label?: string; className?: string }) {
  return (
    <span role="status" className={cn('inline-flex items-center gap-2 text-sm text-muted', className)}>
      <Loader2 className="size-4 animate-spin" aria-hidden />
      <span>{label}…</span>
    </span>
  )
}

export function PageLoader({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="grid min-h-[40vh] place-items-center">
      <Spinner label={label} />
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('animate-pulse-soft rounded-control bg-line', className)} />
}

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: ReactNode
  action?: ReactNode
}

export function EmptyState({ icon: Icon = Info, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      <div className="mb-3 grid size-11 place-items-center rounded-full bg-primary-soft text-primary">
        <Icon className="size-5" aria-hidden />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry, title = 'Something went wrong' }: { message: string; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-10 text-center">
      <div className="mb-3 grid size-11 place-items-center rounded-full bg-danger-soft text-danger">
        <AlertCircle className="size-5" aria-hidden />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted">{message}</p>
      {onRetry && <Button className="mt-4" variant="secondary" onClick={onRetry}>Try again</Button>}
    </div>
  )
}
