import { useEffect, useState } from 'react'
import { Timer } from 'lucide-react'
import { cn } from '@/utils/cn'
import { formatCountdown, parseServerDate } from '@/utils/format'

/** Client-side countdown. The backend stores the duration but does not enforce it. */
export function InterviewTimer({ startedAt, durationMinutes }: { startedAt: string; durationMinutes: number }) {
  const endsAt = parseServerDate(startedAt).getTime() + durationMinutes * 60_000
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  const remaining = Math.max(0, Math.round((endsAt - now) / 1000))
  const over = remaining === 0
  const low = !over && remaining <= 300
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium tabular',
        over ? 'border-danger/30 bg-danger-soft text-danger' : low ? 'border-warning-line bg-warning-soft text-warning' : 'border-line bg-surface text-ink-2',
      )}
      role="timer"
      aria-label={over ? 'Time is up' : `${formatCountdown(remaining)} remaining`}
    >
      <Timer className="size-4" aria-hidden />
      {over ? 'Time is up' : `${formatCountdown(remaining)} left`}
    </span>
  )
}
