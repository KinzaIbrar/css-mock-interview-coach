import { GraduationCap, ScanEye } from 'lucide-react'
import type { Coaching, NonVerbalReport } from '@/api/types'
import { Badge } from '@/components/ui/Badge'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'

/** Coaching Agent output (rule-based from the saved evaluations; labelled as such). */
export function CoachingCard({ coaching }: { coaching: Coaching }) {
  const empty =
    !coaching.weak_topics.length && !coaching.misunderstood_concepts.length && !coaching.recurring_mistakes.length && !coaching.recommended_practice.length
  return (
    <Card>
      <CardHeader
        as="h2"
        title={<span className="flex items-center gap-2"><GraduationCap className="size-5 text-primary" aria-hidden />Coaching plan</span>}
        description="Built by rules from your saved evaluations and the question bank."
        action={<Badge>Coaching Agent · rule-based, not AI</Badge>}
      />
      <CardBody className="space-y-5">
        {empty && <p className="text-sm text-muted">Nothing needs special attention from this interview.</p>}
        {coaching.weak_topics.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold">Weak topics</h3>
            <ul className="mt-1.5 space-y-1 text-sm">
              {coaching.weak_topics.map((t) => (
                <li key={t.topic}><span className="font-medium">{t.topic}</span> <span className="text-muted">— {Math.round(t.score)}/100. {t.reason}</span></li>
              ))}
            </ul>
          </div>
        )}
        {coaching.misunderstood_concepts.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold">Concepts to revisit</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-ink-2">{coaching.misunderstood_concepts.map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
        )}
        {coaching.recurring_mistakes.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold">Recurring mistakes</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-ink-2">{coaching.recurring_mistakes.map((m) => <li key={m.pattern}>{m.pattern} <span className="text-muted">(×{m.count})</span></li>)}</ul>
          </div>
        )}
        {coaching.recommended_practice.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold">Recommended practice</h3>
            <ul className="mt-1.5 space-y-1.5 text-sm">
              {coaching.recommended_practice.map((p) => (
                <li key={p.question_id} className="rounded-control bg-surface-2 p-2.5">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted">{p.topic} · {p.difficulty}</span>
                  <p className="text-ink">{p.question}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

/** Observable behaviours only. Separate from the verbal score; never combined into one number. */
export function NonVerbalCard({ report }: { report: NonVerbalReport }) {
  return (
    <Card>
      <CardHeader
        as="h2"
        title={<span className="flex items-center gap-2"><ScanEye className="size-5 text-primary" aria-hidden />Non-verbal observations</span>}
        description="Separate from your verbal score. Simple, observable indicators only."
      />
      <CardBody className="space-y-4">
        {(report.observation_coverage_pct !== null || report.tracking_quality_pct !== null) && (
          <p className="text-sm text-muted">
            {report.observation_coverage_pct !== null && <>Observation coverage: <strong className="text-ink">{Math.round(report.observation_coverage_pct)}%</strong>. </>}
            {report.tracking_quality_pct !== null && <>Tracking quality: <strong className="text-ink">{Math.round(report.tracking_quality_pct)}%</strong>.</>}
          </p>
        )}
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {report.metrics.map((m) => (
            <div key={m.key} className="flex items-baseline justify-between gap-3 border-b border-line py-1 text-sm">
              <dt className="text-muted">{m.label}</dt>
              <dd className={m.available ? 'font-semibold text-ink' : 'text-muted'}>{m.available ? m.value : (m.note ?? 'Not enough data')}</dd>
            </div>
          ))}
        </dl>
        <div className="space-y-1.5 text-xs text-muted">
          {report.limitations.map((l) => <p key={l}>{l}</p>)}
        </div>
        <details className="text-xs text-muted">
          <summary className="cursor-pointer font-medium text-ink-2">How these are calculated</summary>
          <ul className="mt-1.5 list-disc space-y-1 pl-5">{report.rules.map((r) => <li key={r}>{r}</li>)}</ul>
        </details>
      </CardBody>
    </Card>
  )
}
