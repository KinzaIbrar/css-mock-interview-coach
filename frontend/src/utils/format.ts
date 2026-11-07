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

export function formatScore(value: number | null | undefined, digits = 0): string {
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

export const CRITERIA_LABELS: Record<string, string> = {
  relevance: 'Relevance',
  subject_knowledge: 'Subject knowledge',
  accuracy: 'Accuracy',
  reasoning: 'Reasoning',
  structure: 'Structure',
  clarity: 'Clarity',
}

/** Score band used for text labels, so meaning never depends on colour alone. */
export function scoreBand(score: number): { label: string; tone: 'success' | 'primary' | 'warning' | 'danger' } {
  if (score >= 75) return { label: 'Strong', tone: 'success' }
  if (score >= 60) return { label: 'Good', tone: 'primary' }
  if (score >= 40) return { label: 'Developing', tone: 'warning' }
  return { label: 'Needs work', tone: 'danger' }
}
