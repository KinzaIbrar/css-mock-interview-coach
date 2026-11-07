import { http } from './client'
import type { Dashboard, QuestionList, QuestionMeta, QuestionOut, QuestionQuery, Report } from './types'

export const getDashboard = () => http.get<Dashboard>('/dashboard').then((r) => r.data)
export const getReport = (interviewId: number) => http.get<Report>(`/reports/${interviewId}`).then((r) => r.data)

export const getQuestionMeta = () => http.get<QuestionMeta>('/questions/meta').then((r) => r.data)
export const listQuestions = (params: QuestionQuery) => {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
  return http.get<QuestionList>('/questions', { params: clean }).then((r) => r.data)
}
export const getQuestion = (id: number) => http.get<QuestionOut>(`/questions/${id}`).then((r) => r.data)
