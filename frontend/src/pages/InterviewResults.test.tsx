import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import * as content from '@/api/content'
import type { QuestionResult, Report } from '@/api/types'
import { interviewOut, renderApp } from '@/test/utils'
import InterviewResults from './InterviewResults'

vi.mock('@/api/content')
const m = vi.mocked(content)

const scores = { relevance: 8, subject_knowledge: 7, accuracy: 6, reasoning: 5, structure: 4, clarity: 9 }
const answered = (over: Partial<QuestionResult> = {}): QuestionResult => ({
  order_index: 0, question_id: 1, question: 'Explain the Objectives Resolution.', topic: 'Constitutional History', difficulty: 'medium',
  skipped: false, answer_text: 'It was passed in 1949.', scores, overall: 65, strengths: ['Gives the date'], weaknesses: ['Thin detail'],
  missing_info: ['Article 2A'], model_answer: 'Passed by the first Constituent Assembly.', evaluation_source: 'gemini', is_ai_generated: true,
  follow_up_question: null, follow_up_answer: null, follow_up_evaluation: null, ...over,
})
const report = (over: Partial<Report> = {}): Report => ({
  interview: interviewOut({ status: 'completed', completed_at: '2026-11-07T10:00:00', overall_score: 65 }),
  overall_score: 65, criteria_scores: scores, strengths: ['Gives the date'], weaknesses: ['Thin detail'], missing_info: ['Article 2A'],
  summary: 'You covered the basics well.', improvements: ['Add an example to every answer'], revision_topics: ['Constitutional History'],
  next_practice: ['Revisit Constitutional History questions in English.'], questions: [answered()],
  evaluation_source: 'gemini', is_ai_generated: true, evaluation_model: 'gemini-3.8-flash',
  notice: 'AI-generated evaluation by gemini-3.8-flash. AI can make mistakes.', reference_notice: 'Sample question bank: unverified study aids.',
  feedback_source: 'gemini', feedback_is_ai_generated: true, progress_note: null,
  introduction: null, follow_up_average: null, coaching: null, observations: null, ...over,
})
const open = () => renderApp(<InterviewResults />, { route: '/interviews/1/results', path: '/interviews/:id/results' })

beforeEach(() => vi.resetAllMocks())

describe('InterviewResults', () => {
  it('shows the score, six criteria, feedback and sections from real report data', async () => {
    m.getReport.mockResolvedValue(report())
    open()
    expect(await screen.findByRole('heading', { name: 'English' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /overall score 65\.0 out of 100/i })).toBeInTheDocument()
    for (const label of ['Relevance', 'Subject knowledge', 'Accuracy', 'Reasoning', 'Structure', 'Clarity']) {
      expect(screen.getByRole('progressbar', { name: new RegExp(`^${label}: `) })).toBeInTheDocument()
    }
    expect(screen.getByText('You covered the basics well.')).toBeInTheDocument()
    expect(screen.getByText('Add an example to every answer')).toBeInTheDocument()
    expect(screen.getAllByText('Constitutional History').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Article 2A', { selector: 'li' }).length).toBeGreaterThan(0)
  })

  it('Gemini report: labelled as AI evaluation with the model name', async () => {
    m.getReport.mockResolvedValue(report())
    open()
    expect(await screen.findByText('Evaluated by AI (gemini-3.8-flash)')).toBeInTheDocument()
    expect(screen.getAllByText(/AI evaluation · gemini-3\.8-flash/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('AI feedback').length).toBeGreaterThan(0)
    expect(screen.queryByText(/not AI/i)).not.toBeInTheDocument()
  })

  it('fallback report: says plainly that it is a development evaluation, not AI', async () => {
    m.getReport.mockResolvedValue(report({
      evaluation_source: 'dev_heuristic', is_ai_generated: false, evaluation_model: null, feedback_source: 'dev_rules', feedback_is_ai_generated: false,
      notice: 'DEVELOPMENT MODE: this evaluation is produced by a simple keyword/length heuristic, NOT by an AI model.',
      questions: [answered({ evaluation_source: 'dev_heuristic', is_ai_generated: false })],
    }))
    open()
    expect(await screen.findByText('Development evaluation — not AI')).toBeInTheDocument()
    expect(screen.getByText(/NOT by an AI model/)).toBeInTheDocument()
    expect(screen.getAllByText(/Development evaluation · not AI/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Rule-based feedback · not AI/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/Evaluated by AI/)).not.toBeInTheDocument()
  })

  it('mixed report: warns that only part was AI-evaluated and labels each question', async () => {
    m.getReport.mockResolvedValue(report({
      evaluation_source: 'mixed', is_ai_generated: false,
      notice: 'Mixed evaluation: some answers were evaluated by gemini-3.8-flash; the others fell back to the development keyword heuristic (NOT AI).',
      questions: [
        answered({ question_id: 1, order_index: 0 }),
        answered({ question_id: 2, order_index: 1, question: 'Second question here?', evaluation_source: 'dev_heuristic', is_ai_generated: false }),
      ],
    }))
    open()
    expect(await screen.findByText('Partly AI-evaluated')).toBeInTheDocument()
    expect(screen.getAllByText('Partly AI').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/AI evaluation · Gemini/).length).toBe(1) // per-question badge for the AI one
    expect(screen.getAllByText(/Development evaluation · not AI/).length).toBe(1) // and for the fallback one
  })

  it('rule-based progress is never presented as AI', async () => {
    m.getReport.mockResolvedValue(report({ progress_note: 'Your English score is up 12 points from your previous session.' }))
    open()
    expect(await screen.findByText(/Progress · rule-based, not AI/)).toBeInTheDocument()
    expect(screen.getByText(/up 12 points/)).toBeInTheDocument()
  })

  it('skipped questions are clearly marked as scored 0 and have no fake scores', async () => {
    m.getReport.mockResolvedValue(report({
      questions: [answered(), answered({ question_id: 2, order_index: 1, question: 'Skipped one?', skipped: true, answer_text: null, scores: null, overall: null, evaluation_source: null, is_ai_generated: false, strengths: [], weaknesses: ['Question was skipped.'], missing_info: [] })],
    }))
    open()
    expect(await screen.findByText(/Skipped · scored 0/)).toBeInTheDocument()
    expect(screen.getByText('1 of 2 answered', { exact: false })).toBeInTheDocument()
  })

  it('expanding a question shows the answer, the follow-up exchange and the unverified reference answer', async () => {
    m.getReport.mockResolvedValue(report({
      questions: [answered({ follow_up_question: 'Which article?', follow_up_answer: 'Article 2A.' })],
    }))
    open()
    await userEvent.click(await screen.findByText('Explain the Objectives Resolution.'))
    expect(screen.getByText('It was passed in 1949.')).toBeInTheDocument()
    expect(screen.getByText('Which article?')).toBeInTheDocument()
    expect(screen.getByText('Article 2A.')).toBeInTheDocument()
    expect(screen.getByText('Reference answer (unverified sample)')).toBeInTheDocument()
    expect(screen.getByText('Passed by the first Constituent Assembly.')).toBeInTheDocument()
  })

  it('an unanswered follow-up is shown honestly', async () => {
    m.getReport.mockResolvedValue(report({ questions: [answered({ follow_up_question: 'Which article?', follow_up_answer: null })] }))
    open()
    await userEvent.click(await screen.findByText('Explain the Objectives Resolution.'))
    expect(screen.getByText('You did not answer the follow-up question.')).toBeInTheDocument()
  })

  it('409 (not finished) offers to resume; 404 is a clear not-found; other errors can retry', async () => {
    m.getReport.mockRejectedValueOnce(new ApiError('x', { kind: 'http', status: 409 }))
    open()
    expect(await screen.findByText('This interview is not finished yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Resume interview' })).toBeInTheDocument()
  })

  it('404 shows report not found', async () => {
    m.getReport.mockRejectedValue(new ApiError('x', { kind: 'http', status: 404 }))
    open()
    expect(await screen.findByText('Report not found')).toBeInTheDocument()
  })

  it('network failure offers a retry that reloads the report', async () => {
    m.getReport.mockRejectedValueOnce(new ApiError('Cannot reach the server.', { kind: 'network' })).mockResolvedValue(report())
    open()
    await userEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('You covered the basics well.')).toBeInTheDocument()
  })
})
