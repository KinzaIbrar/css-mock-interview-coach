import { cn } from '@/utils/cn'
import { scoreBand } from '@/utils/format'

const stroke = { success: '#15803d', primary: '#1d4ed8', warning: '#b45309', danger: '#b42318' } as const

/** Circular score (0-100) with the number AND a text band, so meaning never depends on colour. */
export function ScoreRing({ score, size = 132, className }: { score: number; size?: number; className?: string }) {
  const band = scoreBand(score)
  const r = (size - 14) / 2
  const c = 2 * Math.PI * r
  const pct = Math.min(100, Math.max(0, score)) / 100
  return (
    <div className={cn('relative inline-grid place-items-center', className)} style={{ width: size, height: size }} role="img" aria-label={`Overall score ${score.toFixed(1)} out of 100, ${band.label}`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={10} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={stroke[band.tone]} strokeWidth={10} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct)} />
      </svg>
      <div className="absolute text-center leading-tight">
        <p className="tabular text-3xl font-semibold text-ink">{score.toFixed(1)}</p>
        <p className="text-xs text-muted">out of 100</p>
      </div>
    </div>
  )
}
