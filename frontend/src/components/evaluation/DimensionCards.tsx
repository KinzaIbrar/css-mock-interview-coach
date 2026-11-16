import { BookOpen, Gavel, Newspaper, Scale } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { CRITERIA } from '@/api/types'
import { Card, CardBody } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/Badge'
import { CRITERIA_DESCRIPTIONS, CRITERIA_LABELS, formatScore, scoreBand } from '@/utils/format'

const DIMENSION_ICONS: Record<string, LucideIcon> = {
  constitutional_understanding: Gavel,
  analytical_depth: Scale,
  subject_expertise: BookOpen,
  policy_awareness: Newspaper,
}

const RING_TONE: Record<'success' | 'primary' | 'warning' | 'danger', string> = {
  success: 'bg-success-soft text-success',
  primary: 'bg-primary-soft text-primary',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
}

/** One of the 4 CSS-specific evaluation dimensions: score (0-10), a short description, and a progress bar. */
export function DimensionCard({ dimension, score, isFocusArea }: { dimension: string; score: number; isFocusArea?: boolean }) {
  const Icon = DIMENSION_ICONS[dimension]
  const band = scoreBand(score)
  const tone = band.tone === 'success' ? 'success' : band.tone === 'danger' ? 'danger' : band.tone === 'warning' ? 'warning' : 'primary'
  return (
    <Card className="h-full transition-shadow hover:shadow-raised">
      <CardBody className="flex h-full flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <span className={`grid size-9 shrink-0 place-items-center rounded-control ${RING_TONE[tone]}`}>
            {Icon && <Icon className="size-[18px]" aria-hidden />}
          </span>
          <div className="text-right">
            <p className="tabular text-xl font-semibold leading-none text-ink">
              {formatScore(score)}<span className="text-xs font-normal text-muted">/10</span>
            </p>
            <p className="mt-0.5 text-xs text-muted">{band.label}</p>
          </div>
        </div>
        <div>
          <h3 className="flex flex-wrap items-center gap-1.5 text-sm font-semibold text-ink">
            {CRITERIA_LABELS[dimension] ?? dimension}
            {isFocusArea && <span className="rounded-full bg-warning-soft px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-warning">Focus area</span>}
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-muted">{CRITERIA_DESCRIPTIONS[dimension]}</p>
        </div>
        <ProgressBar
          className="mt-auto"
          value={score}
          max={10}
          tone={tone}
          label={`${CRITERIA_LABELS[dimension] ?? dimension}: ${formatScore(score)} out of 10`}
        />
      </CardBody>
    </Card>
  )
}

/** Grid of the 4 dimension cards. `scores` may be missing a key (e.g. legacy data); those are skipped
 * rather than shown as a fabricated 0. `highlightWeakest` marks the lowest-scoring card as a "Focus area"
 * (only when 2+ dimensions are present - with one, "weakest" is meaningless). */
export function DimensionCardGrid({ scores, highlightWeakest }: { scores: Record<string, number>; highlightWeakest?: boolean }) {
  const present = CRITERIA.filter((c) => scores[c] !== undefined && scores[c] !== null)
  if (present.length === 0) return null
  const weakest = highlightWeakest && present.length > 1
    ? present.reduce((min, c) => (scores[c] < scores[min] ? c : min), present[0])
    : null
  return (
    <div className="grid grid-cols-1 gap-4 min-[30rem]:grid-cols-2 lg:grid-cols-4">
      {present.map((c) => <DimensionCard key={c} dimension={c} score={scores[c]} isFocusArea={c === weakest} />)}
    </div>
  )
}
