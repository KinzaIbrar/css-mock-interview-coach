import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import type { InterviewDetail, InterviewOut, QuestionPublic } from '@/api/types'

function LocationProbe() {
  const loc = useLocation()
  return <div data-testid="location">{loc.pathname}</div>
}

/** Render with a fresh query cache (no retries) and a router; `path` lets components read route params. */
export function renderApp(ui: ReactElement, { route = '/', path = '*' }: { route?: string; path?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={path} element={ui} />
          <Route path="*" element={<div>other page</div>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

export const interviewOut = (over: Partial<InterviewOut> = {}): InterviewOut => ({
  id: 1, subject: 'English', difficulty: 'mixed', num_questions: 3, duration_minutes: 30, mode: 'mock', status: 'in_progress',
  current_index: 0, answered_count: 0, started_at: new Date().toISOString().replace('Z', ''), completed_at: null, overall_score: null, ...over,
})

export const question = (over: Partial<QuestionPublic> = {}): QuestionPublic => ({
  id: 10, subject: 'English', topic: 'Grammar', difficulty: 'easy', text: 'What are the parts of speech?', ...over,
})

export const detail = (over: Partial<InterviewDetail> = {}): InterviewDetail => ({
  interview: interviewOut(), current_question: question(), question_number: 1, total_questions: 3,
  answered_indexes: [], report_available: false, pending_follow_up: null,
  introduction_pending: false, introduction_prompt: null, conversation: [], main_questions_answered: 0, ...over,
})

/** A promise you resolve/reject by hand, to freeze a request "in flight". */
export function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}
