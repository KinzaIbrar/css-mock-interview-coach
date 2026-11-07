import { useEffect, useRef } from 'react'
import type { ConversationTurn } from '@/api/types'
import { cn } from '@/utils/cn'

const KIND_LABEL: Record<string, string> = {
  greeting: 'Interviewer',
  introduction_question: 'Interviewer',
  question: 'Interviewer',
  follow_up: 'Interviewer · follow-up',
  introduction: 'You · introduction',
  answer: 'You',
  follow_up_answer: 'You · follow-up reply',
}

/** The dialogue so far. Main questions are numbered; follow-ups are labelled and not counted as main questions. */
export function Conversation({ turns }: { turns: ConversationTurn[] }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'nearest' }) }, [turns.length])
  if (turns.length === 0) return null
  return (
    <section aria-label="Conversation so far" className="rounded-xl border border-line bg-surface p-3">
      <h2 className="mb-2 text-sm font-semibold text-ink">Conversation</h2>
      <ol className="max-h-72 space-y-2 overflow-y-auto pr-1" data-testid="conversation">
        {turns.map((t, i) => (
          <li key={i} className={cn('flex', t.role === 'candidate' ? 'justify-end' : 'justify-start')}>
            <div className={cn('max-w-[90%] rounded-lg px-3 py-2 text-sm', t.role === 'candidate' ? 'bg-primary-soft text-ink' : 'bg-surface-2 text-ink')}>
              <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                {t.kind === 'question' && t.question_number ? `Question ${t.question_number}` : KIND_LABEL[t.kind] ?? t.role}
              </p>
              <p className="whitespace-pre-wrap break-words">{t.text}</p>
            </div>
          </li>
        ))}
      </ol>
      <div ref={end} />
    </section>
  )
}
