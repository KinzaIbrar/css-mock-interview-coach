import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import * as content from '@/api/content'
import * as interviews from '@/api/interviews'
import * as authApi from '@/api/auth'
import type { Health, QuestionList, QuestionMeta } from '@/api/types'
import { AppShell } from '@/components/layout/AppShell'
import { useAuth } from '@/context/AuthContext'
import { describeAiStatus } from '@/utils/aiStatus'
import { deferred, interviewOut, renderApp } from '@/test/utils'
import InterviewSetup from './InterviewSetup'

vi.mock('@/api/content')
vi.mock('@/api/interviews')
vi.mock('@/api/auth')
vi.mock('@/context/AuthContext', () => ({ useAuth: vi.fn() }))
const c = vi.mocked(content)
const iv = vi.mocked(interviews)

const meta: QuestionMeta = {
  total: 16, tags: [], notice: 'Sample question bank.',
  subjects: [{ subject: 'English', count: 16, difficulties: { easy: 5, medium: 7, hard: 4 }, topics: [{ topic: 'Grammar', count: 6 }] }],
}
const listOf = (total: number): QuestionList => ({ items: [], total, limit: 1, offset: 0, notice: '' })

const started = () => ({ interview: interviewOut({ id: 9 }), question: { id: 1, subject: 'English', topic: 'Grammar', difficulty: 'hard', text: 'Q?' }, question_number: 1, total_questions: 1, notice: '', introduction_required: false, introduction_prompt: null })

beforeEach(() => {
  vi.resetAllMocks()
  c.getQuestionMeta.mockResolvedValue(meta)
  Element.prototype.scrollIntoView = vi.fn()
})

const open = async () => {
  renderApp(<InterviewSetup />, { route: '/interviews/new', path: '/interviews/new' })
  await screen.findByText('Interview settings')
}
const chooseTopicAndHard = async () => {
  await userEvent.selectOptions(screen.getByLabelText('Subject'), 'English')
  await userEvent.selectOptions(screen.getByLabelText('Topic (optional)'), 'Grammar')
  await userEvent.click(screen.getByText('Hard'))
}
const start = () => userEvent.click(screen.getByRole('button', { name: /start interview/i }))

describe('setup: no doomed requests (the cause of the repeated 400s)', () => {
  it('asks the server for the exact count when a topic AND a difficulty are chosen', async () => {
    c.listQuestions.mockResolvedValue(listOf(1))
    await open()
    await chooseTopicAndHard()
    await waitFor(() => expect(c.listQuestions).toHaveBeenCalledWith({ subject: 'English', topic: 'Grammar', difficulty: 'hard', limit: 1 }))
    expect(await screen.findByText('1 available for this choice (max 20).')).toBeInTheDocument()
  })

  it('does not ask for a count when the metadata already knows it', async () => {
    await open()
    await userEvent.selectOptions(screen.getByLabelText('Subject'), 'English')
    await userEvent.selectOptions(screen.getByLabelText('Topic (optional)'), 'Grammar') // topic + mixed: topic.count is known
    expect(await screen.findByText('6 available for this choice (max 20).')).toBeInTheDocument()
    expect(c.listQuestions).not.toHaveBeenCalled()
  })

  it('blocks a request the server would refuse, explains why, and sends nothing', async () => {
    c.listQuestions.mockResolvedValue(listOf(1))
    await open()
    await chooseTopicAndHard() // default is 5 questions
    await screen.findByText('1 available for this choice (max 20).')
    await start()
    expect(await screen.findByText(/only 1 question is available for this choice/i)).toBeInTheDocument()
    expect(iv.startInterview).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Number of questions')).toHaveFocus() // the user is taken to the field to fix
  })

  it('says so plainly when the combination has no questions at all', async () => {
    c.listQuestions.mockResolvedValue(listOf(0))
    await open()
    await chooseTopicAndHard()
    await screen.findByText('0 available for this choice (max 20).')
    await start()
    expect(await screen.findByText('No questions match this topic and difficulty. Choose another difficulty or topic.')).toBeInTheDocument()
    expect(iv.startInterview).not.toHaveBeenCalled()
  })

  it('starts once the count is lowered to what exists', async () => {
    c.listQuestions.mockResolvedValue(listOf(1))
    iv.startInterview.mockResolvedValue(started())
    await open()
    await chooseTopicAndHard()
    await screen.findByText('1 available for this choice (max 20).')
    const n = screen.getByLabelText('Number of questions')
    await userEvent.clear(n)
    await userEvent.type(n, '1')
    await start()
    await waitFor(() => expect(iv.startInterview).toHaveBeenCalledTimes(1))
    expect(iv.startInterview.mock.calls[0][0]).toMatchObject({ subject: 'English', topic: 'Grammar', difficulty: 'hard', num_questions: 1 })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/interviews/9'))
  })

  it('while the count is still loading it says so and does not block (the server decides)', async () => {
    const d = deferred<QuestionList>()
    c.listQuestions.mockReturnValue(d.promise)
    iv.startInterview.mockResolvedValue(started())
    await open()
    await chooseTopicAndHard()
    expect(await screen.findByText('Checking how many questions are available…')).toBeInTheDocument()
    const n = screen.getByLabelText('Number of questions')
    await userEvent.clear(n)
    await userEvent.type(n, '1')
    await start()
    await waitFor(() => expect(iv.startInterview).toHaveBeenCalledTimes(1))
    d.resolve(listOf(1))
  })
})

describe('setup: a refused request must be visible', () => {
  it('shows the server message next to the Start button, focused and scrolled into view', async () => {
    c.listQuestions.mockRejectedValue(new ApiError('count unavailable', { kind: 'network' })) // exact count could not be fetched
    iv.startInterview.mockRejectedValue(new ApiError('Only 1 question(s) available for English / Grammar (hard); requested 5. Reduce the number of questions or change the difficulty.', { kind: 'http', status: 400 }))
    await open()
    await chooseTopicAndHard()
    await start()
    const alert = await screen.findByText(/Only 1 question\(s\) available for English \/ Grammar \(hard\)/)
    expect(screen.getByText("We couldn't start this interview")).toBeInTheDocument()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    const wrapper = alert.closest('[tabindex="-1"]') as HTMLElement
    expect(wrapper).toHaveFocus()
    // it sits between the form fields and the button, not at the very top of the form
    const button = screen.getByRole('button', { name: /start interview/i })
    expect(wrapper.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByLabelText('Subject').compareDocumentPosition(wrapper) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('a double click sends exactly one request', async () => {
    const d = deferred<ReturnType<typeof started>>()
    iv.startInterview.mockReturnValue(d.promise)
    await open()
    await userEvent.selectOptions(screen.getByLabelText('Subject'), 'English')
    const btn = screen.getByRole('button', { name: /start interview/i })
    await userEvent.dblClick(btn)
    await waitFor(() => expect(screen.getByRole('button', { name: /preparing your interview/i })).toBeDisabled())
    await userEvent.click(screen.getByRole('button', { name: /preparing your interview/i }))
    expect(iv.startInterview).toHaveBeenCalledTimes(1)
    d.resolve(started())
  })
})

describe('honest AI status', () => {
  const health = (over: Partial<Health> = {}): Health => ({ status: 'ok', environment: 'development', ai_mode: 'gemini', ai_availability: { available: true, reason: null, retry_after_seconds: null }, ...over })

  it('distinguishes configured, quota exhausted, rate limited, paused and not configured', () => {
    expect(describeAiStatus(undefined)).toBeNull()
    expect(describeAiStatus(health())).toMatchObject({ headline: 'Gemini configured', degraded: false })
    expect(describeAiStatus(health({ ai_mode: 'development (no GEMINI_API_KEY)', ai_availability: null }))).toMatchObject({ headline: 'Development mode', degraded: true })
    const quota = describeAiStatus(health({ ai_availability: { available: false, reason: 'quota_exhausted', retry_after_seconds: 600 } }))
    expect(quota).toMatchObject({ headline: 'Gemini quota used up', degraded: true })
    expect(quota?.detail).toMatch(/daily request limit/i)
    expect(quota?.detail).toMatch(/not AI/)
    expect(quota?.detail).toMatch(/about 10 min/)
    expect(describeAiStatus(health({ ai_availability: { available: false, reason: 'rate_limited', retry_after_seconds: 30 } }))?.headline).toBe('Gemini is rate-limited')
    expect(describeAiStatus(health({ ai_availability: { available: false, reason: 'cooldown', retry_after_seconds: 20 } }))?.headline).toBe('Gemini temporarily unavailable')
  })

  it('the sidebar no longer says "Gemini configured" while the quota is exhausted', async () => {
    vi.mocked(useAuth).mockReturnValue({ user: { id: 1, email: 'a@example.com', full_name: 'Ayesha Khan', created_at: '2026-01-01T00:00:00', preferences: {} }, status: 'authenticated', signIn: vi.fn(), signUp: vi.fn(), signOut: vi.fn() })
    vi.mocked(authApi.getHealth).mockResolvedValue(health({ ai_availability: { available: false, reason: 'quota_exhausted', retry_after_seconds: 900 } }))
    renderApp(<AppShell />, { route: '/dashboard' })
    const box = await screen.findByTestId('ai-status')
    expect(box).toHaveTextContent('Gemini quota used up')
    expect(box).not.toHaveTextContent('Gemini configured')
  })
})
