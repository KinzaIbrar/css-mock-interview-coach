import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, CheckCircle2, Flag, MessageCircleQuestion } from 'lucide-react'
import { toApiError, type ApiError } from '@/api/client'
import {
  completeInterview, getInterview, listAgents, nextQuestion, saveObservations, submitAnswer, submitFollowUp, submitIntroduction,
} from '@/api/interviews'
import type { AgentStep, ConversationTurn, InterviewDetail, InterviewOut, IntroductionPrompt, QuestionPublic } from '@/api/types'
import { AgentPanel } from '@/components/agents/AgentPanel'
import { InterviewerAvatar, type AvatarState } from '@/components/avatar/InterviewerAvatar'
import { CameraPanel } from '@/components/camera/CameraPanel'
import { EvaluationSourceBadge } from '@/components/evaluation/SourceBadge'
import { AiNotice } from '@/components/interview/AiNotice'
import { AnswerComposer } from '@/components/interview/AnswerComposer'
import { Conversation } from '@/components/interview/Conversation'
import { EvaluatingPanel } from '@/components/interview/EvaluatingPanel'
import { InterviewTimer } from '@/components/interview/InterviewTimer'
import { Badge, ProgressBar } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody } from '@/components/ui/Card'
import { Alert, ErrorState, Skeleton } from '@/components/ui/Feedback'
import { useCamera } from '@/hooks/useCamera'
import { useSpeechSynthesis } from '@/hooks/useSpeechSynthesis'
import { deriveAgents, type RoomPhase } from '@/utils/agentStatus'
import { titleCase } from '@/utils/format'

type Phase = Exclude<RoomPhase, 'completed'>

interface AckInfo {
  source: string | null
  notice: string | null
  /** True when the request outcome was recovered from the server instead of read from a response. */
  recovered?: boolean
}

const difficultyTone = { easy: 'success', medium: 'primary', hard: 'warning' } as const

export default function InterviewRoom() {
  const { id: idParam } = useParams()
  const id = Number(idParam)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const speech = useSpeechSynthesis()
  const videoRef = useRef<HTMLVideoElement>(null)
  const camera = useCamera(videoRef)
  const agentInfo = useQuery({ queryKey: ['agents'], queryFn: listAgents, staleTime: 60_000, retry: false })

  const [phase, setPhase] = useState<Phase>('loading')
  const [interview, setInterview] = useState<InterviewOut | null>(null)
  const [question, setQuestion] = useState<QuestionPublic | null>(null)
  const [introPrompt, setIntroPrompt] = useState<IntroductionPrompt | null>(null)
  const [conversation, setConversation] = useState<ConversationTurn[]>([])
  const [trace, setTrace] = useState<AgentStep[]>([])
  const [questionNumber, setQuestionNumber] = useState(1)
  const [total, setTotal] = useState(0)
  const [hasNext, setHasNext] = useState(false)
  const [answer, setAnswer] = useState('')
  const [introAnswer, setIntroAnswer] = useState('')
  const [followUpText, setFollowUpText] = useState<string | null>(null)
  const [followUpAnswer, setFollowUpAnswer] = useState('')
  const [ack, setAck] = useState<AckInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<ApiError | null>(null)
  const [advancing, setAdvancing] = useState(false)
  const [confirmFinish, setConfirmFinish] = useState(false)

  const busy = useRef(false) // synchronous lock: a second click can never start a second request
  const uncertain = useRef(false) // a request failed with an unknown outcome: re-check the server before resending
  const questionShownAt = useRef(0) // set when a question is shown (Date.now() is not allowed during render)
  const dictation = useRef({ words: 0, seconds: 0 })
  const answerRef = useRef<HTMLTextAreaElement>(null)
  const followUpRef = useRef<HTMLTextAreaElement>(null)
  const introRef = useRef<HTMLTextAreaElement>(null)

  const onDictation = useCallback((d: { words: number; seconds: number }) => {
    dictation.current.words += d.words
    dictation.current.seconds += d.seconds
  }, [])

  const applyDetail = useCallback((d: InterviewDetail) => {
    questionShownAt.current = Date.now()
    setInterview(d.interview)
    setQuestion(d.current_question)
    setIntroPrompt(d.introduction_prompt)
    setConversation(d.conversation)
    setQuestionNumber(d.question_number)
    setTotal(d.total_questions)
    setHasNext(d.interview.current_index + 1 < d.total_questions)
    const answered = d.answered_indexes.includes(d.interview.current_index)
    if (d.introduction_pending) {
      setFollowUpText(null)
      setPhase('introduction')
    } else if (d.pending_follow_up) {
      setFollowUpText(d.pending_follow_up)
      setPhase('follow_up')
    } else if (answered) {
      setFollowUpText(null)
      setPhase('answered')
    } else {
      setFollowUpText(null)
      setPhase('answering')
    }
    return { answered, pending: d.pending_follow_up }
  }, [])

  const load = useCallback(async () => {
    try {
      const d = await getInterview(id)
      setLoadError(null)
      if (d.interview.status === 'completed') {
        navigate(`/interviews/${id}/results`, { replace: true })
        return null
      }
      return { detail: d, ...applyDetail(d) }
    } catch (e) {
      setLoadError(toApiError(e))
      return null
    }
  }, [id, navigate, applyDetail])

  useEffect(() => {
    if (!Number.isFinite(id)) return
    void load()
  }, [id, load])

  /** Refresh the transcript from the server (the source of truth); failures are harmless. */
  const refreshConversation = useCallback(async () => {
    try { setConversation((await getInterview(id)).conversation) } catch { /* keep what we have */ }
  }, [id])

  // Focus the right box whenever something is ready to be answered.
  useEffect(() => {
    if (phase === 'introduction') introRef.current?.focus()
    if (phase === 'answering') answerRef.current?.focus()
    if (phase === 'follow_up') followUpRef.current?.focus()
  }, [phase, question?.id])

  // Warn before closing the tab while the server is working on the candidate's answer.
  const waiting = phase === 'submitting' || phase === 'submitting_follow_up' || phase === 'submitting_introduction' || phase === 'finishing'
  useEffect(() => {
    if (!waiting) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [waiting])

  const secondsSpent = () => Math.max(0, Math.round((Date.now() - questionShownAt.current) / 1000))

  /** After a failed request, ask the server what actually happened. Returns the fresh state or null if unreachable. */
  const recheck = async () => {
    try {
      const d = await getInterview(id)
      if (d.interview.status === 'completed') { navigate(`/interviews/${id}/results`, { replace: true }); return 'completed' as const }
      return { detail: d }
    } catch {
      return null
    }
  }

  // ---- submit the introduction -------------------------------------------------------------------------------------
  const onSubmitIntroduction = async () => {
    const text = introAnswer.trim()
    if (!text || busy.current || phase !== 'introduction') return
    busy.current = true
    setError(null)
    setPhase('submitting_introduction')
    try {
      const res = await submitIntroduction({ interview_id: id, answer_text: text, time_taken_seconds: secondsSpent() })
      setTrace(res.trace ?? [])
      questionShownAt.current = Date.now()
      setPhase('answering')
      void refreshConversation()
    } catch (e) {
      const err = toApiError(e)
      if (err.status === 401) return
      const fresh = err.status === 409 || err.outcomeUnknown ? await recheck() : null
      if (fresh === 'completed') return
      if (fresh && !fresh.detail.introduction_pending) { applyDetail(fresh.detail); return } // it was saved after all
      setPhase('introduction')
      setError(err.message)
    } finally {
      busy.current = false
    }
  }

  // ---- submit the main answer ------------------------------------------------------------------------------------
  const onSubmitAnswer = async () => {
    const text = answer.trim()
    if (!text || busy.current || phase !== 'answering') return
    busy.current = true
    setError(null)
    setPhase('submitting')
    try {
      if (uncertain.current) {
        // Last time we could not tell whether the answer was saved. Check first so it is never sent twice.
        const fresh = await recheck()
        if (fresh === 'completed') return
        if (fresh && fresh.detail.answered_indexes.includes(fresh.detail.interview.current_index)) {
          uncertain.current = false
          applyDetail(fresh.detail)
          setAck({ source: null, notice: null, recovered: true })
          return
        }
        if (!fresh) { setPhase('answering'); setError("We still can't reach the server. Your answer is kept below — try again in a moment."); return }
        uncertain.current = false
      }
      const res = await submitAnswer({ interview_id: id, answer_text: text, time_taken_seconds: secondsSpent() })
      setAck({ source: res.evaluation_source, notice: res.ai_notice })
      setTrace(res.trace ?? [])
      if (res.ai_notice) void queryClient.invalidateQueries({ queryKey: ['health'] })
      setHasNext(res.has_next)
      if (res.follow_up_question) { setFollowUpText(res.follow_up_question); setFollowUpAnswer(''); setPhase('follow_up') }
      else setPhase('answered')
      void refreshConversation()
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    } catch (e) {
      const err = toApiError(e)
      if (err.status === 401) return // the auth handler signs the user out
      if (err.status === 409 || err.outcomeUnknown) {
        const fresh = await recheck()
        if (fresh === 'completed') return
        if (fresh && fresh.detail.answered_indexes.includes(fresh.detail.interview.current_index)) {
          applyDetail(fresh.detail)
          setAck({ source: null, notice: null, recovered: true })
          return
        }
        if (!fresh) uncertain.current = true
        setPhase('answering')
        setError(
          fresh
            ? `${err.message} Your answer was not saved, so it is safe to try again.`
            : `${err.message} We could not confirm whether your answer was saved. When you try again we will check first, so it will not be sent twice.`,
        )
        return
      }
      setPhase('answering')
      setError(err.message)
    } finally {
      busy.current = false
    }
  }

  // ---- submit the follow-up reply ----------------------------------------------------------------------------------
  const onSubmitFollowUp = async () => {
    const text = followUpAnswer.trim()
    if (!text || busy.current || phase !== 'follow_up') return
    busy.current = true
    setError(null)
    setPhase('submitting_follow_up')
    try {
      const res = await submitFollowUp({ interview_id: id, answer_text: text, time_taken_seconds: secondsSpent() })
      setAck({ source: res.evaluation_source, notice: res.ai_notice })
      setTrace(res.trace ?? [])
      if (res.ai_notice) void queryClient.invalidateQueries({ queryKey: ['health'] })
      setHasNext(res.has_next)
      setFollowUpText(null)
      setPhase('answered')
      void refreshConversation()
    } catch (e) {
      const err = toApiError(e)
      if (err.status === 401) return
      if (err.status === 409 || err.outcomeUnknown) {
        const fresh = await recheck()
        if (fresh === 'completed') return
        if (fresh && !fresh.detail.pending_follow_up) {
          applyDetail(fresh.detail)
          setAck({ source: null, notice: null, recovered: true })
          return
        }
        setPhase('follow_up')
        setError(fresh ? `${err.message} Your reply was not saved, so it is safe to try again.` : `${err.message} We could not confirm whether your reply was saved.`)
        return
      }
      setPhase('follow_up')
      setError(err.message)
    } finally {
      busy.current = false
    }
  }

  // ---- next question / finish -------------------------------------------------------------------------------------
  /** Send the browser-computed AGGREGATES (never video or frames), then release the camera. Best effort. */
  const sendObservations = async () => {
    const cam = camera.collect()
    camera.stop()
    const d = dictation.current
    if (!cam && d.words === 0) return
    try {
      await saveObservations({
        interview_id: id,
        ...(cam ? { camera: cam } : {}),
        ...(d.words > 0 ? { voice: { dictated_words: Math.round(d.words), dictated_seconds: Math.round(d.seconds * 10) / 10 } } : {}),
      })
    } catch {
      // The report simply has no non-verbal section; the interview itself must never fail because of it.
    }
  }

  const finish = async () => {
    if (busy.current) return
    busy.current = true
    const before: Phase = phase === 'finishing' || phase === 'loading' ? 'answered' : phase
    setError(null)
    setConfirmFinish(false)
    setPhase('finishing')
    try {
      await sendObservations()
      await completeInterview(id)
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['history'] })
      navigate(`/interviews/${id}/results`, { replace: true })
    } catch (e) {
      const err = toApiError(e)
      if (err.status === 401) return
      const fresh = err.outcomeUnknown || err.status === 409 ? await recheck() : null
      if (fresh === 'completed') return
      setPhase(fresh ? (fresh.detail.introduction_pending ? 'introduction' : fresh.detail.pending_follow_up ? 'follow_up' : answeredNow(fresh.detail) ? 'answered' : 'answering') : before)
      setError(
        err.status === 409
          ? `${err.message}. Answer at least one question before finishing, or leave and come back later.`
          : `${err.message} Your interview is safe — try finishing again.`,
      )
    } finally {
      busy.current = false
    }
  }

  const goNext = async () => {
    if (busy.current) return
    busy.current = true
    setAdvancing(true)
    setError(null)
    try {
      const res = await nextQuestion(id)
      if (res.finished || !res.question) { busy.current = false; setAdvancing(false); await finish(); return }
      speech.stop()
      setQuestion(res.question)
      setQuestionNumber(res.question_number)
      setTotal(res.total_questions)
      setAnswer('')
      setFollowUpAnswer('')
      setFollowUpText(null)
      setAck(null)
      uncertain.current = false
      questionShownAt.current = Date.now()
      setHasNext(res.question_number < res.total_questions)
      setPhase('answering')
      void refreshConversation()
    } catch (e) {
      const err = toApiError(e)
      if (err.status === 401) return
      if (err.status === 409) {
        // e.g. a follow-up is still pending: resynchronise with the server.
        await load()
        setError(err.message)
      } else setError(err.message)
    } finally {
      busy.current = false
      setAdvancing(false)
    }
  }

  // ---- render ---------------------------------------------------------------------------------------------------------
  if (!Number.isFinite(id)) return <Navigate to="/history" replace />
  if (loadError) {
    const notFound = loadError.status === 404
    return (
      <Card>
        <ErrorState
          title={notFound ? 'Interview not found' : "We couldn't open this interview"}
          message={notFound ? 'It may have been removed, or it belongs to another account.' : loadError.message}
          onRetry={notFound ? undefined : () => void load()}
        />
        <div className="pb-6 text-center"><Link to="/history" className="text-sm font-medium">Back to interview history</Link></div>
      </Card>
    )
  }
  if (phase === 'loading' || !interview || !question) {
    return <div className="space-y-4" aria-busy="true" aria-label="Loading interview"><Skeleton className="h-14" /><Skeleton className="h-52" /><Skeleton className="h-52" /></div>
  }

  const inIntro = phase === 'introduction' || phase === 'submitting_introduction'
  const answeredCurrent = phase === 'answered' || phase === 'follow_up' || phase === 'submitting_follow_up'
  const completedCount = inIntro ? 0 : questionNumber - 1 + (answeredCurrent ? 1 : 0)
  const diffTone = difficultyTone[question.difficulty as keyof typeof difficultyTone] ?? 'neutral'
  const lastAnswered = answeredCurrent && !hasNext && phase === 'answered'

  // What the avatar is (or would be) saying right now.
  const currentPrompt = inIntro && introPrompt ? `${introPrompt.greeting} ${introPrompt.question}` : followUpText && (phase === 'follow_up' || phase === 'submitting_follow_up') ? followUpText : question.text
  const avatarState: AvatarState = speech.speaking
    ? 'speaking'
    : phase === 'introduction' || phase === 'answering' || phase === 'follow_up'
      ? 'listening'
      : waiting
        ? 'waiting'
        : 'idle'
  const agents = deriveAgents({ phase, speaking: speech.speaking, dictating: false, trace, info: agentInfo.data })

  return (
    <div className="grid gap-6 animate-in lg:grid-cols-[minmax(0,1fr)_21rem]">
      <div className="min-w-0 space-y-5">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">{interview.subject}</Badge>
              {!inIntro && <Badge tone="neutral">{question.topic}</Badge>}
              {!inIntro && <Badge tone={diffTone}>{titleCase(question.difficulty)}</Badge>}
              {interview.mode === 'practice' && <Badge tone="primary">Practice</Badge>}
            </div>
            <InterviewTimer startedAt={interview.started_at} durationMinutes={interview.duration_minutes} />
          </div>
          <div>
            <div className="mb-1.5 flex items-center justify-between text-sm">
              <span className="font-medium text-ink">{inIntro ? `Introduction · then ${total} questions` : `Question ${questionNumber} of ${total}`}</span>
              <span className="text-muted tabular">{completedCount} answered</span>
            </div>
            <ProgressBar value={completedCount} max={Math.max(total, 1)} label={`Interview progress: ${completedCount} of ${total} questions answered`} />
          </div>
        </div>

        <Card>
          <CardBody className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">{inIntro ? 'Introduction' : 'Interview question'}</p>
            {inIntro && introPrompt ? (
              <>
                <p className="text-sm text-muted" data-testid="intro-greeting">{introPrompt.greeting}</p>
                <h1 className="text-xl font-semibold leading-snug sm:text-[1.375rem]" data-testid="question-text">{introPrompt.question}</h1>
              </>
            ) : (
              <h1 className="text-xl font-semibold leading-snug sm:text-[1.375rem]" data-testid="question-text">{question.text}</h1>
            )}
          </CardBody>
        </Card>

        {error && (
          <Alert tone="danger" live="alert" title="That didn't go through">
            {error}
          </Alert>
        )}

        {inIntro && (
          <Card>
            <CardBody className="space-y-4">
              <AnswerComposer
                label="Your introduction"
                textareaRef={introRef}
                value={introAnswer}
                onChange={setIntroAnswer}
                onSubmit={() => void onSubmitIntroduction()}
                submitLabel={phase === 'submitting_introduction' ? 'Submitting…' : 'Continue to questions'}
                disabled={phase === 'submitting_introduction'}
                placeholder="Tell the panel about your background, studies and why you want to join the civil service."
                onDictation={onDictation}
              />
              <p className="text-xs text-muted">Your introduction gives the panel context. It is not scored.</p>
            </CardBody>
          </Card>
        )}

        {(phase === 'answering' || phase === 'submitting') && (
          <Card>
            <CardBody className="space-y-4">
              <AnswerComposer
                label="Your answer"
                textareaRef={answerRef}
                value={answer}
                onChange={setAnswer}
                onSubmit={() => void onSubmitAnswer()}
                submitLabel={phase === 'submitting' ? 'Submitting…' : 'Submit answer'}
                disabled={phase === 'submitting'}
                onDictation={onDictation}
              />
              {phase === 'submitting' && <EvaluatingPanel title="Evaluating your answer…" />}
            </CardBody>
          </Card>
        )}

        {(phase === 'follow_up' || phase === 'submitting_follow_up') && followUpText && (
          <Card className="border-primary/30">
            <CardBody className="space-y-4">
              <div className="flex items-start gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary-soft text-primary"><MessageCircleQuestion className="size-5" aria-hidden /></span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-primary">Follow-up to question {questionNumber}</p>
                  <p className="mt-1 text-lg font-semibold leading-snug" data-testid="follow-up-text">{followUpText}</p>
                  <p className="mt-1 text-sm text-muted">The panel would like you to expand on your answer. Reply to continue.</p>
                </div>
              </div>
              {ack && !ack.recovered && <AiNotice source={ack.source} notice={ack.notice} />}
              <AnswerComposer
                label="Your reply to the follow-up"
                textareaRef={followUpRef}
                value={followUpAnswer}
                onChange={setFollowUpAnswer}
                onSubmit={() => void onSubmitFollowUp()}
                submitLabel={phase === 'submitting_follow_up' ? 'Submitting…' : 'Submit reply'}
                disabled={phase === 'submitting_follow_up'}
                placeholder="Type your reply to the follow-up question."
                onDictation={onDictation}
              />
              {phase === 'submitting_follow_up' && <EvaluatingPanel title="Evaluating your reply…" />}
            </CardBody>
          </Card>
        )}

        {phase === 'answered' && (
          <Card>
            <CardBody className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="inline-flex items-center gap-2 text-base font-semibold text-success"><CheckCircle2 className="size-5" aria-hidden />Answer submitted</span>
                {ack?.source && <EvaluationSourceBadge source={ack.source} />}
              </div>
              {ack && <AiNotice source={ack.source} notice={ack.notice} unknown={ack.recovered} />}
              <p className="text-sm text-muted">Scores and detailed feedback are shown in your report after you finish — they are not revealed during the interview.</p>
              <div className="flex flex-wrap justify-end gap-3">
                {hasNext ? (
                  <Button size="lg" onClick={() => void goNext()} loading={advancing} icon={<ArrowRight className="size-4" aria-hidden />}>
                    Next question
                  </Button>
                ) : (
                  <Button size="lg" onClick={() => void finish()} icon={<Flag className="size-4" aria-hidden />}>
                    Finish and view report
                  </Button>
                )}
              </div>
            </CardBody>
          </Card>
        )}

        {phase === 'finishing' && <EvaluatingPanel title="Preparing your report…" />}

        {phase !== 'finishing' && !lastAnswered && (
          <div className="flex flex-col items-start gap-3 border-t border-line pt-4 sm:flex-row sm:items-center sm:justify-between">
            {confirmFinish ? (
              <Alert
                tone="warning"
                title="Finish the interview now?"
                action={
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setConfirmFinish(false)}>Keep going</Button>
                    <Button size="sm" onClick={() => void finish()}>Finish</Button>
                  </div>
                }
                live="off"
              >
                Questions you have not answered will score 0. {completedCount === 0 && 'You must answer at least one question to get a report.'}
              </Alert>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setConfirmFinish(true)} disabled={waiting || advancing} icon={<Flag className="size-4" aria-hidden />}>
                Finish interview early
              </Button>
            )}
          </div>
        )}
      </div>

      <aside className="min-w-0 space-y-4" aria-label="Interview panel">
        <InterviewerAvatar
          state={avatarState}
          caption={currentPrompt}
          speechSupported={speech.supported}
          speaking={speech.speaking}
          onRepeat={() => speech.speak(currentPrompt)}
          onStop={speech.stop}
        />
        <AgentPanel views={agents} info={agentInfo.data} />
        <CameraPanel camera={camera} videoRef={videoRef} />
        <Conversation turns={conversation} />
      </aside>
    </div>
  )
}

function answeredNow(d: InterviewDetail): boolean {
  return d.answered_indexes.includes(d.interview.current_index)
}
