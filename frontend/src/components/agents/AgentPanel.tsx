import { ClipboardCheck, GraduationCap, MessageSquareText, Workflow, type LucideIcon } from 'lucide-react'
import type { AgentInfo, AgentKey } from '@/api/types'
import { cn } from '@/utils/cn'
import type { AgentStatus, AgentView } from '@/utils/agentStatus'

const ICONS: Record<AgentKey, LucideIcon> = {
  interviewer: MessageSquareText,
  evaluator: ClipboardCheck,
  coaching: GraduationCap,
  orchestration: Workflow,
}

const TONE: Record<AgentStatus, string> = {
  Active: 'bg-primary-soft text-primary',
  Speaking: 'bg-primary-soft text-primary',
  Listening: 'bg-success-soft text-success',
  Evaluating: 'bg-warning-soft text-warning',
  Coaching: 'bg-warning-soft text-warning',
  Waiting: 'bg-surface-2 text-muted',
  Completed: 'bg-success-soft text-success',
  Error: 'bg-danger-soft text-danger',
}

const FALLBACK_INFO: Record<AgentKey, { name: string; description: string }> = {
  interviewer: { name: 'Interviewer Agent', description: 'Asks the introduction, main questions and follow-ups.' },
  evaluator: { name: 'Evaluator Agent', description: 'Scores every answer and follow-up reply separately.' },
  coaching: { name: 'Coaching Agent', description: 'Finds weak topics and recommends practice.' },
  orchestration: { name: 'Orchestration Agent', description: 'Runs the LangGraph workflow connecting the agents.' },
}

interface Props { views: AgentView[]; info?: AgentInfo[] }

/** The four agents with their REAL status (derived from the room state and backend results; nothing is simulated). */
export function AgentPanel({ views, info }: Props) {
  return (
    <section aria-label="Interview agents" className="rounded-xl border border-line bg-surface p-3">
      <h2 className="mb-2 text-sm font-semibold text-ink">Your interview panel</h2>
      <ul className="space-y-2">
        {views.map((v) => {
          const Icon = ICONS[v.key]
          const meta = info?.find((a) => a.key === v.key)
          const name = meta?.name ?? FALLBACK_INFO[v.key].name
          const description = meta?.description ?? FALLBACK_INFO[v.key].description
          return (
            <li key={v.key} className="flex gap-3 rounded-lg border border-line/70 p-2.5" data-testid={`agent-${v.key}`}>
              <span className={cn('grid size-9 shrink-0 place-items-center rounded-lg', TONE[v.status])}><Icon className="size-5" aria-hidden /></span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-x-2">
                  <h3 className="text-sm font-semibold text-ink">{name}</h3>
                  <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-semibold', TONE[v.status])} data-testid={`agent-${v.key}-status`}>{v.status}</span>
                </div>
                <p className="text-xs text-muted">{description}</p>
                <p className="mt-0.5 text-xs text-ink">{v.detail}</p>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
