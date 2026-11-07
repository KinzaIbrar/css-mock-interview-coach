import { aiRequest, http } from './client'
import type {
  AgentInfo, AnswerAck, AnswerRequest, FollowUpAck, IntroductionAck, InterviewDetail, InterviewOut, NextResponse, ObservationsIn, Report,
  StartInterviewRequest, StartInterviewResponse,
} from './types'

export const startInterview = (body: StartInterviewRequest) =>
  http.post<StartInterviewResponse>('/interviews/start', body).then((r) => r.data)

export const getInterview = (id: number) => http.get<InterviewDetail>(`/interviews/${id}`).then((r) => r.data)

export const listHistory = (params: { limit?: number; offset?: number } = {}) =>
  http.get<InterviewOut[]>('/interviews/history', { params }).then((r) => r.data)

/** Gemini-backed: long timeout, and callers must NOT auto-retry (re-check state with getInterview first). */
export const submitAnswer = (body: AnswerRequest) =>
  http.post<AnswerAck>('/interviews/answer', body, aiRequest).then((r) => r.data)

export const submitFollowUp = (body: AnswerRequest) =>
  http.post<FollowUpAck>('/interviews/follow-up', body, aiRequest).then((r) => r.data)

export const nextQuestion = (interviewId: number) =>
  http.post<NextResponse>('/interviews/next', { interview_id: interviewId }).then((r) => r.data)

export const completeInterview = (interviewId: number) =>
  http.post<Report>('/interviews/complete', { interview_id: interviewId }, aiRequest).then((r) => r.data)

export const submitIntroduction = (body: AnswerRequest) =>
  http.post<IntroductionAck>('/interviews/introduction', body).then((r) => r.data)

/** Aggregate camera/voice numbers only (never video, frames or landmarks). */
export const saveObservations = (body: ObservationsIn) =>
  http.post<{ interview_id: number; saved: boolean }>('/interviews/observations', body).then((r) => r.data)

export const listAgents = () => http.get<AgentInfo[]>('/agents').then((r) => r.data)
