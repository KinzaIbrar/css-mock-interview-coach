import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { AxiosError } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AI_TIMEOUT_MS, ApiError, DEFAULT_TIMEOUT_MS, http, setUnauthorizedHandler, tokenStore, toApiError } from './client'
import { completeInterview, nextQuestion, submitAnswer, submitFollowUp } from './interviews'

function respond(status: number, data: unknown): AxiosAdapter {
  return (config: InternalAxiosRequestConfig) => {
    const res = { data, status, statusText: '', headers: {}, config } as AxiosResponse
    if (status >= 200 && status < 300) return Promise.resolve(res)
    return Promise.reject(new AxiosError('failed', 'ERR_BAD_REQUEST', config, null, res))
  }
}

afterEach(() => {
  tokenStore.clear()
  setUnauthorizedHandler(null)
  http.defaults.adapter = undefined
})

describe('error normalisation', () => {
  it('uses the backend detail string (409)', async () => {
    http.defaults.adapter = respond(409, { detail: 'Answer the follow-up question before continuing' })
    const err = await http.get('/x').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(409)
    expect(err.message).toBe('Answer the follow-up question before continuing')
    expect(err.outcomeUnknown).toBe(false)
  })

  it('maps 422 validation lists to per-field messages', async () => {
    http.defaults.adapter = respond(422, { detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address' }, { loc: ['body', 'password'], msg: 'Value error, Password must be at most 72 bytes' }] })
    const err = await http.post('/x', {}).catch((e) => e)
    expect(err.status).toBe(422)
    expect(err.fieldErrors).toEqual({ email: 'value is not a valid email address', password: 'Password must be at most 72 bytes' })
  })

  it.each([
    [401, /session has expired/i],
    [404, /could not find/i],
    [500, /went wrong on our side/i],
  ])('falls back to a friendly message for %i without a detail', async (status, pattern) => {
    http.defaults.adapter = respond(status, {})
    const err = await http.get('/x').catch((e) => e)
    expect(err.message).toMatch(pattern)
  })

  it('treats 5xx, timeouts and network failures as "outcome unknown"', () => {
    expect(new ApiError('x', { kind: 'http', status: 500 }).outcomeUnknown).toBe(true)
    expect(new ApiError('x', { kind: 'timeout' }).outcomeUnknown).toBe(true)
    expect(new ApiError('x', { kind: 'network' }).outcomeUnknown).toBe(true)
    expect(new ApiError('x', { kind: 'http', status: 422 }).outcomeUnknown).toBe(false)
  })

  it('identifies timeouts and network errors', () => {
    const timeout = toApiError(new AxiosError('timeout', 'ECONNABORTED', { headers: {} } as InternalAxiosRequestConfig))
    expect(timeout.kind).toBe('timeout')
    const net = toApiError(new AxiosError('Network Error', 'ERR_NETWORK', { headers: {} } as InternalAxiosRequestConfig))
    expect(net.kind).toBe('network')
    expect(net.message).toMatch(/cannot reach the server/i)
  })
})

describe('auth handling', () => {
  it('attaches the bearer token when one is stored', async () => {
    tokenStore.set('abc123')
    let seen: string | undefined
    http.defaults.adapter = (config) => { seen = String(config.headers.Authorization); return respond(200, {})(config) }
    await http.get('/x')
    expect(seen).toBe('Bearer abc123')
  })

  it('sends no Authorization header when signed out', async () => {
    let seen: unknown = 'unset'
    http.defaults.adapter = (config) => { seen = config.headers.Authorization; return respond(200, {})(config) }
    await http.get('/x')
    expect(seen).toBeUndefined()
  })

  it('a 401 on a protected call clears the token and notifies the app', async () => {
    tokenStore.set('expired')
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    http.defaults.adapter = respond(401, { detail: 'Not authenticated' })
    await http.get('/dashboard').catch(() => undefined)
    expect(tokenStore.get()).toBeNull()
    expect(handler).toHaveBeenCalledOnce()
  })

  it('a 401 from login (wrong password) does NOT sign anyone out', async () => {
    tokenStore.set('still-valid')
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    http.defaults.adapter = respond(401, { detail: 'Incorrect email or password' })
    await http.post('/auth/login', {}).catch(() => undefined)
    expect(handler).not.toHaveBeenCalled()
    expect(tokenStore.get()).toBe('still-valid')
  })
})

describe('timeouts', () => {
  it('uses a long timeout (>= 90 s) for the Gemini-backed calls and the default for the rest', async () => {
    expect(AI_TIMEOUT_MS).toBeGreaterThanOrEqual(90_000)
    const seen: Record<string, number | undefined> = {}
    http.defaults.adapter = (config) => { seen[`${config.method} ${config.url}`] = config.timeout; return respond(200, {})(config) }
    await submitAnswer({ interview_id: 1, answer_text: 'x' })
    await submitFollowUp({ interview_id: 1, answer_text: 'x' })
    await completeInterview(1)
    await nextQuestion(1)
    expect(seen['post /interviews/answer']).toBe(AI_TIMEOUT_MS)
    expect(seen['post /interviews/follow-up']).toBe(AI_TIMEOUT_MS)
    expect(seen['post /interviews/complete']).toBe(AI_TIMEOUT_MS)
    expect(seen['post /interviews/next']).toBe(DEFAULT_TIMEOUT_MS)
  })
})
