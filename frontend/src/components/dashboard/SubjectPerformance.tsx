import type { SubjectPerformance as Row } from '@/api/types'
import { ProgressBar } from '@/components/ui/Badge'
import { formatScore, scoreBand } from '@/utils/format'

export function SubjectPerformanceList({ rows, weakest }: { rows: Row[]; weakest: string | null }) {
  const sorted = [...rows].sort((a, b) => b.avg_score - a.avg_score)
  return (
    <ul className="divide-y divide-line">
      {sorted.map((r) => {
        const band = scoreBand(r.avg_score)
        return (
          <li key={r.subject} className="py-3.5 first:pt-0 last:pb-0">
            <div className="flex items-baseline justify-between gap-3">
              <p className="min-w-0 truncate text-sm font-medium text-ink">
                {r.subject}
                {r.subject === weakest && rows.length > 1 && <span className="ml-2 rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning">Weakest</span>}
              </p>
              <p className="tabular shrink-0 text-sm text-ink-2"><span className="font-semibold text-ink">{formatScore(r.avg_score)}</span>/100 · {band.label}</p>
            </div>
            <ProgressBar className="mt-2" value={r.avg_score} label={`${r.subject} average score`} tone={band.tone === 'success' ? 'success' : band.tone === 'danger' ? 'danger' : band.tone === 'warning' ? 'warning' : 'primary'} />
            <p className="mt-1.5 text-xs text-muted">{r.sessions_count} session{r.sessions_count === 1 ? '' : 's'} · best {formatScore(r.best_score)} · latest {formatScore(r.last_score)}</p>
          </li>
        )
      })}
    </ul>
  )
}
