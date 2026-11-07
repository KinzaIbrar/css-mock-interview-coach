import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, CircleHelp, Compass, PlayCircle } from 'lucide-react'
import { getReport } from '@/api/content'
import { toApiError } from '@/api/client'
import type { Report } from '@/api/types'
import { CriteriaBars } from '@/components/evaluation/CriteriaBars'
import { CoachingCard, NonVerbalCard } from '@/components/evaluation/ReportExtras'
import { QuestionResultCard } from '@/components/evaluation/QuestionResultCard'
import { ScoreRing } from '@/components/evaluation/ScoreRing'
import { EvaluationSourceBadge, FeedbackSourceBadge } from '@/components/evaluation/SourceBadge'
import { Badge } from '@/components/ui/Badge'
import { ButtonLink } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert, ErrorState, Skeleton } from '@/components/ui/Feedback'
import { formatDateTime, scoreBand, titleCase } from '@/utils/format'

/** How the evaluation was produced, in plain words. Never hides a fallback. */
function SourceBanner({ report }: { report: Report }) {
  const model = report.evaluation_model ?? undefined
  if (report.evaluation_source === 'gemini') {
    return <Alert tone="info" title={`Evaluated by AI${model ? ` (${model})` : ''}`}>{report.notice}</Alert>
  }
  if (report.evaluation_source === 'mixed') {
    return <Alert tone="warning" title="Partly AI-evaluated">{report.notice} Check the label on each question below.</Alert>
  }
  return (
    <Alert tone="warning" title="Development evaluation — not AI">
      {report.notice} This happens when the AI service is not configured or was unavailable. The scores come from a simple keyword check, so treat them as rough guidance only.
    </Alert>
  )
}

function ItemList({ title, items, icon: Icon, empty }: { title: string; items: string[]; icon: typeof CheckCircle2; empty: string }) {
  return (
    <Card>
      <CardHeader as="h3" title={<span className="flex items-center gap-2"><Icon className="size-4 text-primary" aria-hidden />{title}</span>} />
      <CardBody>
        {items.length === 0 ? <p className="text-sm text-muted">{empty}</p> : (
          <ul className="list-disc space-y-2 pl-5 text-sm text-ink-2">{items.map((s) => <li key={s}>{s}</li>)}</ul>
        )}
      </CardBody>
    </Card>
  )
}

export default function InterviewResults() {
  const id = Number(useParams().id)
  const { data: report, error, isPending, refetch } = useQuery({ queryKey: ['report', id], queryFn: () => getReport(id), enabled: Number.isFinite(id) })

  if (isPending) return <div className="space-y-4" aria-busy="true" aria-label="Loading report"><Skeleton className="h-40" /><Skeleton className="h-64" /></div>
  if (error) {
    const err = toApiError(error)
    return (
      <Card>
        <ErrorState
          title={err.status === 409 ? 'This interview is not finished yet' : err.status === 404 ? 'Report not found' : "We couldn't load this report"}
          message={err.status === 409 ? 'Finish the interview to see your report.' : err.status === 404 ? 'It may belong to another account.' : err.message}
          onRetry={err.status === 404 || err.status === 409 ? undefined : () => refetch()}
        />
        <div className="flex justify-center gap-4 pb-6 text-sm font-medium">
          {err.status === 409 && <Link to={`/interviews/${id}`}>Resume interview</Link>}
          <Link to="/history">Interview history</Link>
        </div>
      </Card>
    )
  }

  const band = scoreBand(report.overall_score)
  const answered = report.questions.filter((q) => !q.skipped).length

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted">Interview report</p>
          <h1 className="text-[1.75rem] font-semibold">{report.interview.subject}</h1>
          <p className="mt-1 text-sm text-muted">
            {titleCase(report.interview.difficulty)} · {answered} of {report.questions.length} answered · {formatDateTime(report.interview.completed_at ?? report.interview.started_at)}
          </p>
        </div>
        <ButtonLink to="/interviews/new" icon={<PlayCircle className="size-4" aria-hidden />}>Practise again</ButtonLink>
      </div>

      <SourceBanner report={report} />

      <Card>
        <CardBody className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
          <ScoreRing score={report.overall_score} />
          <div className="min-w-0 flex-1 text-center sm:text-left">
            <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
              <h2 className="text-lg font-semibold">Overall: {band.label}</h2>
              <EvaluationSourceBadge source={report.evaluation_source} model={report.evaluation_model} />
              <FeedbackSourceBadge source={report.feedback_source} />
            </div>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">{report.summary}</p>
            {report.progress_note && (
              <p className="mt-3 text-sm text-muted">
                <Badge className="mr-2">Progress · rule-based, not AI</Badge>{report.progress_note}
              </p>
            )}
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Scores by criterion" description="Averaged across all questions. Unanswered questions count as 0." />
          <CardBody><CriteriaBars scores={report.criteria_scores} /></CardBody>
        </Card>
        <Card>
          <CardHeader title="Personalised feedback" action={<FeedbackSourceBadge source={report.feedback_source} />} />
          <CardBody className="space-y-5">
            <div>
              <h3 className="text-sm font-semibold text-ink">How to improve</h3>
              {report.improvements.length === 0 ? <p className="mt-1.5 text-sm text-muted">No suggestions.</p> : (
                <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-ink-2">{report.improvements.map((s) => <li key={s}>{s}</li>)}</ul>
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink">Topics to revise</h3>
              {report.revision_topics.length === 0
                ? <p className="mt-1.5 text-sm text-muted">No specific topics flagged.</p>
                : <div className="mt-2 flex flex-wrap gap-2">{report.revision_topics.map((t) => <Badge key={t} tone="primary">{t}</Badge>)}</div>}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink">Recommended next practice</h3>
              <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-ink-2">{report.next_practice.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <ItemList title="Strengths" items={report.strengths} icon={CheckCircle2} empty="No strengths were identified." />
        <ItemList title="Weaknesses" items={report.weaknesses} icon={AlertTriangle} empty="No weaknesses were identified." />
        <ItemList title="Missing important points" items={report.missing_info} icon={CircleHelp} empty="No missing points were identified." />
      </div>

      {report.follow_up_average !== null && (
        <p className="rounded-control border border-line bg-surface p-3 text-sm text-ink-2" data-testid="follow-up-average">
          Follow-up replies average <strong className="text-ink">{Math.round(report.follow_up_average)}/100</strong>. They are scored separately and are not part of the overall score above.
        </p>
      )}
      {report.coaching && <CoachingCard coaching={report.coaching} />}
      {report.observations && <NonVerbalCard report={report.observations} />}

      <section aria-labelledby="per-question">
        <h2 id="per-question" className="mb-3 flex items-center gap-2 text-lg font-semibold"><Compass className="size-5 text-primary" aria-hidden />Question by question</h2>
        <div className="space-y-3">
          {report.questions.map((q) => <QuestionResultCard key={q.question_id} q={q} referenceNotice={report.reference_notice} />)}
        </div>
      </section>

      <p className="text-center text-xs text-muted">{report.reference_notice}</p>
    </div>
  )
}
