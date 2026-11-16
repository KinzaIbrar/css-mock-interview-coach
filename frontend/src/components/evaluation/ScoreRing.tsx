import { cn } from '@/utils/cn'
import { scoreBand } from '@/utils/format'

const stroke = { success: '#15803d', primary: '#16281c', warning: '#92400e', danger: '#b42318' } as const

/** Circular score (0-10) with the number AND a text band, so meaning never depends on colour. */
export function ScoreRing({ score, size = 132, className }: { score: number; size?: number; className?: string }) {
  const band = scoreBand(score)
  const r = (size - 14) / 2
  const c = 2 * Math.PI * r
  const pct = Math.min(10, Math.max(0, score)) / 10
  return (
    <div className={cn('relative inline-grid place-items-center', className)} style={{ width: size, height: size }} role="img" aria-label={`Overall score ${score.toFixed(1)} out of 10, ${band.label}`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e6e4da" strokeWidth={10} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={stroke[band.tone]} strokeWidth={10} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct)} />
      </svg>
      <div className="absolute text-center leading-tight">
        <p className="tabular text-3xl font-semibold text-ink">{score.toFixed(1)}</p>
        <p className="text-xs text-muted">out of 10</p>
      </div>
    </div>
  )
}
