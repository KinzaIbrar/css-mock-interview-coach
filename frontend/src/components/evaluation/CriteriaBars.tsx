import { CRITERIA } from '@/api/types'
import { ProgressBar } from '@/components/ui/Badge'
import { CRITERIA_LABELS } from '@/utils/format'

/** The six evaluation criteria (each scored 0-10 by the backend). */
export function CriteriaBars({ scores }: { scores: Record<string, number> }) {
  return (
    <ul className="space-y-4">
      {CRITERIA.map((key) => {
        const value = scores[key] ?? 0
        const tone = value >= 7.5 ? 'success' : value >= 6 ? 'primary' : value >= 4 ? 'warning' : 'danger'
        return (
          <li key={key}>
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="font-medium text-ink">{CRITERIA_LABELS[key]}</span>
              <span className="tabular text-ink-2"><span className="font-semibold text-ink">{value.toFixed(1)}</span> / 10</span>
            </div>
            <ProgressBar value={value} max={10} tone={tone} label={`${CRITERIA_LABELS[key]}: ${value.toFixed(1)} out of 10`} />
          </li>
        )
      })}
    </ul>
  )
}
