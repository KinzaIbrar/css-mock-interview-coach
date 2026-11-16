import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import type { InterviewOut } from '@/api/types'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/interview/StatusBadge'
import { formatDate, formatScore, titleCase } from '@/utils/format'
import { interviewLink } from '@/utils/interview'

export function RecentInterviews({ items }: { items: InterviewOut[] }) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((i) => (
        <li key={i.id} className="rounded-control border border-line p-4 transition-colors hover:border-line-strong hover:bg-surface-2">
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 truncate text-sm font-semibold text-ink">{i.subject}</p>
            {i.status === 'completed'
              ? <Badge tone="accent">{formatScore(i.overall_score)}/10</Badge>
              : <StatusBadge status={i.status} />}
          </div>
          <p className="mt-1.5 text-xs text-muted">{formatDate(i.started_at)} · {titleCase(i.difficulty)} · {i.answered_count}/{i.num_questions} answered</p>
          <Link to={interviewLink(i)} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-ink hover:text-primary">
            {i.status === 'completed' ? 'See performance' : 'Resume'}
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  )
}
