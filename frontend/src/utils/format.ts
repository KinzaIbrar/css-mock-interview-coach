/** The backend stores UTC datetimes and serialises them without a timezone suffix. */
export function parseServerDate(value: string): Date {
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return parseServerDate(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return parseServerDate(value).toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

/** Scores are 0-10 throughout the app; default to 1 decimal place. */
export function formatScore(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** The 4 CSS-specific evaluation dimensions, each scored 0-10. */
export const CRITERIA_LABELS: Record<string, string> = {
  constitutional_understanding: 'Constitutional Understanding',
  analytical_depth: 'Analytical Depth',
  subject_expertise: 'Subject Expertise',
  policy_awareness: 'Policy Awareness',
}

/** One short line explaining what each dimension assesses, for the evaluation cards. */
export const CRITERIA_DESCRIPTIONS: Record<string, string> = {
  constitutional_understanding: 'Understanding and accurate application of constitutional provisions, legal frameworks and policy application.',
  analytical_depth: 'Reasoning, argument development, critical thinking and supporting evidence.',
  subject_expertise: 'Subject knowledge, factual accuracy and conceptual understanding.',
  policy_awareness: 'Current affairs, legislative developments, government policies and practical implications.',
}

/** Score band used for text labels, so meaning never depends on colour alone. Scores are 0-10. */
export function scoreBand(score: number): { label: string; tone: 'success' | 'primary' | 'warning' | 'danger' } {
  if (score >= 8.5) return { label: 'Excellent', tone: 'success' }
  if (score >= 7.5) return { label: 'Very Good', tone: 'success' }
  if (score >= 6) return { label: 'Good', tone: 'primary' }
  if (score >= 4) return { label: 'Needs Improvement', tone: 'warning' }
  return { label: 'Weak', tone: 'danger' }
}
