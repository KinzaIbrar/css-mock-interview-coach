import { useState } from 'react'
import { ChevronDown, MessageCircleQuestion, SkipForward } from 'lucide-react'
import type { QuestionResult } from '@/api/types'
import { Badge } from '@/components/ui/Badge'
import { scoreBand, titleCase } from '@/utils/format'
import { CriteriaBars } from './CriteriaBars'
import { EvaluationSourceBadge } from './SourceBadge'

const BORDER_TONE: Record<'success' | 'primary' | 'warning' | 'danger', string> = {
  success: 'border-l-success',
  primary: 'border-l-primary',
  warning: 'border-l-warning',
  danger: 'border-l-danger',
}

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h4>
      <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-ink-2">{items.map((s) => <li key={s}>{s}</li>)}</ul>
    </div>
  )
}

export function QuestionResultCard({ q, referenceNotice }: { q: QuestionResult; referenceNotice: string }) {
  const [open, setOpen] = useState(false)
  const band = q.overall === null ? null : scoreBand(q.overall)
  const borderTone = band ? BORDER_TONE[band.tone] : 'border-l-line'
  return (
    <div className={`overflow-hidden rounded-card border-y border-r border-l-4 border-t-line border-r-line border-b-line bg-surface shadow-card transition-shadow ${borderTone} ${open ? 'shadow-raised' : 'hover:shadow-raised'}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-start gap-3 px-4 py-4 text-left transition-colors hover:bg-surface-2"
      >
        <span className="grid size-7 shrink-0 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary" aria-hidden>{q.order_index + 1}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-ink">{q.question}</span>
          <span className="mt-1.5 flex flex-wrap items-center gap-2">
            <Badge>{q.topic}</Badge>
            <Badge>{titleCase(q.difficulty)}</Badge>
            {q.skipped ? <Badge tone="warning" icon={SkipForward}>Skipped · scored 0</Badge> : <EvaluationSourceBadge source={q.evaluation_source} />}
          </span>
        </span>
        <span className="shrink-0 text-right">
          {q.overall !== null && band ? (
            <>
              <span className="tabular block text-lg font-semibold text-ink">{q.overall.toFixed(1)}<span className="text-xs font-normal text-muted">/10</span></span>
              <span className="block text-xs text-muted">{band.label}</span>
            </>
          ) : <span className="text-sm text-muted">—</span>}
        </span>
        <ChevronDown className={`mt-1 size-4 shrink-0 text-muted transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>

      {open && (
        <div className="animate-in space-y-5 border-t border-line px-4 py-5">
          {q.skipped ? (
            <p className="text-sm text-muted">You did not answer this question.</p>
          ) : (
            <>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Your answer</h4>
                <p className="mt-1.5 whitespace-pre-wrap rounded-control bg-surface-2 p-3 text-sm text-ink-2">{q.answer_text}</p>
              </div>

              {q.follow_up_question && (
                <div className="rounded-control border border-primary/20 bg-primary-soft p-3">
                  <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary-ink"><MessageCircleQuestion className="size-4" aria-hidden />Follow-up</h4>
                  <p className="mt-1.5 text-sm font-medium text-ink">{q.follow_up_question}</p>
                  <p className="mt-1.5 whitespace-pre-wrap text-sm text-ink-2">{q.follow_up_answer ?? 'You did not answer the follow-up question.'}</p>
                  {q.follow_up_evaluation && (
                    <div className="mt-2 border-t border-primary/20 pt-2 text-sm" data-testid="follow-up-evaluation">
                      <p className="font-semibold text-ink">
                        Follow-up score (separate): {q.follow_up_evaluation.overall.toFixed(1)}/10
                        <span className="ml-2 text-xs font-normal text-muted">{q.follow_up_evaluation.is_ai_generated ? 'AI-evaluated' : 'Development heuristic — not AI'}</span>
                      </p>
                      {q.follow_up_evaluation.weaknesses.length > 0 && <p className="mt-1 text-ink-2">Weaker points: {q.follow_up_evaluation.weaknesses.join(' ')}</p>}
                    </div>
                  )}
                </div>
              )}

              {q.scores && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Scores by dimension</h4>
                  <CriteriaBars scores={q.scores} />
                </div>
              )}

              <div className="grid gap-5 sm:grid-cols-3">
                <Bullets title="Strengths" items={q.strengths} />
                <Bullets title="Weaknesses" items={q.weaknesses} />
                <Bullets title="Missing points" items={q.missing_info} />
              </div>
            </>
          )}

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Reference answer (unverified sample)</h4>
            <p className="mt-1.5 whitespace-pre-wrap rounded-control border border-line p-3 text-sm text-ink-2">{q.model_answer}</p>
            <p className="mt-1.5 text-xs text-muted">{referenceNotice}</p>
          </div>
        </div>
      )}
    </div>
  )
}
