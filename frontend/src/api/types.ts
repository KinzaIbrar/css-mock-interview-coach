/** Types mirror the backend's actual Pydantic schemas (see docs/frontend-integration.md). */

export type Difficulty = 'easy' | 'medium' | 'hard'
export type InterviewDifficulty = Difficulty | 'mixed'
export type InterviewMode = 'mock' | 'practice'
export type InterviewStatus = 'in_progress' | 'completed'
/** Where an evaluation came from. The backend sends a string; these are the values it uses. */
export type EvaluationSource = 'gemini' | 'dev_heuristic' | 'mixed'
export type FeedbackSource = 'gemini' | 'dev_rules'

export const CRITERIA = ['relevance', 'subject_knowledge', 'accuracy', 'reasoning', 'structure', 'clarity'] as const
export type Criterion = (typeof CRITERIA)[number]

export interface User {
  id: number
  email: string
  full_name: string
  created_at: string
  preferences: Record<string, unknown>
}
export interface TokenResponse { access_token: string; token_type: string; user: User }
export interface RegisterRequest { email: string; password: string; full_name: string }
export interface LoginRequest { email: string; password: string }

export interface AiAvailability { available: boolean; reason: string | null; retry_after_seconds: number | null }
/** `ai_mode` says whether a key is configured; `ai_availability` says whether Gemini can be used right now. */
export interface Health { status: string; environment: string; ai_mode: string; ai_availability: AiAvailability | null }

export interface QuestionPublic { id: number; subject: string; topic: string; difficulty: string; text: string }
export interface QuestionOut extends QuestionPublic {
  reference_answer: string
  keywords: string[]
  evaluation_criteria: string[]
  tags: string[]
  explanation: string
  is_sample: boolean
  score: number | null
}
export interface QuestionList { items: QuestionOut[]; total: number; limit: number; offset: number; notice: string }
export interface TopicMeta { topic: string; count: number }
export interface SubjectMeta { subject: string; count: number; difficulties: Record<string, number>; topics: TopicMeta[] }
export interface QuestionMeta { total: number; subjects: SubjectMeta[]; tags: string[]; notice: string }
export interface QuestionQuery {
  subject?: string; topic?: string; difficulty?: string; tag?: string; search?: string; limit?: number; offset?: number
}

export interface InterviewOut {
  id: number
  subject: string
  difficulty: string
  num_questions: number
  duration_minutes: number
  mode: string
  status: InterviewStatus
  current_index: number
  answered_count: number
  started_at: string
  completed_at: string | null
  overall_score: number | null
}
export interface StartInterviewRequest {
  subject: string
  difficulty: InterviewDifficulty
  num_questions: number
  duration_minutes: number
  mode: InterviewMode
  topic?: string | null
  /** Conversational opening: greeting + "Tell me about yourself" before question 1. */
  with_introduction?: boolean
}
export interface IntroductionPrompt { greeting: string; question: string }
export interface StartInterviewResponse {
  interview: InterviewOut
  introduction_required: boolean
  introduction_prompt: IntroductionPrompt | null
  question: QuestionPublic
  question_number: number
  total_questions: number
  notice: string
}
export interface AnswerRequest { interview_id: number; answer_text: string; time_taken_seconds?: number | null }
export interface AnswerAck {
  interview_id: number
  answered_index: number
  answered_count: number
  has_next: boolean
  evaluation_saved: boolean
  evaluation_source: string
  is_ai_generated: boolean
  follow_up_question: string | null
  ai_notice: string | null
  fallback_reason: string | null
  trace: AgentStep[]
}
export interface FollowUpAck {
  interview_id: number
  answered_index: number
  has_next: boolean
  evaluation_source: string
  is_ai_generated: boolean
  ai_notice: string | null
  fallback_reason: string | null
  trace: AgentStep[]
}
export interface IntroductionAck { interview_id: number; introduction_saved: boolean; trace: AgentStep[] }
export interface NextResponse {
  interview_id: number
  finished: boolean
  question_number: number
  total_questions: number
  question: QuestionPublic | null
}
export interface InterviewDetail {
  interview: InterviewOut
  current_question: QuestionPublic | null
  question_number: number
  total_questions: number
  answered_indexes: number[]
  report_available: boolean
  pending_follow_up: string | null
  introduction_pending: boolean
  introduction_prompt: IntroductionPrompt | null
  conversation: ConversationTurn[]
  /** Follow-ups are NOT counted. */
  main_questions_answered: number
}

export type AgentKey = 'interviewer' | 'evaluator' | 'coaching' | 'orchestration'
export interface AgentStep { agent: AgentKey; status: 'completed' | 'waiting' | 'error'; detail: string; source: string | null }
export interface AgentInfo {
  key: AgentKey; name: string; description: string; uses_llm: boolean; implemented_by: string[]
  available: boolean; unavailable_reason: string | null
}
export type TurnKind = 'greeting' | 'introduction_question' | 'introduction' | 'question' | 'answer' | 'follow_up' | 'follow_up_answer'
export interface ConversationTurn { role: 'interviewer' | 'candidate'; kind: TurnKind; text: string; question_number: number | null }

/** Aggregate numbers computed in the browser. Raw video, frames and landmarks are never sent. */
export interface CameraAggregates {
  enabled: boolean; total_seconds: number; analysed_seconds: number; samples: number
  face_visible_pct?: number; facing_camera_pct?: number
  posture_stability?: 'stable' | 'moderate' | 'variable'; movement_level?: 'low' | 'moderate' | 'high'
  tracking_quality_pct?: number
}
export interface VoiceAggregates { dictated_words: number; dictated_seconds: number }
export interface ObservationsIn { interview_id: number; camera?: CameraAggregates; voice?: VoiceAggregates }
export interface Metric { key: string; label: string; available: boolean; value: string | null; note: string | null }
export interface NonVerbalReport {
  camera_used: boolean; voice_used: boolean
  observation_coverage_pct: number | null; tracking_quality_pct: number | null
  metrics: Metric[]; unavailable: string[]; limitations: string[]; rules: string[]
}
export interface FollowUpEvaluation {
  overall: number; scores: Record<string, number>; strengths: string[]; weaknesses: string[]; missing_info: string[]
  source: string; is_ai_generated: boolean; model: string | null
}
export interface Coaching {
  weak_topics: { topic: string; score: number; reason: string }[]
  misunderstood_concepts: string[]
  recurring_mistakes: { pattern: string; count: number }[]
  recommended_practice: { question_id: number; question: string; topic: string; difficulty: string }[]
  source: string; is_ai_generated: boolean
}

export interface QuestionResult {
  order_index: number
  question_id: number
  question: string
  topic: string
  difficulty: string
  skipped: boolean
  answer_text: string | null
  scores: Record<string, number> | null
  overall: number | null
  strengths: string[]
  weaknesses: string[]
  missing_info: string[]
  model_answer: string
  evaluation_source: string | null
  is_ai_generated: boolean
  follow_up_question: string | null
  follow_up_answer: string | null
  follow_up_evaluation: FollowUpEvaluation | null
}
export interface Report {
  interview: InterviewOut
  overall_score: number
  criteria_scores: Record<string, number>
  strengths: string[]
  weaknesses: string[]
  missing_info: string[]
  summary: string
  improvements: string[]
  revision_topics: string[]
  next_practice: string[]
  questions: QuestionResult[]
  evaluation_source: string
  is_ai_generated: boolean
  evaluation_model: string | null
  notice: string
  reference_notice: string
  feedback_source: string
  feedback_is_ai_generated: boolean
  progress_note: string | null
  introduction: string | null
  follow_up_average: number | null
  coaching: Coaching | null
  observations: NonVerbalReport | null
}

export interface SubjectPerformance {
  subject: string; sessions_count: number; avg_score: number; best_score: number; last_score: number
}
export interface TrendPoint { interview_id: number; subject: string; score: number; completed_at: string }
export interface Recommendation { title: string; detail: string; subject: string | null }
export interface Dashboard {
  total_interviews: number
  in_progress_count: number
  average_score: number | null
  best_score: number | null
  weakest_subject: string | null
  score_trend: TrendPoint[]
  subject_performance: SubjectPerformance[]
  recent_interviews: InterviewOut[]
  recommendations: Recommendation[]
  recommendations_source: string
  is_ai_generated: boolean
  notice: string
}
