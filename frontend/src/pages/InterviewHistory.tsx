import { useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, History as HistoryIcon, PlayCircle } from 'lucide-react'
import { listHistory } from '@/api/interviews'
import { toApiError } from '@/api/client'
import type { InterviewOut } from '@/api/types'
import { StatusBadge } from '@/components/interview/StatusBadge'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/Feedback'
import { formatDateTime, formatScore, titleCase } from '@/utils/format'
import { interviewLink } from '@/utils/interview'

const PAGE_SIZE = 10

function actionLabel(i: InterviewOut) {
  return i.status === 'completed' ? 'View report' : 'Resume'
}

export default function InterviewHistory() {
  const [page, setPage] = useState(0)
  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: ['history', page],
    queryFn: () => listHistory({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })
  // The API returns a plain list (no total), so a full page means "there may be more".
  const hasMore = (data?.length ?? 0) === PAGE_SIZE

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[1.75rem] font-semibold">Interview history</h1>
          <p className="mt-1 text-sm text-muted">Every interview you have started, newest first.</p>
        </div>
        <ButtonLink to="/interviews/new" icon={<PlayCircle className="size-4" aria-hidden />}>New interview</ButtonLink>
      </div>

      <Card>
        {isPending && <div className="space-y-3 p-5" aria-busy="true" aria-label="Loading history">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>}
        {error && !data && <ErrorState message={toApiError(error).message} onRetry={() => refetch()} title="We couldn't load your history" />}

        {data && data.length === 0 && page === 0 && (
          <EmptyState icon={HistoryIcon} title="No interviews yet" description="Your interviews and reports will appear here once you start practising." action={<ButtonLink to="/interviews/new">Start your first interview</ButtonLink>} />
        )}
        {data && data.length === 0 && page > 0 && (
          <EmptyState title="No more interviews" description="You have reached the end of your history." action={<Button variant="secondary" onClick={() => setPage(page - 1)}>Back</Button>} />
        )}

        {data && data.length > 0 && (
          <>
            {/* Tablet/desktop: table */}
            <div className="hidden md:block">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Your interviews</caption>
                <thead>
                  <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
                    <th scope="col" className="px-5 py-3 font-semibold">Subject</th>
                    <th scope="col" className="px-3 py-3 font-semibold">Date</th>
                    <th scope="col" className="px-3 py-3 font-semibold">Difficulty</th>
                    <th scope="col" className="px-3 py-3 font-semibold">Answered</th>
                    <th scope="col" className="px-3 py-3 font-semibold">Status</th>
                    <th scope="col" className="px-3 py-3 text-right font-semibold">Score</th>
                    <th scope="col" className="px-5 py-3 text-right font-semibold"><span className="sr-only">Action</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.map((i) => (
                    <tr key={i.id} className="hover:bg-surface-2">
                      <th scope="row" className="px-5 py-3.5 font-medium text-ink">{i.subject}</th>
                      <td className="px-3 py-3.5 text-ink-2">{formatDateTime(i.started_at)}</td>
                      <td className="px-3 py-3.5 text-ink-2">{titleCase(i.difficulty)}</td>
                      <td className="tabular px-3 py-3.5 text-ink-2">{i.answered_count}/{i.num_questions}</td>
                      <td className="px-3 py-3.5"><StatusBadge status={i.status} /></td>
                      <td className="tabular px-3 py-3.5 text-right font-semibold text-ink">{i.status === 'completed' ? formatScore(i.overall_score, 1) : '—'}</td>
                      <td className="px-5 py-3.5 text-right"><Link to={interviewLink(i)} className="font-medium">{actionLabel(i)}<span className="sr-only"> — {i.subject}, {formatDateTime(i.started_at)}</span></Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile: cards */}
            <ul className="divide-y divide-line md:hidden">
              {data.map((i) => (
                <li key={i.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink">{i.subject}</p>
                      <p className="mt-0.5 text-xs text-muted">{formatDateTime(i.started_at)}</p>
                    </div>
                    <StatusBadge status={i.status} />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-sm text-ink-2">
                    <span>{titleCase(i.difficulty)} · {i.answered_count}/{i.num_questions} answered</span>
                    {i.status === 'completed' && <span className="tabular font-semibold text-ink">{formatScore(i.overall_score, 1)}/100</span>}
                  </div>
                  <Link to={interviewLink(i)} className="mt-3 inline-block text-sm font-medium">{actionLabel(i)} →</Link>
                </li>
              ))}
            </ul>

            <nav aria-label="Pagination" className="flex items-center justify-between border-t border-line px-4 py-3">
              <Button variant="secondary" size="sm" onClick={() => setPage(page - 1)} disabled={page === 0 || isFetching} icon={<ChevronLeft className="size-4" aria-hidden />}>Previous</Button>
              <span className="text-sm text-muted" aria-live="polite">Page {page + 1}</span>
              <Button variant="secondary" size="sm" onClick={() => setPage(page + 1)} disabled={!hasMore || isFetching} icon={<ChevronRight className="size-4" aria-hidden />}>Next</Button>
            </nav>
          </>
        )}
      </Card>
    </div>
  )
}
