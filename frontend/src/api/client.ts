import axios, { AxiosError, type AxiosRequestConfig } from 'axios'

/** Backend base URL. "/api" works with the Vite dev proxy; override with VITE_API_BASE_URL. */
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
export const DEFAULT_TIMEOUT_MS = 30_000
/** Gemini-backed calls (answer, follow-up, complete) can take ~65 s during provider outages before the backend
 *  falls back, so they get a much longer timeout. Never use a shorter one: the backend may still be working. */
export const AI_TIMEOUT_MS = 120_000

// ---- token storage ----------------------------------------------------------------------------------------------
// The backend issues a bearer JWT (12 h, no refresh, no logout endpoint). It is kept in localStorage so a page
// refresh keeps the session; logging out simply discards it. Storage access can throw (private mode), so it is guarded.
const TOKEN_KEY = 'cmic.token'
let memoryToken: string | null = null
export const tokenStore = {
  get(): string | null {
    try { return localStorage.getItem(TOKEN_KEY) ?? memoryToken } catch { return memoryToken }
  },
  set(token: string): void {
    memoryToken = token
    try { localStorage.setItem(TOKEN_KEY, token) } catch { /* keep in memory only */ }
  },
  clear(): void {
    memoryToken = null
    try { localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
  },
}

// ---- errors -----------------------------------------------------------------------------------------------------
export type ApiErrorKind = 'http' | 'network' | 'timeout'

export class ApiError extends Error {
  status: number | null
  kind: ApiErrorKind
  /** Per-field messages from 422 responses, keyed by field name. */
  fieldErrors: Record<string, string>

  constructor(message: string, init: { status?: number | null; kind: ApiErrorKind; fieldErrors?: Record<string, string> }) {
    super(message)
    this.name = 'ApiError'
    this.status = init.status ?? null
    this.kind = init.kind
    this.fieldErrors = init.fieldErrors ?? {}
  }

  /** True when we do not know whether the server processed the request (so state must be re-checked). */
  get outcomeUnknown(): boolean {
    return this.kind !== 'http' || (this.status !== null && this.status >= 500)
  }
}

interface ValidationItem { loc?: Array<string | number>; msg?: string }

function messageFromDetail(detail: unknown): { message: string; fields: Record<string, string> } {
  if (typeof detail === 'string') return { message: detail, fields: {} }
  if (Array.isArray(detail)) {
    const fields: Record<string, string> = {}
    for (const item of detail as ValidationItem[]) {
      const field = item.loc?.filter((p) => typeof p === 'string' && p !== 'body').pop()
      if (typeof field === 'string' && item.msg) fields[field] = item.msg.replace(/^Value error, /, '')
    }
    const first = Object.values(fields)[0]
    return { message: first ?? 'Some of the information you entered is not valid.', fields }
  }
  return { message: '', fields: {} }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err
  if (axios.isAxiosError(err)) {
    const e = err as AxiosError<{ detail?: unknown }>
    if (e.response) {
      const { message, fields } = messageFromDetail(e.response.data?.detail)
      const fallback: Record<number, string> = {
        401: 'Your session has expired. Please sign in again.',
        403: 'You do not have permission to do that.',
        404: 'We could not find that.',
        409: 'That action is not available right now.',
        500: 'Something went wrong on our side. Please try again.',
      }
      return new ApiError(message || fallback[e.response.status] || 'The request failed.', {
        status: e.response.status, kind: 'http', fieldErrors: fields,
      })
    }
    if (e.code === 'ECONNABORTED' || e.code === 'ETIMEDOUT') {
      return new ApiError('The server took too long to respond.', { kind: 'timeout' })
    }
    return new ApiError('Cannot reach the server. Check your connection and that the backend is running.', { kind: 'network' })
  }
  return new ApiError(err instanceof Error ? err.message : 'Unexpected error.', { kind: 'network' })
}

// ---- client -----------------------------------------------------------------------------------------------------
let onUnauthorized: (() => void) | null = null
/** AuthContext registers this so any 401 from a protected call signs the user out. */
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn
}

export const http = axios.create({ baseURL: API_BASE_URL, timeout: DEFAULT_TIMEOUT_MS, headers: { Accept: 'application/json' } })

http.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res,
  (err: unknown) => {
    const apiError = toApiError(err)
    const url = axios.isAxiosError(err) ? (err.config?.url ?? '') : ''
    const isCredentialCall = url.includes('/auth/login') || url.includes('/auth/register')
    if (apiError.status === 401 && !isCredentialCall) {
      tokenStore.clear()
      onUnauthorized?.()
    }
    return Promise.reject(apiError)
  },
)

/** Options for the long Gemini-backed calls. */
export const aiRequest: AxiosRequestConfig = { timeout: AI_TIMEOUT_MS }
