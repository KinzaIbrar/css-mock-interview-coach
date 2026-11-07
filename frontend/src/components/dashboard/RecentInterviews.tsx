import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import type { InterviewOut } from '@/api/types'
import { StatusBadge } from '@/components/interview/StatusBadge'
import { formatDate, formatScore, titleCase } from '@/utils/format'
import { interviewLink } from '@/utils/interview'

export function RecentInterviews({ items }: { items: InterviewOut[] }) {
  return (
    <ul className="divide-y divide-line">
      {items.map((i) => (
        <li key={i.id}>
          <Link to={interviewLink(i)} className="-mx-2 flex items-center gap-3 rounded-control px-2 py-3 hover:bg-surface-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{i.subject}</p>
              <p className="mt-0.5 text-xs text-muted">{formatDate(i.started_at)} · {titleCase(i.difficulty)} · {i.answered_count}/{i.num_questions} answered</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <StatusBadge status={i.status} />
              {i.status === 'completed' && <span className="tabular text-sm font-semibold text-ink">{formatScore(i.overall_score)}<span className="font-normal text-muted">/100</span></span>}
            </div>
            <ChevronRight className="size-4 shrink-0 text-muted" aria-hidden />
            <span className="sr-only">{i.status === 'completed' ? 'View report' : 'Resume interview'}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
