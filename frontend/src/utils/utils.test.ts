import { describe, expect, it } from 'vitest'
import type { SubjectMeta } from '@/api/types'
import { formatCountdown, formatScore, parseServerDate, scoreBand } from './format'
import { availableQuestions, interviewLink } from './interview'
import { loginSchema, registerSchema } from './schemas'
import { interviewOut } from '@/test/utils'

describe('format', () => {
  it('treats timezone-less server dates as UTC', () => {
    expect(parseServerDate('2026-11-07T02:00:00').toISOString()).toBe('2026-11-07T02:00:00.000Z')
    expect(parseServerDate('2026-11-07T02:00:00Z').toISOString()).toBe('2026-11-07T02:00:00.000Z')
    expect(parseServerDate('2026-11-07T07:00:00+05:00').toISOString()).toBe('2026-11-07T02:00:00.000Z')
  })
  it('formats countdowns and scores', () => {
    expect(formatCountdown(0)).toBe('00:00')
    expect(formatCountdown(65)).toBe('01:05')
    expect(formatCountdown(-5)).toBe('00:00')
    expect(formatScore(null)).toBe('—')
    expect(formatScore(72.46, 1)).toBe('72.5')
  })
  it('bands scores with a text label', () => {
    expect(scoreBand(90).label).toBe('Strong')
    expect(scoreBand(65).label).toBe('Good')
    expect(scoreBand(45).label).toBe('Developing')
    expect(scoreBand(10).label).toBe('Needs work')
  })
})

describe('schemas', () => {
  const ok = { full_name: 'Ayesha Khan', email: 'a@example.com', password: 'long-enough-pw', confirm: 'long-enough-pw' }
  it('accepts valid registration', () => expect(registerSchema.safeParse(ok).success).toBe(true))
  it('rejects mismatched passwords on the confirm field', () => {
    const r = registerSchema.safeParse({ ...ok, confirm: 'different-pw' })
    expect(r.success).toBe(false)
    expect(!r.success && r.error.issues[0].path).toEqual(['confirm'])
  })
  it('rejects short passwords and bad emails', () => {
    expect(registerSchema.safeParse({ ...ok, password: 'short', confirm: 'short' }).success).toBe(false)
    expect(registerSchema.safeParse({ ...ok, email: 'nope' }).success).toBe(false)
    expect(loginSchema.safeParse({ email: '', password: 'x' }).success).toBe(false)
  })
  it('counts password BYTES (bcrypt limit is 72), not characters', () => {
    const emoji = '😀'.repeat(19) // 19 chars but 76 bytes
    expect(emoji.length).toBeLessThan(72)
    expect(registerSchema.safeParse({ ...ok, password: emoji, confirm: emoji }).success).toBe(false)
  })
})

describe('interview helpers', () => {
  const subject: SubjectMeta = {
    subject: 'English', count: 16, difficulties: { easy: 5, medium: 7, hard: 4 },
    topics: [{ topic: 'Grammar', count: 6 }],
  }
  it('computes available questions per choice', () => {
    expect(availableQuestions(subject, '', 'mixed')).toBe(16)
    expect(availableQuestions(subject, '', 'hard')).toBe(4)
    expect(availableQuestions(subject, 'Grammar', 'mixed')).toBe(6)
    expect(availableQuestions(subject, 'Grammar', 'hard')).toBeNull() // unknown split: let the server decide
    expect(availableQuestions(undefined, '', 'mixed')).toBeNull()
  })
  it('links completed interviews to the report and unfinished ones to the room', () => {
    expect(interviewLink(interviewOut({ id: 7, status: 'completed' }))).toBe('/interviews/7/results')
    expect(interviewLink(interviewOut({ id: 7, status: 'in_progress' }))).toBe('/interviews/7')
  })
})
