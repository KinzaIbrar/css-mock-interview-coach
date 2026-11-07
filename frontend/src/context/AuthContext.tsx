import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import * as authApi from '@/api/auth'
import { setUnauthorizedHandler, toApiError, tokenStore } from '@/api/client'
import type { LoginRequest, RegisterRequest, User } from '@/api/types'

type Status = 'loading' | 'authenticated' | 'anonymous' | 'offline'

interface AuthValue {
  user: User | null
  status: Status
  signIn: (body: LoginRequest) => Promise<void>
  signUp: (body: RegisterRequest) => Promise<void>
  /** Client-side only: the backend has no logout endpoint, so this discards the token. */
  signOut: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<Status>(() => (tokenStore.get() ? 'loading' : 'anonymous'))

  const signOut = useCallback(() => {
    tokenStore.clear()
    queryClient.clear() // never keep one user's data in memory for the next
    setUser(null)
    setStatus('anonymous')
  }, [queryClient])

  // Validate any stored token once on start. A 401 clears it (and triggers the handler below).
  useEffect(() => {
    if (!tokenStore.get()) return
    let cancelled = false
    authApi
      .getMe()
      .then((u) => { if (!cancelled) { setUser(u); setStatus('authenticated') } })
      .catch((e) => {
        if (cancelled) return
        // Only an invalid/expired token signs the user out; a network blip or 5xx must not discard a valid session.
        if (toApiError(e).status === 401) signOut()
        else setStatus('offline')
      })
    return () => { cancelled = true }
  }, [signOut])

  // Any 401 from a protected call (expired/invalid token) signs the user out; the route guard then redirects.
  useEffect(() => {
    setUnauthorizedHandler(signOut)
    return () => setUnauthorizedHandler(null)
  }, [signOut])

  const signIn = useCallback(async (body: LoginRequest) => {
    const res = await authApi.login(body)
    tokenStore.set(res.access_token)
    setUser(res.user)
    setStatus('authenticated')
  }, [])

  const signUp = useCallback(async (body: RegisterRequest) => {
    const res = await authApi.register(body)
    tokenStore.set(res.access_token)
    setUser(res.user)
    setStatus('authenticated')
  }, [])

  const value = useMemo(() => ({ user, status, signIn, signUp, signOut }), [user, status, signIn, signUp, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
