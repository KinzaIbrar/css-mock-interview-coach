import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import * as api from '@/api/interviews'
import type { AnswerAck, FollowUpAck } from '@/api/types'
import { deferred, detail, interviewOut, question, renderApp } from '@/test/utils'
import InterviewRoom from './InterviewRoom'

vi.mock('@/api/interviews')
const m = vi.mocked(api)

const ack = (over: Partial<AnswerAck> = {}): AnswerAck => ({
  interview_id: 1, answered_index: 0, answered_count: 1, has_next: true, evaluation_saved: true,
  evaluation_source: 'gemini', is_ai_generated: true, follow_up_question: null, ai_notice: null, fallback_reason: null, trace: [], ...over,
})
const fuAck = (over: Partial<FollowUpAck> = {}): FollowUpAck => ({
  interview_id: 1, answered_index: 0, has_next: true, evaluation_source: 'gemini', is_ai_generated: true, ai_notice: null, fallback_reason: null, trace: [], ...over,
})
const http = (status: number, message = 'nope') => new ApiError(message, { kind: 'http', status })
const network = () => new ApiError('Cannot reach the server.', { kind: 'network' })

const open = async () => {
  renderApp(<InterviewRoom />, { route: '/interviews/1', path: '/interviews/:id' })
  await screen.findByTestId('question-text')
}
const answerBox = () => screen.getByLabelText('Your answer')
const typeAndSubmit = async (text = 'My considered answer to the question.') => {
  await userEvent.type(answerBox(), text)
  await userEvent.click(screen.getByRole('button', { name: /submit answer/i }))
}

beforeEach(() => {
  vi.resetAllMocks()
  m.getInterview.mockResolvedValue(detail())
  m.listAgents.mockResolvedValue([])
})

describe('InterviewRoom: basics', () => {
  it('shows the question, progress, timer and an empty answer box', async () => {
    await open()
    expect(screen.getByTestId('question-text')).toHaveTextContent('What are the parts of speech?')
    expect(screen.getByText('Question 1 of 3')).toBeInTheDocument()
    expect(screen.getByRole('timer')).toHaveTextContent(/left/)
    expect(screen.getByText(/0 \/ 8,000 characters/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /submit answer/i })).toBeDisabled()
  })

  it('counts characters and enables submit only for non-blank text', async () => {
    await open()
    await userEvent.type(answerBox(), '   ')
    expect(screen.getByRole('button', { name: /submit answer/i })).toBeDisabled()
    await userEvent.type(answerBox(), 'hello')
    expect(screen.getByText(/8 \/ 8,000 characters/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /submit answer/i })).toBeEnabled()
  })

  it('voice dictation is optional: unsupported browsers see a text-only message', async () => {
    await open()
    expect(screen.getByText(/voice dictation isn't supported in this browser/i)).toBeInTheDocument()
    expect(answerBox()).toBeEnabled() // typing still works
  })

  it('sends the interview id, trimmed answer and time taken', async () => {
    m.submitAnswer.mockResolvedValue(ack())
    await open()
    await typeAndSubmit('  trimmed answer  ')
    await screen.findByText('Answer submitted')
    expect(m.submitAnswer).toHaveBeenCalledWith(expect.objectContaining({ interview_id: 1, answer_text: 'trimmed answer' }))
  })

  it('resumes an interview whose current question is already answered', async () => {
    m.getInterview.mockResolvedValue(detail({ interview: interviewOut({ current_index: 0, answered_count: 1 }), answered_indexes: [0] }))
    await open()
    expect(await screen.findByText('Answer submitted')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next question/i })).toBeInTheDocument()
    expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument()
  })

  it('redirects to the report when the interview is already completed', async () => {
    m.getInterview.mockResolvedValue(detail({ interview: interviewOut({ status: 'completed' }), report_available: true, current_question: null }))
    renderApp(<InterviewRoom />, { route: '/interviews/1', path: '/interviews/:id' })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/interviews/1/results'))
  })

  it('shows a clear not-found state for an unknown interview', async () => {
    m.getInterview.mockRejectedValue(http(404))
    renderApp(<InterviewRoom />, { route: '/interviews/99', path: '/interviews/:id' })
    expect(await screen.findByText('Interview not found')).toBeInTheDocument()
  })
})

describe('InterviewRoom: answer + AI source labelling', () => {
  it('Gemini result: labelled as AI, no scores revealed mid-interview', async () => {
    m.submitAnswer.mockResolvedValue(ack())
    await open()
    await typeAndSubmit()
    expect(await screen.findByText('Answer submitted')).toBeInTheDocument()
    expect(screen.getByText(/AI evaluation/)).toBeInTheDocument()
    expect(screen.queryByText(/not evaluated by ai/i)).not.toBeInTheDocument()
    expect(screen.getByText(/not revealed during the interview/i)).toBeInTheDocument()
    expect(screen.queryByText(/\/ ?100/)).not.toBeInTheDocument()
  })

  it('fallback result: shows the ai_notice and a "not AI" badge', async () => {
    m.submitAnswer.mockResolvedValue(ack({
      evaluation_source: 'dev_heuristic', is_ai_generated: false, fallback_reason: 'http_503',
      ai_notice: 'Gemini was unavailable (http_503); this answer was evaluated by the development heuristic instead.',
    }))
    await open()
    await typeAndSubmit()
    expect(await screen.findByText('Not evaluated by AI')).toBeInTheDocument()
    expect(screen.getByText(/Gemini was unavailable \(http_503\)/)).toBeInTheDocument()
    expect(screen.getByText(/Development evaluation · not AI/)).toBeInTheDocument()
  })

  it('shows the evaluating state while the request is pending', async () => {
    const d = deferred<AnswerAck>()
    m.submitAnswer.mockReturnValue(d.promise)
    await open()
    await typeAndSubmit()
    expect(await screen.findByText('Evaluating your answer…')).toBeInTheDocument()
    expect(answerBox()).toBeDisabled()
    d.resolve(ack())
    expect(await screen.findByText('Answer submitted')).toBeInTheDocument()
  })

  it('cannot submit the same answer twice while a request is pending', async () => {
    const d = deferred<AnswerAck>()
    m.submitAnswer.mockReturnValue(d.promise)
    await open()
    await typeAndSubmit()
    await screen.findByText('Evaluating your answer…')
    const btn = screen.getByRole('button', { name: /submitting/i })
    expect(btn).toBeDisabled()
    await userEvent.click(btn)
    await userEvent.type(answerBox(), '{Control>}{Enter}{/Control}') // keyboard shortcut is blocked too
    expect(m.submitAnswer).toHaveBeenCalledTimes(1)
    d.resolve(ack())
    await screen.findByText('Answer submitted')
    expect(m.submitAnswer).toHaveBeenCalledTimes(1)
  })
})

describe('InterviewRoom: follow-up workflow', () => {
  it('asks the follow-up, blocks moving on, then continues after the reply', async () => {
    m.submitAnswer.mockResolvedValue(ack({ follow_up_question: 'Which article made it binding?' }))
    m.submitFollowUp.mockResolvedValue(fuAck())
    m.nextQuestion.mockResolvedValue({ interview_id: 1, finished: false, question_number: 2, total_questions: 3, question: question({ id: 11, text: 'Second question text?' }) })
    await open()
    await typeAndSubmit()

    expect(await screen.findByTestId('follow-up-text')).toHaveTextContent('Which article made it binding?')
    // while a follow-up is pending there is no way to advance
    expect(screen.queryByRole('button', { name: /next question/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /finish and view report/i })).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Your reply to the follow-up'), 'Article 2A.')
    await userEvent.click(screen.getByRole('button', { name: /submit reply/i }))
    expect(await screen.findByText('Answer submitted')).toBeInTheDocument()
    expect(m.submitFollowUp).toHaveBeenCalledWith(expect.objectContaining({ interview_id: 1, answer_text: 'Article 2A.' }))

    await userEvent.click(screen.getByRole('button', { name: /next question/i }))
    await waitFor(() => expect(screen.getByTestId('question-text')).toHaveTextContent('Second question text?'))
    expect(screen.getByText('Question 2 of 3')).toBeInTheDocument()
    expect(answerBox()).toHaveValue('') // fresh answer box for the new question
  })

  it('shows a pending follow-up straight away when resuming', async () => {
    m.getInterview.mockResolvedValue(detail({ interview: interviewOut({ answered_count: 1 }), answered_indexes: [0], pending_follow_up: 'Please elaborate on that.' }))
    await open()
    expect(await screen.findByTestId('follow-up-text')).toHaveTextContent('Please elaborate on that.')
    expect(screen.queryByRole('button', { name: /next question/i })).not.toBeInTheDocument()
  })

  it('a follow-up fallback notice is shown and does not block the interview', async () => {
    m.submitAnswer.mockResolvedValue(ack({ follow_up_question: 'Why?' }))
    m.submitFollowUp.mockResolvedValue(fuAck({ is_ai_generated: true, ai_notice: 'Gemini was unavailable (timeout) to re-evaluate your follow-up reply. Your reply was saved and the original AI evaluation of your answer was kept.' }))
    await open()
    await typeAndSubmit()
    await screen.findByTestId('follow-up-text')
    await userEvent.type(screen.getByLabelText('Your reply to the follow-up'), 'Because.')
    await userEvent.click(screen.getByRole('button', { name: /submit reply/i }))
    expect(await screen.findByText(/original AI evaluation of your answer was kept/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next question/i })).toBeInTheDocument()
  })

  it('HTTP 409 on /next (follow-up still pending) resynchronises instead of failing', async () => {
    m.getInterview
      .mockResolvedValueOnce(detail({ interview: interviewOut({ answered_count: 1 }), answered_indexes: [0] })) // load: answered, no follow-up known
      .mockResolvedValue(detail({ interview: interviewOut({ answered_count: 1 }), answered_indexes: [0], pending_follow_up: 'A follow-up appeared.' }))
    m.nextQuestion.mockRejectedValue(http(409, 'Answer the follow-up question before continuing'))
    await open()
    await userEvent.click(await screen.findByRole('button', { name: /next question/i }))
    expect(await screen.findByTestId('follow-up-text')).toHaveTextContent('A follow-up appeared.')
    expect(screen.getByText('Answer the follow-up question before continuing')).toBeInTheDocument()
  })

  it('follow-up reply is not double-submitted', async () => {
    const d = deferred<FollowUpAck>()
    m.submitAnswer.mockResolvedValue(ack({ follow_up_question: 'Why?' }))
    m.submitFollowUp.mockReturnValue(d.promise)
    await open()
    await typeAndSubmit()
    await screen.findByTestId('follow-up-text')
    await userEvent.type(screen.getByLabelText('Your reply to the follow-up'), 'Because.')
    await userEvent.click(screen.getByRole('button', { name: /submit reply/i }))
    await screen.findByText('Evaluating your reply…')
    await userEvent.click(screen.getByRole('button', { name: /submitting/i }))
    expect(m.submitFollowUp).toHaveBeenCalledTimes(1)
    d.resolve(fuAck())
    await screen.findByText('Answer submitted')
  })
})

describe('InterviewRoom: failures and safe retry', () => {
  it('HTTP 409 on submit: re-checks the server and reports the answer as saved', async () => {
    m.getInterview.mockResolvedValueOnce(detail()).mockResolvedValue(detail({ interview: interviewOut({ answered_count: 1 }), answered_indexes: [0] }))
    m.submitAnswer.mockRejectedValue(http(409, 'Current question already answered'))
    await open()
    await typeAndSubmit()
    expect(await screen.findByText('Your answer was saved')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /next question/i })).toBeInTheDocument()
    expect(m.submitAnswer).toHaveBeenCalledTimes(1)
  })

  it('a dropped connection where the answer was NOT saved keeps the text and allows a safe retry', async () => {
    m.submitAnswer.mockRejectedValueOnce(network()).mockResolvedValueOnce(ack())
    await open()
    await typeAndSubmit('Important long answer I do not want to lose.')
    expect(await screen.findByText(/your answer was not saved, so it is safe to try again/i)).toBeInTheDocument()
    expect(answerBox()).toHaveValue('Important long answer I do not want to lose.')
    await userEvent.click(screen.getByRole('button', { name: /submit answer/i }))
    expect(await screen.findByText('Answer submitted')).toBeInTheDocument()
    expect(m.submitAnswer).toHaveBeenCalledTimes(2)
  })

  it('a dropped connection where the answer WAS saved is recovered without re-sending', async () => {
    m.getInterview.mockResolvedValueOnce(detail()).mockResolvedValue(detail({ interview: interviewOut({ answered_count: 1 }), answered_indexes: [0] }))
    m.submitAnswer.mockRejectedValue(new ApiError('The server took too long to respond.', { kind: 'timeout' }))
    await open()
    await typeAndSubmit()
    expect(await screen.findByText('Your answer was saved')).toBeInTheDocument()
    expect(m.submitAnswer).toHaveBeenCalledTimes(1)
  })

  it('if the outcome cannot be confirmed, the next attempt checks first and never sends twice', async () => {
    m.getInterview
      .mockResolvedValueOnce(detail()) // initial load
      .mockRejectedValueOnce(network()) // re-check right after the failure: server unreachable
      .mockResolvedValue(detail({ interview: interviewOut({ answered_count: 1 }), answered_indexes: [0] })) // later: it was saved after all
    m.submitAnswer.mockRejectedValueOnce(network())
    await open()
    await typeAndSubmit()
    expect(await screen.findByText(/could not confirm whether your answer was saved/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /submit answer/i }))
    expect(await screen.findByText('Your answer was saved')).toBeInTheDocument()
    expect(m.submitAnswer).toHaveBeenCalledTimes(1) // never re-sent
  })

  it('validation errors (422) are shown and the text is kept', async () => {
    m.submitAnswer.mockRejectedValue(new ApiError('answer_text must not be blank', { kind: 'http', status: 422 }))
    await open()
    await typeAndSubmit()
    expect(await screen.findByText('answer_text must not be blank')).toBeInTheDocument()
    expect(answerBox()).toHaveValue('My considered answer to the question.')
  })
})

describe('InterviewRoom: finishing', () => {
  const lastQuestion = detail({
    interview: interviewOut({ current_index: 2, answered_count: 2 }), question_number: 3, total_questions: 3, answered_indexes: [0, 1],
  })

  it('after the last answer offers "Finish and view report" and navigates to the report', async () => {
    m.getInterview.mockResolvedValue(lastQuestion)
    m.submitAnswer.mockResolvedValue(ack({ has_next: false, answered_index: 2 }))
    m.completeInterview.mockResolvedValue({} as never)
    await open()
    await typeAndSubmit()
    await userEvent.click(await screen.findByRole('button', { name: /finish and view report/i }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/interviews/1/results'))
    expect(m.completeInterview).toHaveBeenCalledWith(1)
    expect(m.nextQuestion).not.toHaveBeenCalled()
  })

  it('finishing early asks for confirmation and warns that skipped questions score 0', async () => {
    m.completeInterview.mockResolvedValue({} as never)
    await open()
    await userEvent.click(screen.getByRole('button', { name: /finish interview early/i }))
    expect(screen.getByText('Finish the interview now?')).toBeInTheDocument()
    expect(screen.getByText(/will score 0/i)).toBeInTheDocument()
    expect(m.completeInterview).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /keep going/i }))
    expect(screen.queryByText('Finish the interview now?')).not.toBeInTheDocument()
  })

  it('finishing with no answers shows the backend limitation as a clear message', async () => {
    m.completeInterview.mockRejectedValue(http(409, 'Answer at least one question before completing the interview'))
    await open()
    await userEvent.click(screen.getByRole('button', { name: /finish interview early/i }))
    await userEvent.click(screen.getByRole('button', { name: /^finish$/i }))
    expect(await screen.findByText(/answer at least one question before completing the interview/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Your answer')).toBeInTheDocument() // back to answering
  })

  it('shows a loading state while the report is prepared', async () => {
    const d = deferred<never>()
    m.completeInterview.mockReturnValue(d.promise)
    await open()
    await userEvent.click(screen.getByRole('button', { name: /finish interview early/i }))
    await userEvent.click(screen.getByRole('button', { name: /^finish$/i }))
    expect(await screen.findByText('Preparing your report…')).toBeInTheDocument()
    d.resolve({} as never)
  })
})
