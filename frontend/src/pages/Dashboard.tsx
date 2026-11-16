import { lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, Bot, CheckCircle2, Clock3, History, Lightbulb, PlayCircle, Sparkles, Target, Trophy } from 'lucide-react'
import { getDashboard, getQuestionMeta } from '@/api/content'
import { toApiError } from '@/api/client'
import { DimensionCardGrid } from '@/components/evaluation/DimensionCards'
import { RecentInterviews } from '@/components/dashboard/RecentInterviews'
import { StatCard } from '@/components/dashboard/StatCard'
import { SubjectPerformanceList } from '@/components/dashboard/SubjectPerformance'
import { ButtonLink } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert, EmptyState, ErrorState, Skeleton } from '@/components/ui/Feedback'
import { useAuth } from '@/context/AuthContext'
import { formatScore } from '@/utils/format'

const ScoreTrendChart = lazy(() => import('@/components/dashboard/ScoreTrendChart'))

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
      <div className="grid grid-cols-1 gap-4 min-[30rem]:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid gap-6 lg:grid-cols-5"><Skeleton className="h-72 lg:col-span-3" /><Skeleton className="h-72 lg:col-span-2" /></div>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const { data, error, isPending, refetch } = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard })
  const meta = useQuery({ queryKey: ['question-meta'], queryFn: getQuestionMeta, staleTime: 5 * 60_000 })
  const firstName = user?.full_name.split(' ')[0] ?? ''

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="mt-1 hidden size-11 shrink-0 place-items-center rounded-full bg-accent text-accent-ink sm:grid" aria-hidden><Bot className="size-5" /></span>
          <div>
            <h1 className="text-[2rem] font-bold tracking-tight">Welcome back{firstName ? `, ${firstName}` : ''}</h1>
            <p className="mt-1.5 text-sm text-muted">Your AI interview coach is ready — keep building consistency, one session at a time.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink to="/history" variant="ghost" icon={<History className="size-4" aria-hidden />}>View history</ButtonLink>
          <ButtonLink to="/interviews/new" size="lg" icon={<PlayCircle className="size-5" aria-hidden />}>Start new interview</ButtonLink>
        </div>
      </div>

      {isPending && <DashboardSkeleton />}
      {error && <Card><ErrorState message={toApiError(error).message} onRetry={() => refetch()} title="We couldn't load your dashboard" /></Card>}

      {data && (
        <>
          {data.in_progress_count > 0 && (
            <Alert tone="info" title={`You have ${data.in_progress_count} unfinished interview${data.in_progress_count === 1 ? '' : 's'}`} action={<Link to="/history" className="text-sm font-medium">Resume</Link>}>
              Pick up where you left off from your interview history.
            </Alert>
          )}

          <section aria-label="Summary" className="grid grid-cols-1 gap-4 min-[30rem]:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Completed interviews" value={String(data.total_interviews)} icon={CheckCircle2} />
            <StatCard label="Average score" value={data.average_score === null ? '—' : formatScore(data.average_score, 1)} hint={data.average_score === null ? 'Complete an interview to see this' : 'Out of 10, across completed interviews'} icon={BarChart3} />
            <StatCard label="Best score" value={formatScore(data.best_score, 1)} hint={data.best_score === null ? 'Complete an interview to see this' : 'Your highest single interview'} icon={Trophy} />
            <StatCard label="In progress" value={String(data.in_progress_count)} hint="Started but not finished" icon={Clock3} />
          </section>

          <Card>
            <CardHeader
              title={<span className="flex items-center gap-2"><Sparkles className="size-4 text-primary" aria-hidden />Quick start</span>}
              description="Jump straight into a subject, or set up a custom interview."
            />
            <CardBody>
              {meta.data && meta.data.subjects.length > 0 ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    {meta.data.subjects.map((s) => (
                      <ButtonLink key={s.subject} to={`/interviews/new?subject=${encodeURIComponent(s.subject)}`} variant="secondary" size="sm">
                        {s.subject} <span className="ml-1 text-muted">({s.count})</span>
                      </ButtonLink>
                    ))}
                  </div>
                  <ButtonLink to="/interviews/new" variant="ghost" size="sm" className="mt-3" icon={<PlayCircle className="size-4" aria-hidden />}>
                    Or set up a custom interview
                  </ButtonLink>
                </>
              ) : meta.isPending ? (
                <div className="flex flex-wrap gap-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 w-28 rounded-full" />)}</div>
              ) : (
                <ButtonLink to="/interviews/new" icon={<PlayCircle className="size-4" aria-hidden />}>Start new interview</ButtonLink>
              )}
            </CardBody>
          </Card>

          {data.total_interviews === 0 && data.recent_interviews.length === 0 ? (
            <Card>
              <EmptyState
                icon={Target}
                title="Start your first mock interview"
                description="Choose a subject and difficulty. You will get one question at a time, optional follow-ups, and a full report at the end."
                action={<ButtonLink to="/interviews/new" icon={<PlayCircle className="size-4" aria-hidden />}>Start new interview</ButtonLink>}
              />
            </Card>
          ) : (
            <>
              <section aria-labelledby="dimension-performance">
                <h2 id="dimension-performance" className="text-lg font-semibold">Four-dimensional performance</h2>
                <p className="mt-1 text-sm text-muted">Your average on each CSS evaluation dimension, across every completed interview.</p>
                <div className="mt-3">
                  {Object.keys(data.dimension_performance).length === 0 ? (
                    <Card><EmptyState title="Not enough data yet" description="Complete an interview to see your dimension-by-dimension performance." /></Card>
                  ) : <DimensionCardGrid scores={data.dimension_performance} highlightWeakest />}
                </div>
              </section>

              <div className="grid gap-6 lg:grid-cols-5">
                <Card className="lg:col-span-3">
                  <CardHeader title="Performance trend" description="Score of each completed interview (most recent 10)" />
                  <CardBody>
                    {data.score_trend.length === 0 ? (
                      <EmptyState title="No completed interviews yet" description="Finish an interview and your scores will appear here." />
                    ) : (
                      <>
                        <Suspense fallback={<Skeleton className="h-56" />}><ScoreTrendChart points={data.score_trend} /></Suspense>
                        {data.score_trend.length < 2 && <p className="mt-2 text-xs text-muted">Complete more interviews to see a trend over time.</p>}
                      </>
                    )}
                  </CardBody>
                </Card>

                <Card className="lg:col-span-2">
                  <CardHeader title="Subject performance" description="Average score per subject" />
                  <CardBody>
                    {data.subject_performance.length === 0
                      ? <EmptyState title="No subject data yet" description="Complete an interview to see how each subject is going." />
                      : <SubjectPerformanceList rows={data.subject_performance} weakest={data.weakest_subject} />}
                  </CardBody>
                </Card>
              </div>

              <Card>
                <CardHeader title="Recent interviews" action={<Link to="/history" className="text-sm font-medium">View all</Link>} />
                <CardBody>
                  {data.recent_interviews.length === 0 ? <EmptyState title="Nothing here yet" /> : <RecentInterviews items={data.recent_interviews} />}
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="Suggested next steps" description="Rule-based suggestions from your saved results — not AI-generated" />
                <CardBody>
                  {data.recommendations.length === 0 ? <EmptyState title="No suggestions right now" /> : (
                    <ul className="grid gap-4 sm:grid-cols-2">
                      {data.recommendations.map((r) => (
                        <li key={r.title} className="flex gap-3 rounded-control border border-line p-3.5">
                          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent text-accent-ink"><Lightbulb className="size-4" aria-hidden /></span>
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-ink">{r.title}</p>
                            <p className="mt-0.5 text-sm text-muted">{r.detail}</p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardBody>
              </Card>

              <div className="overflow-hidden rounded-card bg-primary px-6 py-10 text-center text-white sm:px-10">
                <h2 className="text-2xl font-semibold text-white sm:text-3xl">Ready to sharpen your next answer?</h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-white/75">Start another mock interview and keep building consistency across all four evaluation dimensions.</p>
                <ButtonLink to="/interviews/new" variant="accent" size="lg" className="mt-5" icon={<PlayCircle className="size-5" aria-hidden />}>
                  Start mock interview
                </ButtonLink>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
