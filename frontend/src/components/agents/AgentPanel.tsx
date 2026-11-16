import { ClipboardCheck, GraduationCap, MessageSquareText, Users, Workflow, type LucideIcon } from 'lucide-react'
import type { AgentInfo, AgentKey } from '@/api/types'
import { cn } from '@/utils/cn'
import type { AgentStatus, AgentView } from '@/utils/agentStatus'

const ICONS: Record<AgentKey, LucideIcon> = {
  interviewer: MessageSquareText,
  evaluator: ClipboardCheck,
  coaching: GraduationCap,
  orchestration: Workflow,
}

/** Each agent keeps its own identity colour regardless of status, so the panel reads as four
 * distinct specialists rather than four identical rows. The status pill next to its name is the
 * only thing that changes colour with state - never the only signal, since the word is always there too. */
const IDENTITY: Record<AgentKey, string> = {
  interviewer: 'bg-primary-soft text-primary-ink',
  evaluator: 'bg-accent-soft text-accent-ink',
  coaching: 'bg-warning-soft text-warning',
  orchestration: 'bg-success-soft text-success',
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

/** Statuses that mean the agent is actually doing something right now, worth a gentle pulse. */
const LIVE: Set<AgentStatus> = new Set(['Active', 'Speaking', 'Listening', 'Evaluating', 'Coaching'])

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
    <section aria-label="Interview agents" className="rounded-card border border-line bg-surface p-3.5">
      <h2 className="mb-2.5 flex items-center gap-1.5 text-sm font-semibold text-ink"><Users className="size-4 text-primary" aria-hidden />Your interview panel</h2>
      <ul className="space-y-2">
        {views.map((v) => {
          const Icon = ICONS[v.key]
          const meta = info?.find((a) => a.key === v.key)
          const name = meta?.name ?? FALLBACK_INFO[v.key].name
          const description = meta?.description ?? FALLBACK_INFO[v.key].description
          const live = LIVE.has(v.status)
          return (
            <li key={v.key} className="flex gap-3 rounded-control border border-line/70 p-2.5 transition-colors" data-testid={`agent-${v.key}`}>
              <span className={cn('relative grid size-9 shrink-0 place-items-center rounded-control', IDENTITY[v.key])}>
                <Icon className="size-5" aria-hidden />
                {live && <span className="absolute -right-0.5 -top-0.5 size-2.5 animate-pulse-soft rounded-full bg-success ring-2 ring-surface" aria-hidden />}
              </span>
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
