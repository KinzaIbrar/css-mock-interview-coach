import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/api/interviews'
import * as content from '@/api/content'
import type { AgentInfo, NonVerbalReport, Report } from '@/api/types'
import { AgentPanel } from '@/components/agents/AgentPanel'
import { InterviewerAvatar } from '@/components/avatar/InterviewerAvatar'
import { CameraPanel } from '@/components/camera/CameraPanel'
import { CoachingCard, NonVerbalCard } from '@/components/evaluation/ReportExtras'
import type { CameraControls } from '@/hooks/useCamera'
import { deriveAgents } from '@/utils/agentStatus'
import { ObservationAggregator, analyseFrame, countWords, type Landmark } from '@/utils/poseMetrics'
import { deferred, detail, interviewOut, renderApp } from '@/test/utils'
import InterviewResults from './InterviewResults'
import InterviewRoom from './InterviewRoom'

vi.mock('@/api/interviews')
vi.mock('@/api/content')
const m = vi.mocked(api)
const c = vi.mocked(content)

// ---- pose metrics (pure rules) ---------------------------------------------------------------------------------
function person(over: Partial<Record<number, Partial<Landmark>>> = {}, shift = 0): Landmark[] {
  const l: Landmark[] = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0 }))
  const set = (i: number, x: number, y: number) => { l[i] = { x: x + shift, y, visibility: 0.99, ...over[i] } }
  set(0, 0.5, 0.3); set(7, 0.45, 0.3); set(8, 0.55, 0.3); set(11, 0.4, 0.6); set(12, 0.6, 0.6)
  return l
}

describe('pose metrics', () => {
  it('detects a visible, camera-facing person', () => {
    const f = analyseFrame(person())
    expect(f.faceVisible).toBe(true)
    expect(f.facing).toBe(true)
    expect(f.shoulder?.width).toBeCloseTo(0.2)
    expect(f.quality).toBe(1)
  })
  it('treats a turned head (nose far from the ear midpoint) as not facing', () => {
    expect(analyseFrame(person({ 0: { x: 0.64 } })).facing).toBe(false)
  })
  it('reports nothing when nobody is detected', () => {
    const f = analyseFrame(null)
    expect(f).toEqual({ faceVisible: false, facing: null, shoulder: null, quality: 0 })
  })
  it('summarises a steady person as stable with low movement', () => {
    const agg = new ObservationAggregator()
    for (let i = 0; i < 100; i++) agg.add({ t: i * 0.2, landmarks: person() })
    const r = agg.finish(20)
    expect(r.posture_stability).toBe('stable')
    expect(r.movement_level).toBe('low')
    expect(r.face_visible_pct).toBe(100)
    expect(r.facing_camera_pct).toBe(100)
    expect(r.analysed_seconds).toBeGreaterThan(15)
    expect(r.samples).toBe(100)
  })
  it('flags a swaying person as variable/high movement', () => {
    const agg = new ObservationAggregator()
    for (let i = 0; i < 100; i++) agg.add({ t: i * 0.2, landmarks: person({}, i % 2 ? 0.1 : -0.1) })
    const r = agg.finish(20)
    expect(r.posture_stability).toBe('variable')
    expect(r.movement_level).toBe('high')
  })
  it('gives low tracking quality (and no shoulder metrics) when landmarks are unreliable', () => {
    const agg = new ObservationAggregator()
    for (let i = 0; i < 40; i++) agg.add({ t: i * 0.2, landmarks: null })
    const r = agg.finish(8)
    expect(r.tracking_quality_pct).toBe(0)
    expect(r.posture_stability).toBeUndefined()
    expect(r.analysed_seconds).toBe(0)
  })
  it('counts dictated words', () => {
    expect(countWords('  the quick  brown fox ')).toBe(4)
    expect(countWords('   ')).toBe(0)
  })
  it('keeps only counters: the aggregate has no frame data', () => {
    const agg = new ObservationAggregator()
    agg.add({ t: 0.2, landmarks: person() })
    expect(Object.keys(agg.finish(1)).sort()).toEqual(
      ['analysed_seconds', 'enabled', 'face_visible_pct', 'facing_camera_pct', 'movement_level', 'posture_stability', 'samples', 'total_seconds', 'tracking_quality_pct'].sort(),
    )
  })
})

// ---- agent status derivation ----------------------------------------------------------------------------------
const evaluatorInfo = (available: boolean): AgentInfo[] => [
  { key: 'evaluator', name: 'Evaluator Agent', description: 'x', uses_llm: true, implemented_by: [], available, unavailable_reason: available ? null : 'Gemini is paused: quota_exhausted' },
]
const status = (views: ReturnType<typeof deriveAgents>, key: string) => views.find((v) => v.key === key)!.status

describe('agent status', () => {
  const base = { speaking: false, dictating: false, trace: [], info: undefined }
  it('shows the evaluator evaluating only while a request is in flight', () => {
    expect(status(deriveAgents({ ...base, phase: 'submitting' }), 'evaluator')).toBe('Evaluating')
    expect(status(deriveAgents({ ...base, phase: 'answering' }), 'evaluator')).toBe('Waiting')
  })
  it('shows the interviewer speaking / listening from real signals', () => {
    expect(status(deriveAgents({ ...base, phase: 'answering', speaking: true }), 'interviewer')).toBe('Speaking')
    expect(status(deriveAgents({ ...base, phase: 'answering' }), 'interviewer')).toBe('Listening')
  })
  it('shows coaching only while finishing / after completion', () => {
    expect(status(deriveAgents({ ...base, phase: 'finishing' }), 'coaching')).toBe('Coaching')
    expect(status(deriveAgents({ ...base, phase: 'answering' }), 'coaching')).toBe('Waiting')
    expect(status(deriveAgents({ ...base, phase: 'completed' }), 'coaching')).toBe('Completed')
  })
  it('reports an Error when the backend trace says the evaluator fell back', () => {
    const trace = [{ agent: 'evaluator' as const, status: 'error' as const, detail: 'Answer evaluated by the development heuristic (Gemini unavailable)', source: 'dev_heuristic' }]
    expect(status(deriveAgents({ ...base, phase: 'answered', trace }), 'evaluator')).toBe('Error')
  })
  it('explains an unavailable evaluator before any answer', () => {
    const v = deriveAgents({ ...base, phase: 'answering', info: evaluatorInfo(false) }).find((a) => a.key === 'evaluator')!
    expect(v.detail).toContain('quota_exhausted')
  })
})

describe('AgentPanel', () => {
  it('renders the four named agents with heading, description and a status', () => {
    render(<AgentPanel views={deriveAgents({ phase: 'answering', speaking: false, dictating: false, trace: [], info: undefined })} />)
    for (const name of ['Interviewer Agent', 'Evaluator Agent', 'Coaching Agent', 'Orchestration Agent']) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument()
    }
    expect(screen.getByTestId('agent-interviewer-status')).toHaveTextContent('Listening')
  })
})

// ---- avatar --------------------------------------------------------------------------------------------------
describe('InterviewerAvatar', () => {
  it('falls back to a flat avatar when WebGL is unavailable and says so', () => {
    render(<InterviewerAvatar state="idle" caption="Tell me about yourself" speechSupported speaking={false} onRepeat={() => {}} />)
    expect(screen.getByTestId('avatar-fallback')).toBeInTheDocument()
    expect(screen.getByText(/WebGL not supported/i)).toBeInTheDocument()
    expect(screen.getByTestId('avatar-caption')).toHaveTextContent('Tell me about yourself')
  })
  it('offers repeat when idle and stop while speaking', async () => {
    const onRepeat = vi.fn(); const onStop = vi.fn()
    const { rerender } = render(<InterviewerAvatar state="idle" speechSupported speaking={false} onRepeat={onRepeat} onStop={onStop} />)
    await userEvent.click(screen.getByRole('button', { name: /repeat question/i }))
    expect(onRepeat).toHaveBeenCalled()
    rerender(<InterviewerAvatar state="speaking" speechSupported speaking onRepeat={onRepeat} onStop={onStop} />)
    await userEvent.click(screen.getByRole('button', { name: /stop speaking/i }))
    expect(onStop).toHaveBeenCalled()
    expect(screen.getByText(/Interviewer · Speaking/)).toBeInTheDocument()
  })
  it('explains when speech is not supported', () => {
    render(<InterviewerAvatar state="idle" speechSupported={false} speaking={false} />)
    expect(screen.getByText(/aren't supported in this browser/i)).toBeInTheDocument()
  })
})

// ---- camera panel ---------------------------------------------------------------------------------------------
const cam = (over: Partial<CameraControls> = {}): CameraControls => ({
  status: 'off', tracking: 'idle', message: null, start: vi.fn().mockResolvedValue(undefined), stop: vi.fn(), collect: () => null, ...over,
})

describe('CameraPanel', () => {
  it('asks for explicit consent and explains privacy before anything is requested', async () => {
    const camera = cam()
    render(<CameraPanel camera={camera} videoRef={createRef()} />)
    const consent = screen.getByTestId('camera-consent')
    expect(consent).toHaveTextContent(/on your device only/i)
    expect(consent).toHaveTextContent(/never uploaded or stored/i)
    expect(consent).toHaveTextContent(/not.*judge emotions, confidence or honesty/i)
    expect(camera.start).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /turn on camera/i }))
    expect(camera.start).toHaveBeenCalledTimes(1)
  })
  it('shows an on indicator and a way to turn it off', async () => {
    const camera = cam({ status: 'on', tracking: 'tracking' })
    render(<CameraPanel camera={camera} videoRef={createRef()} />)
    expect(screen.getByText('Camera on')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /turn off camera/i }))
    expect(camera.stop).toHaveBeenCalled()
  })
  it('explains a denied permission and lets the user retry', () => {
    render(<CameraPanel camera={cam({ status: 'denied', message: 'Camera permission was denied. You can continue without it.' })} videoRef={createRef()} />)
    expect(screen.getByRole('alert')).toHaveTextContent(/denied/i)
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})

// ---- room: introduction, conversation, agents --------------------------------------------------------------------
describe('InterviewRoom (conversational)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    m.listAgents.mockResolvedValue([])
  })
  const intro = { greeting: 'Welcome to your mock interview.', question: 'Please tell me about yourself.' }

  it('starts with the introduction, hides question 1 until it is answered, then moves to Question 1', async () => {
    const turns = [
      { role: 'interviewer' as const, kind: 'greeting' as const, text: intro.greeting, question_number: null },
      { role: 'interviewer' as const, kind: 'introduction_question' as const, text: intro.question, question_number: null },
    ]
    m.getInterview.mockResolvedValue(detail({ introduction_pending: true, introduction_prompt: intro, conversation: turns }))
    const sent = deferred<{ interview_id: number; introduction_saved: boolean; trace: [] }>()
    m.submitIntroduction.mockReturnValue(sent.promise)
    renderApp(<InterviewRoom />, { route: '/interviews/1', path: '/interviews/:id' })

    expect(await screen.findByText('Please tell me about yourself.', { selector: 'h1' })).toBeInTheDocument()
    expect(screen.queryByText('What are the parts of speech?', { selector: 'h1' })).not.toBeInTheDocument()
    expect(screen.getByTestId('conversation')).toHaveTextContent('Welcome to your mock interview.')

    await userEvent.type(screen.getByLabelText('Your introduction'), 'I am a graduate in English literature.')
    await userEvent.click(screen.getByRole('button', { name: /continue to questions/i }))
    expect(m.submitIntroduction).toHaveBeenCalledWith(expect.objectContaining({ interview_id: 1, answer_text: 'I am a graduate in English literature.' }))
    sent.resolve({ interview_id: 1, introduction_saved: true, trace: [] })
    expect(await screen.findByLabelText('Your answer')).toBeInTheDocument()
    expect(screen.getByTestId('question-text')).toHaveTextContent('What are the parts of speech?')
  })

  it('does not send the introduction twice on a double click', async () => {
    m.getInterview.mockResolvedValue(detail({ introduction_pending: true, introduction_prompt: intro }))
    m.submitIntroduction.mockReturnValue(new Promise(() => {}))
    renderApp(<InterviewRoom />, { route: '/interviews/1', path: '/interviews/:id' })
    await userEvent.type(await screen.findByLabelText('Your introduction'), 'Hello there.')
    const btn = screen.getByRole('button', { name: /continue to questions/i })
    await userEvent.dblClick(btn)
    expect(m.submitIntroduction).toHaveBeenCalledTimes(1)
  })

  it('resumes mid-interview with the full conversation and follow-ups labelled, not counted as questions', async () => {
    m.getInterview.mockResolvedValue(
      detail({
        interview: interviewOut({ current_index: 1 }), question_number: 2, answered_indexes: [0], main_questions_answered: 1,
        conversation: [
          { role: 'interviewer', kind: 'question', text: 'Q1 text', question_number: 1 },
          { role: 'candidate', kind: 'answer', text: 'A1 text', question_number: 1 },
          { role: 'interviewer', kind: 'follow_up', text: 'Why is that?', question_number: 1 },
          { role: 'candidate', kind: 'follow_up_answer', text: 'Because.', question_number: 1 },
          { role: 'interviewer', kind: 'question', text: 'Q2 text', question_number: 2 },
        ],
      }),
    )
    renderApp(<InterviewRoom />, { route: '/interviews/1', path: '/interviews/:id' })
    await screen.findByTestId('question-text')
    const convo = screen.getByTestId('conversation')
    expect(convo).toHaveTextContent('Question 1')
    expect(convo).toHaveTextContent('Question 2')
    expect(convo).toHaveTextContent('Interviewer · follow-up')
    expect(convo).toHaveTextContent('You · follow-up reply')
    expect(screen.getByText('Question 2 of 3')).toBeInTheDocument()
  })

  it('shows the four agents and the evaluator "Evaluating" only while the answer is being evaluated', async () => {
    m.getInterview.mockResolvedValue(detail())
    const inflight = deferred<never>()
    m.submitAnswer.mockReturnValue(inflight.promise)
    renderApp(<InterviewRoom />, { route: '/interviews/1', path: '/interviews/:id' })
    await screen.findByTestId('question-text')
    expect(screen.getByTestId('agent-evaluator-status')).toHaveTextContent('Waiting')
    await userEvent.type(screen.getByLabelText('Your answer'), 'An answer.')
    await userEvent.click(screen.getByRole('button', { name: /submit answer/i }))
    await waitFor(() => expect(screen.getByTestId('agent-evaluator-status')).toHaveTextContent('Evaluating'))
  })

  it('labels a heuristic fallback as an evaluator Error from the backend trace', async () => {
    m.getInterview.mockResolvedValue(detail())
    m.submitAnswer.mockResolvedValue({
      interview_id: 1, answered_index: 0, answered_count: 1, has_next: true, evaluation_saved: true, evaluation_source: 'dev_heuristic',
      is_ai_generated: false, follow_up_question: null, ai_notice: 'Gemini is not configured', fallback_reason: 'not_configured',
      trace: [{ agent: 'evaluator', status: 'error', detail: 'Answer evaluated by the development heuristic (Gemini unavailable)', source: 'dev_heuristic' }],
    })
    renderApp(<InterviewRoom />, { route: '/interviews/1', path: '/interviews/:id' })
    await userEvent.type(await screen.findByLabelText('Your answer'), 'An answer.')
    await userEvent.click(screen.getByRole('button', { name: /submit answer/i }))
    await waitFor(() => expect(screen.getByTestId('agent-evaluator-status')).toHaveTextContent('Error'))
  })
})

// ---- report sections ---------------------------------------------------------------------------------------------
const nv: NonVerbalReport = {
  camera_used: true, voice_used: false, observation_coverage_pct: 88, tracking_quality_pct: 91,
  metrics: [
    { key: 'face_visible', label: 'Face visible', available: true, value: '95% of the time', note: null },
    { key: 'movement', label: 'Movement level', available: false, value: null, note: 'Not enough data' },
  ],
  unavailable: ['Movement level'], limitations: ['These are rough, observable indicators.'], rules: ['No emotion, confidence, honesty or personality is inferred.'],
}

describe('report extras', () => {
  it('shows non-verbal observations with Not enough data, limitations and no combined score', () => {
    render(<NonVerbalCard report={nv} />)
    expect(screen.getByText('95% of the time')).toBeInTheDocument()
    expect(screen.getByText('Not enough data')).toBeInTheDocument()
    expect(screen.getByText(/rough, observable indicators/)).toBeInTheDocument()
    expect(screen.getByText(/Separate from your verbal score/)).toBeInTheDocument()
    expect(screen.queryByText(/confidence score|personality score/i)).not.toBeInTheDocument()
  })
  it('labels the coaching plan as rule-based and lists weak topics and practice', () => {
    render(
      <CoachingCard
        coaching={{
          weak_topics: [{ topic: 'Grammar', score: 40, reason: 'Scored below 60/100 on this topic.' }], misunderstood_concepts: ['Tenses'],
          recurring_mistakes: [{ pattern: 'thin detail', count: 2 }],
          recommended_practice: [{ question_id: 5, question: 'Define a noun.', topic: 'Grammar', difficulty: 'easy' }], source: 'rule_based', is_ai_generated: false,
        }}
      />,
    )
    expect(screen.getByText(/rule-based, not AI/)).toBeInTheDocument()
    expect(screen.getByText('Define a noun.')).toBeInTheDocument()
    expect(screen.getByText('thin detail')).toBeInTheDocument()
  })
  it('renders the follow-up score on the results page separately from the overall score', async () => {
    const scores = { relevance: 8, subject_knowledge: 7, accuracy: 6, reasoning: 5, structure: 4, clarity: 9 }
    const report = {
      interview: interviewOut({ status: 'completed', completed_at: '2026-11-07T10:00:00', overall_score: 65 }), overall_score: 65, criteria_scores: scores,
      strengths: [], weaknesses: [], missing_info: [], summary: 's', improvements: [], revision_topics: [], next_practice: [],
      questions: [{
        order_index: 0, question_id: 1, question: 'Q?', topic: 'T', difficulty: 'easy', skipped: false, answer_text: 'A', scores, overall: 65,
        strengths: [], weaknesses: [], missing_info: [], model_answer: 'M', evaluation_source: 'gemini', is_ai_generated: true,
        follow_up_question: 'Why?', follow_up_answer: 'Because', follow_up_evaluation: { overall: 42, scores, strengths: [], weaknesses: ['Vague.'], missing_info: [], source: 'gemini', is_ai_generated: true, model: 'm' },
      }],
      evaluation_source: 'gemini', is_ai_generated: true, evaluation_model: 'm', notice: 'n', reference_notice: 'r', feedback_source: 'gemini',
      feedback_is_ai_generated: true, progress_note: null, introduction: 'Hi', follow_up_average: 42, coaching: null, observations: nv,
    } as Report
    c.getReport.mockResolvedValue(report)
    renderApp(<InterviewResults />, { route: '/interviews/1/results', path: '/interviews/:id/results' })
    expect(await screen.findByTestId('follow-up-average')).toHaveTextContent('42/100')
    expect(screen.getByTestId('follow-up-average')).toHaveTextContent(/not part of the overall score/i)
    expect(screen.getByText('Non-verbal observations')).toBeInTheDocument()
  })
})
