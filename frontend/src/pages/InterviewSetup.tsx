import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import type { z } from 'zod'
import { PlayCircle } from 'lucide-react'
import { getQuestionMeta, listQuestions } from '@/api/content'
import { toApiError } from '@/api/client'
import { startInterview } from '@/api/interviews'
import type { InterviewDifficulty, InterviewMode } from '@/api/types'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert, ErrorState, Skeleton } from '@/components/ui/Feedback'
import { SelectField, TextInput } from '@/components/ui/Form'
import { cn } from '@/utils/cn'
import { availableQuestions } from '@/utils/interview'
import { setupSchema } from '@/utils/schemas'
import { titleCase } from '@/utils/format'

const DIFFICULTIES: Array<{ value: InterviewDifficulty; label: string; help: string }> = [
  { value: 'mixed', label: 'Mixed', help: 'Easy to hard' },
  { value: 'easy', label: 'Easy', help: 'Core facts' },
  { value: 'medium', label: 'Medium', help: 'Explain and compare' },
  { value: 'hard', label: 'Hard', help: 'Analyse and evaluate' },
]
const MODES: Array<{ value: InterviewMode; label: string; help: string }> = [
  { value: 'mock', label: 'Mock interview', help: 'Treat it like the real thing' },
  { value: 'practice', label: 'Practice', help: 'Relaxed, learn as you go' },
]

type Values = z.infer<typeof setupSchema>

function RadioCards<T extends string>({ legend, name, value, onChange, options }: {
  legend: string; name: string; value: T; onChange: (v: T) => void; options: Array<{ value: T; label: string; help: string }>
}) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-ink">{legend}</legend>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {options.map((o) => (
          <label
            key={o.value}
            className={cn(
              'relative cursor-pointer rounded-control border px-3 py-2.5 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary',
              value === o.value ? 'border-primary bg-primary-soft' : 'border-line-strong bg-surface hover:bg-surface-2',
              options.length === 2 && 'sm:col-span-2',
            )}
          >
            <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} className="sr-only" />
            <span className="block text-sm font-semibold text-ink">{o.label}</span>
            <span className="block text-xs text-muted">{o.help}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

export default function InterviewSetup() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const meta = useQuery({ queryKey: ['question-meta'], queryFn: getQuestionMeta, staleTime: 5 * 60_000 })
  const [serverError, setServerError] = useState<string | null>(null)

  const { register, handleSubmit, control, setValue, setError, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(setupSchema),
    defaultValues: { subject: '', topic: '', difficulty: 'mixed', num_questions: 5, duration_minutes: 30, mode: 'mock' },
  })
  const [subjectName, topic, difficulty, mode, numQuestions] = useWatch({ control, name: ['subject', 'topic', 'difficulty', 'mode', 'num_questions'] })

  const subject = useMemo(() => meta.data?.subjects.find((s) => s.subject === subjectName), [meta.data, subjectName])

  // The metadata has no topic x difficulty split, so for that combination ask the server for the exact count (it uses the
  // same filters as "start"), instead of letting the user submit a request that is certain to be refused.
  const needsExactCount = Boolean(subjectName && topic && difficulty !== 'mixed')
  const exact = useQuery({
    queryKey: ['question-count', subjectName, topic, difficulty],
    queryFn: () => listQuestions({ subject: subjectName, topic, difficulty, limit: 1 }).then((r) => r.total),
    enabled: needsExactCount,
    staleTime: 5 * 60_000,
  })
  const available = needsExactCount ? (exact.data ?? null) : availableQuestions(subject, topic, difficulty)
  const checkingCount = needsExactCount && exact.isPending

  // A refused request must be seen: on small screens the Start button is far below the top of the form.
  const errorRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (serverError) {
      errorRef.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' }) // optional call: not every environment implements it
      errorRef.current?.focus()
    }
  }, [serverError])

  const start = useMutation({
    mutationFn: startInterview,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['history'] })
      navigate(`/interviews/${res.interview.id}`)
    },
  })

  const onSubmit = handleSubmit((v) => {
    setServerError(null)
    if (available !== null && v.num_questions > available) {
      setError(
        'num_questions',
        {
          message: available === 0
            ? 'No questions match this topic and difficulty. Choose another difficulty or topic.'
            : `Only ${available} question${available === 1 ? ' is' : 's are'} available for this choice. Reduce the number or change the difficulty.`,
        },
        { shouldFocus: true },
      )
      return
    }
    start.mutate(
      { subject: v.subject, difficulty: v.difficulty, num_questions: v.num_questions, duration_minutes: v.duration_minutes, mode: v.mode, topic: v.topic || null, with_introduction: true },
      {
        onError: (e) => setServerError(toApiError(e).message),
      },
    )
  })

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-[1.75rem] font-semibold">New interview</h1>
        <p className="mt-1 text-sm text-muted">Choose what you want to practise. You will be asked one question at a time.</p>
      </div>

      {meta.isPending && <Skeleton className="h-96" />}
      {meta.error && <Card><ErrorState message={toApiError(meta.error).message} onRetry={() => meta.refetch()} title="We couldn't load the question bank" /></Card>}

      {meta.data && (
        <Card>
          <CardHeader title="Interview settings" />
          <CardBody>
            <form onSubmit={onSubmit} noValidate className="space-y-6">

              <div className="grid gap-5 sm:grid-cols-2">
                <SelectField
                  label="Subject"
                  error={errors.subject?.message}
                  {...register('subject', { onChange: () => setValue('topic', '') })}
                >
                  <option value="">Select a subject…</option>
                  {meta.data.subjects.map((s) => <option key={s.subject} value={s.subject}>{s.subject} ({s.count})</option>)}
                </SelectField>

                <SelectField label="Topic (optional)" disabled={!subject} hint={subject ? 'Narrow the interview to one topic.' : 'Choose a subject first.'} {...register('topic')}>
                  <option value="">Any topic</option>
                  {subject?.topics.map((t) => <option key={t.topic} value={t.topic}>{t.topic} ({t.count})</option>)}
                </SelectField>
              </div>

              <RadioCards legend="Difficulty" name="difficulty" value={difficulty} onChange={(v) => setValue('difficulty', v, { shouldValidate: true })} options={DIFFICULTIES} />

              <div className="grid gap-5 sm:grid-cols-2">
                <TextInput
                  label="Number of questions"
                  type="number" inputMode="numeric" min={1} max={20}
                  error={errors.num_questions?.message}
                  hint={
                    !subject ? 'Between 1 and 20.'
                      : checkingCount ? 'Checking how many questions are available…'
                        : available === null ? 'Between 1 and 20.'
                          : `${available} available for this choice (max 20).`
                  }
                  {...register('num_questions', { valueAsNumber: true })}
                />
                <TextInput
                  label="Duration (minutes)"
                  type="number" inputMode="numeric" min={5} max={120}
                  error={errors.duration_minutes?.message}
                  hint="Between 5 and 120."
                  {...register('duration_minutes', { valueAsNumber: true })}
                />
              </div>

              <RadioCards legend="Mode" name="mode" value={mode} onChange={(v) => setValue('mode', v)} options={MODES} />

              <Alert tone="info" live="off">
                Duration and mode are saved with your interview and shown in the interview room. A countdown is displayed, but the server does not stop the interview when time runs out.
              </Alert>

              {serverError && (
                <div ref={errorRef} tabIndex={-1} className="rounded-control outline-none focus-visible:outline-2 focus-visible:outline-primary">
                  <Alert tone="danger" live="alert" title="We couldn't start this interview">{serverError}</Alert>
                </div>
              )}

              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-muted">
                  {subjectName ? `${numQuestions || 0} × ${titleCase(difficulty)} · ${subjectName}` : 'Select a subject to continue'}
                </p>
                <Button type="submit" size="lg" loading={start.isPending} icon={<PlayCircle className="size-5" aria-hidden />}>
                  {start.isPending ? 'Preparing your interview' : 'Start interview'}
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}
      {meta.data && <p className="text-center text-xs text-muted">{meta.data.notice}</p>}
    </div>
  )
}
