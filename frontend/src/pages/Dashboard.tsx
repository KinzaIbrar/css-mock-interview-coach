import { lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, CheckCircle2, Clock3, Lightbulb, PlayCircle, Target, Trophy } from 'lucide-react'
import { getDashboard } from '@/api/content'
import { toApiError } from '@/api/client'
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
  const firstName = user?.full_name.split(' ')[0] ?? ''

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[1.75rem] font-semibold">Welcome back{firstName ? `, ${firstName}` : ''}</h1>
          <p className="mt-1 text-sm text-muted">Here is how your interview practice is going.</p>
        </div>
        <ButtonLink to="/interviews/new" size="lg" icon={<PlayCircle className="size-5" aria-hidden />}>Start new interview</ButtonLink>
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
            <StatCard label="Average score" value={data.average_score === null ? '—' : formatScore(data.average_score, 1)} hint={data.average_score === null ? 'Complete an interview to see this' : 'Out of 100, across completed interviews'} icon={BarChart3} />
            <StatCard label="Best score" value={formatScore(data.best_score, 1)} hint={data.best_score === null ? 'Complete an interview to see this' : 'Your highest single interview'} icon={Trophy} />
            <StatCard label="In progress" value={String(data.in_progress_count)} hint="Started but not finished" icon={Clock3} />
          </section>

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

              <div className="grid gap-6 lg:grid-cols-5">
                <Card className="lg:col-span-3">
                  <CardHeader title="Recent interviews" action={<Link to="/history" className="text-sm font-medium">View all</Link>} />
                  <CardBody>
                    {data.recent_interviews.length === 0 ? <EmptyState title="Nothing here yet" /> : <RecentInterviews items={data.recent_interviews} />}
                  </CardBody>
                </Card>

                <Card className="lg:col-span-2">
                  <CardHeader title="Suggested next steps" description="Rule-based suggestions from your saved results — not AI-generated" />
                  <CardBody>
                    {data.recommendations.length === 0 ? <EmptyState title="No suggestions right now" /> : (
                      <ul className="space-y-4">
                        {data.recommendations.map((r) => (
                          <li key={r.title} className="flex gap-3">
                            <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                            <div>
                              <p className="text-sm font-medium text-ink">{r.title}</p>
                              <p className="mt-0.5 text-sm text-muted">{r.detail}</p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardBody>
                </Card>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
