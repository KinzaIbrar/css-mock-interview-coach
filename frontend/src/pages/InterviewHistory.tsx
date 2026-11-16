import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3, CheckCircle2, ChevronLeft, ChevronRight, Compass, Filter, PlayCircle, SearchX, Trophy, X,
} from 'lucide-react'
import { getDashboard } from '@/api/content'
import { listHistory } from '@/api/interviews'
import { toApiError } from '@/api/client'
import type { InterviewOut } from '@/api/types'
import { StatCard } from '@/components/dashboard/StatCard'
import { StatusBadge } from '@/components/interview/StatusBadge'
import { ProgressBar } from '@/components/ui/Badge'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/Feedback'
import { SelectField, TextInput } from '@/components/ui/Form'
import { formatDateTime, formatScore, scoreBand, titleCase } from '@/utils/format'
import { interviewLink } from '@/utils/interview'

const PAGE_SIZE = 10
// The /interviews/history endpoint has no search/filter/sort params and always orders newest
// first (see backend/app/services/interview_service.py); it caps `limit` at 200. Rather than add
// backend work, we load the user's most recent 200 interviews in one request (the same existing
// API call, just with a larger limit) and do search/filter/sort over that loaded set - more than
// enough for how this app is used today. If an account ever exceeds 200 interviews, the oldest
// ones fall outside what search/filter can reach; nothing is hidden silently, this comment is the
// one place that tradeoff lives.
const HISTORY_FETCH_LIMIT = 200

type StatusFilter = '' | 'completed' | 'in_progress'
type SortKey = 'newest' | 'oldest' | 'highest' | 'lowest'

function actionLabel(i: InterviewOut) {
  return i.status === 'completed' ? 'View report' : 'Resume'
}

function HistorySkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading interview history">
      <div className="grid grid-cols-1 gap-4 min-[30rem]:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <Skeleton className="h-24" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36" />)}
      </div>
    </div>
  )
}

function InterviewCard({ item }: { item: InterviewOut }) {
  const band = item.status === 'completed' && item.overall_score !== null ? scoreBand(item.overall_score) : null
  const tone = !band ? 'primary' : band.tone === 'success' ? 'success' : band.tone === 'danger' ? 'danger' : band.tone === 'warning' ? 'warning' : 'primary'
  return (
    <li className="flex flex-col rounded-card border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-raised">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-ink">{item.subject}</p>
          <p className="mt-0.5 text-xs text-muted">{formatDateTime(item.started_at)}</p>
        </div>
        <StatusBadge status={item.status} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span>{titleCase(item.difficulty)}</span>
        <span aria-hidden>·</span>
        <span>{item.answered_count}/{item.num_questions} answered</span>
        {item.duration_minutes != null && (
          <>
            <span aria-hidden>·</span>
            <span>{item.duration_minutes} min</span>
          </>
        )}
      </div>

      <div className="mt-3">
        {item.status === 'completed' && item.overall_score !== null && band ? (
          <>
            <div className="flex items-baseline justify-between text-sm">
              <span className="text-muted">Score</span>
              <span className="tabular font-semibold text-ink">{formatScore(item.overall_score, 1)}<span className="font-normal text-muted">/10 · {band.label}</span></span>
            </div>
            <ProgressBar className="mt-1.5" value={item.overall_score} max={10} tone={tone} label={`${item.subject} score: ${formatScore(item.overall_score, 1)} out of 10`} />
          </>
        ) : (
          <p className="text-sm text-muted">{item.status === 'in_progress' ? 'Not finished yet — no score until you complete it.' : 'No score available.'}</p>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3 text-sm font-medium">
        <Link to={interviewLink(item)}>{actionLabel(item)} →</Link>
        {item.status === 'completed' && (
          <Link to={`/interviews/new?subject=${encodeURIComponent(item.subject)}`} className="text-muted hover:text-ink">Practice again</Link>
        )}
      </div>
    </li>
  )
}

export default function InterviewHistory() {
  const dash = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ['history-all'],
    queryFn: () => listHistory({ limit: HISTORY_FETCH_LIMIT, offset: 0 }),
  })

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<StatusFilter>('')
  const [subject, setSubject] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sort, setSort] = useState<SortKey>('newest')
  const [page, setPage] = useState(0)

  const subjects = useMemo(() => Array.from(new Set((data ?? []).map((i) => i.subject))).sort(), [data])
  const filtersActive = Boolean(search || status || subject || dateFrom || dateTo || sort !== 'newest')

  const filtered = useMemo(() => {
    let rows = data ?? []
    const q = search.trim().toLowerCase()
    if (q) rows = rows.filter((i) => i.subject.toLowerCase().includes(q))
    if (status) rows = rows.filter((i) => i.status === status)
    if (subject) rows = rows.filter((i) => i.subject === subject)
    if (dateFrom) rows = rows.filter((i) => i.started_at >= dateFrom)
    if (dateTo) rows = rows.filter((i) => i.started_at <= `${dateTo}T23:59:59`)
    const sorted = [...rows]
    if (sort === 'oldest') sorted.sort((a, b) => a.started_at.localeCompare(b.started_at))
    else if (sort === 'newest') sorted.sort((a, b) => b.started_at.localeCompare(a.started_at))
    else if (sort === 'highest') sorted.sort((a, b) => (b.overall_score ?? -1) - (a.overall_score ?? -1))
    else if (sort === 'lowest') sorted.sort((a, b) => (a.overall_score ?? 11) - (b.overall_score ?? 11))
    return sorted
  }, [data, search, status, subject, dateFrom, dateTo, sort])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)
  const from = filtered.length === 0 ? 0 : safePage * PAGE_SIZE + 1
  const to = Math.min(filtered.length, (safePage + 1) * PAGE_SIZE)

  const clearFilters = () => { setSearch(''); setStatus(''); setSubject(''); setDateFrom(''); setDateTo(''); setSort('newest'); setPage(0) }

  const totalInterviews = dash.data ? dash.data.total_interviews + dash.data.in_progress_count : null

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-[2rem] font-bold tracking-tight"><Compass className="size-7 text-primary" aria-hidden />Interview history</h1>
          <p className="mt-1.5 text-sm text-muted">Review your previous interviews, track your progress, and revisit your performance.</p>
        </div>
        <ButtonLink to="/interviews/new" icon={<PlayCircle className="size-4" aria-hidden />}>Start new interview</ButtonLink>
      </div>

      {isPending && <HistorySkeleton />}
      {error && !data && <Card><ErrorState message={toApiError(error).message} onRetry={() => refetch()} title="We couldn't load your history" /></Card>}

      {data && (
        <>
          <section aria-label="Interview statistics" className="grid grid-cols-1 gap-4 min-[30rem]:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total interviews" value={totalInterviews === null ? '—' : String(totalInterviews)} icon={Compass} />
            <StatCard label="Completed" value={dash.data ? String(dash.data.total_interviews) : '—'} icon={CheckCircle2} />
            <StatCard label="Average score" value={dash.data?.average_score == null ? '—' : formatScore(dash.data.average_score, 1)} hint="Out of 10" icon={BarChart3} />
            <StatCard label="Best score" value={dash.data?.best_score == null ? '—' : formatScore(dash.data.best_score, 1)} hint="Out of 10" icon={Trophy} />
          </section>

          {data.length === 0 ? (
            <Card>
              <EmptyState
                icon={Compass}
                title="Your interview journey starts here."
                description="Choose a subject and difficulty, answer one question at a time, and get a full report at the end."
                action={<ButtonLink to="/interviews/new" icon={<PlayCircle className="size-4" aria-hidden />}>Start your first interview</ButtonLink>}
              />
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader title={<span className="flex items-center gap-2"><Filter className="size-4 text-primary" aria-hidden />Search &amp; filter</span>} />
                <CardBody>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <TextInput label="Search by subject" type="search" value={search} placeholder="e.g. Pakistan Affairs" onChange={(e) => { setSearch(e.target.value); setPage(0) }} />
                    <SelectField label="Status" value={status} onChange={(e) => { setStatus(e.target.value as StatusFilter); setPage(0) }}>
                      <option value="">All statuses</option>
                      <option value="completed">Completed</option>
                      <option value="in_progress">In progress</option>
                    </SelectField>
                    <SelectField label="Subject" value={subject} onChange={(e) => { setSubject(e.target.value); setPage(0) }}>
                      <option value="">All subjects</option>
                      {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
                    </SelectField>
                    <SelectField label="Sort by" value={sort} onChange={(e) => { setSort(e.target.value as SortKey); setPage(0) }}>
                      <option value="newest">Newest first</option>
                      <option value="oldest">Oldest first</option>
                      <option value="highest">Highest score first</option>
                      <option value="lowest">Lowest score first</option>
                    </SelectField>
                    <TextInput label="From date" type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(0) }} />
                    <TextInput label="To date" type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(0) }} />
                  </div>
                  {filtersActive && (
                    <Button variant="ghost" size="sm" className="mt-3" onClick={clearFilters} icon={<X className="size-3.5" aria-hidden />}>Clear filters</Button>
                  )}
                </CardBody>
              </Card>

              {filtered.length === 0 ? (
                <Card>
                  <EmptyState icon={SearchX} title="No interviews match these filters" description="Try a different search or clear a filter to see more." action={<Button variant="secondary" onClick={clearFilters}>Clear filters</Button>} />
                </Card>
              ) : (
                <>
                  <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {pageRows.map((item) => <InterviewCard key={item.id} item={item} />)}
                  </ul>

                  {pageCount > 1 && (
                    <nav aria-label="Pagination" className="flex items-center justify-between rounded-card border border-line bg-surface px-4 py-3">
                      <Button variant="secondary" size="sm" onClick={() => setPage(safePage - 1)} disabled={safePage === 0} icon={<ChevronLeft className="size-4" aria-hidden />}>Previous</Button>
                      <span className="text-sm text-muted tabular" aria-live="polite">{from}–{to} of {filtered.length}</span>
                      <Button variant="secondary" size="sm" onClick={() => setPage(safePage + 1)} disabled={safePage >= pageCount - 1} icon={<ChevronRight className="size-4" aria-hidden />}>Next</Button>
                    </nav>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
