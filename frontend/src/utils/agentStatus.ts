import type { AgentInfo, AgentKey, AgentStep } from '@/api/types'

export type AgentStatus = 'Active' | 'Speaking' | 'Listening' | 'Evaluating' | 'Coaching' | 'Waiting' | 'Completed' | 'Error'

/** The room's real state machine; each agent's status is derived ONLY from it and from real backend results. */
export type RoomPhase =
  | 'loading' | 'introduction' | 'submitting_introduction' | 'answering' | 'submitting' | 'answered'
  | 'follow_up' | 'submitting_follow_up' | 'finishing' | 'completed'

export interface AgentView {
  key: AgentKey
  status: AgentStatus
  /** What the agent is doing / last did, in words. */
  detail: string
}

interface Inputs {
  phase: RoomPhase
  speaking: boolean
  dictating: boolean
  /** Steps reported by the backend for the most recent request. */
  trace: AgentStep[]
  info: AgentInfo[] | undefined
}

const lastStep = (trace: AgentStep[], agent: AgentKey) => trace.find((s) => s.agent === agent)

export function deriveAgents({ phase, speaking, dictating, trace, info }: Inputs): AgentView[] {
  const evalAvail = info?.find((a) => a.key === 'evaluator')
  const evalStep = lastStep(trace, 'evaluator')
  const evaluating = phase === 'submitting' || phase === 'submitting_follow_up'

  // Interviewer
  let interviewer: AgentView
  if (phase === 'loading') interviewer = { key: 'interviewer', status: 'Waiting', detail: 'Loading the interview' }
  else if (phase === 'completed') interviewer = { key: 'interviewer', status: 'Completed', detail: 'Interview finished' }
  else if (speaking) interviewer = { key: 'interviewer', status: 'Speaking', detail: 'Reading the question aloud' }
  else if (dictating) interviewer = { key: 'interviewer', status: 'Listening', detail: 'Listening to your spoken answer' }
  else if (phase === 'answering' || phase === 'introduction' || phase === 'follow_up')
    interviewer = { key: 'interviewer', status: 'Listening', detail: phase === 'follow_up' ? 'Waiting for your follow-up reply' : phase === 'introduction' ? 'Waiting for your introduction' : 'Waiting for your answer' }
  else if (evaluating || phase === 'submitting_introduction' || phase === 'finishing')
    interviewer = { key: 'interviewer', status: 'Waiting', detail: 'Waiting for the other agents' }
  else interviewer = { key: 'interviewer', status: 'Active', detail: 'Ready for the next question' }

  // Evaluator
  let evaluator: AgentView
  if (evaluating) evaluator = { key: 'evaluator', status: 'Evaluating', detail: phase === 'submitting_follow_up' ? 'Evaluating your follow-up reply' : 'Evaluating your answer' }
  else if (evalStep?.status === 'error') evaluator = { key: 'evaluator', status: 'Error', detail: evalStep.detail }
  else if (phase === 'completed') evaluator = { key: 'evaluator', status: 'Completed', detail: 'All answers evaluated' }
  else if (evalStep) evaluator = { key: 'evaluator', status: 'Completed', detail: evalStep.detail }
  else if (evalAvail && !evalAvail.available) evaluator = { key: 'evaluator', status: 'Waiting', detail: evalAvail.unavailable_reason ?? 'Gemini unavailable; heuristic fallback will be used' }
  else evaluator = { key: 'evaluator', status: 'Waiting', detail: 'Waiting for an answer' }

  // Coaching
  let coaching: AgentView
  if (phase === 'finishing') coaching = { key: 'coaching', status: 'Coaching', detail: 'Building your feedback and practice plan' }
  else if (phase === 'completed') coaching = { key: 'coaching', status: 'Completed', detail: 'Coaching plan ready in the report' }
  else coaching = { key: 'coaching', status: 'Waiting', detail: 'Starts after the interview ends' }

  // Orchestration
  let orchestration: AgentView
  if (evaluating || phase === 'finishing') orchestration = { key: 'orchestration', status: 'Active', detail: 'Running the LangGraph workflow' }
  else if (phase === 'completed') orchestration = { key: 'orchestration', status: 'Completed', detail: 'Workflow finished' }
  else if (lastStep(trace, 'orchestration')) orchestration = { key: 'orchestration', status: 'Completed', detail: lastStep(trace, 'orchestration')!.detail }
  else orchestration = { key: 'orchestration', status: 'Waiting', detail: 'Idle between steps' }

  return [interviewer, evaluator, coaching, orchestration]
}
