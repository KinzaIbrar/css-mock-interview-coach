import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/Card'

export function StatCard({ label, value, hint, icon: Icon }: { label: string; value: string; hint?: string; icon: LucideIcon }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-muted">{label}</p>
          <p className="tabular mt-1.5 text-[1.75rem] font-semibold leading-none text-ink">{value}</p>
        </div>
        <span className="grid size-9 shrink-0 place-items-center rounded-control bg-primary-soft text-primary">
          <Icon className="size-[18px]" aria-hidden />
        </span>
      </div>
      {hint && <p className="mt-3 text-xs text-muted">{hint}</p>}
    </Card>
  )
}
