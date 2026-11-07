import type { Health } from '@/api/types'

export interface AiStatusText {
  headline: string
  detail: string
  /** True when answers are (or will be) evaluated by the development heuristic instead of Gemini. */
  degraded: boolean
}

function minutes(seconds: number | null | undefined): string {
  if (!seconds || seconds < 60) return 'a minute'
  return `about ${Math.ceil(seconds / 60)} min`
}

/**
 * What the AI can do right now, in plain words. "Configured" (a key exists) is not "available": Google may be
 * overloaded, rate-limiting, or out of quota, and the user should be told instead of seeing a reassuring label.
 */
export function describeAiStatus(health: Health | undefined): AiStatusText | null {
  if (!health) return null
  if (health.ai_mode !== 'gemini') {
    return { headline: 'Development mode', detail: 'No AI key is set: answers use a keyword heuristic, not AI.', degraded: true }
  }
  const a = health.ai_availability
  if (a && !a.available) {
    const again = `We will try Gemini again in ${minutes(a.retry_after_seconds)}.`
    if (a.reason === 'quota_exhausted') {
      return { headline: 'Gemini quota used up', detail: `The API key's daily request limit has been reached. Answers use a labelled development evaluator (not AI). ${again}`, degraded: true }
    }
    if (a.reason === 'rate_limited') {
      return { headline: 'Gemini is rate-limited', detail: `Google is limiting requests. Answers use a labelled development evaluator (not AI) for now. ${again}`, degraded: true }
    }
    return { headline: 'Gemini temporarily unavailable', detail: `Answers use a labelled development evaluator (not AI) for now. ${again}`, degraded: true }
  }
  return { headline: 'Gemini configured', detail: 'If the AI service is busy, answers fall back to a labelled development evaluator.', degraded: false }
}
