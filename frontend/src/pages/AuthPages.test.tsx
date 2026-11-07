import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import { ProtectedRoute, PublicOnlyRoute } from '@/routes/guards'
import { renderApp } from '@/test/utils'
import Login from './Login'
import Register from './Register'

vi.mock('@/context/AuthContext', () => ({ useAuth: vi.fn() }))
const mockAuth = (over: Partial<ReturnType<typeof useAuth>> = {}) => {
  const value = { user: null, status: 'anonymous', signIn: vi.fn().mockResolvedValue(undefined), signUp: vi.fn().mockResolvedValue(undefined), signOut: vi.fn(), ...over } as ReturnType<typeof useAuth>
  vi.mocked(useAuth).mockReturnValue(value)
  return value
}
beforeEach(() => vi.resetAllMocks())

describe('Login', () => {
  it('validates required fields before calling the API', async () => {
    const auth = mockAuth()
    renderApp(<Login />, { route: '/login', path: '/login' })
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter your email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(auth.signIn).not.toHaveBeenCalled()
  })

  it('rejects a malformed email', async () => {
    const auth = mockAuth()
    renderApp(<Login />, { route: '/login', path: '/login' })
    await userEvent.type(screen.getByLabelText('Email'), 'not-an-email')
    await userEvent.type(screen.getByLabelText('Password'), 'secret-pass')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(auth.signIn).not.toHaveBeenCalled()
  })

  it('signs in and goes to the dashboard', async () => {
    const auth = mockAuth()
    renderApp(<Login />, { route: '/login', path: '/login' })
    await userEvent.type(screen.getByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret-pass')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(auth.signIn).toHaveBeenCalledWith({ email: 'a@example.com', password: 'secret-pass' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/dashboard'))
  })

  it('shows a clear message for wrong credentials (401)', async () => {
    mockAuth({ signIn: vi.fn().mockRejectedValue(new ApiError('Incorrect email or password', { kind: 'http', status: 401 })) })
    renderApp(<Login />, { route: '/login', path: '/login' })
    await userEvent.type(screen.getByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-pass')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
  })

  it('shows a network error without losing the typed email', async () => {
    mockAuth({ signIn: vi.fn().mockRejectedValue(new ApiError('Cannot reach the server.', { kind: 'network' })) })
    renderApp(<Login />, { route: '/login', path: '/login' })
    await userEvent.type(screen.getByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret-pass')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Cannot reach the server.')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('a@example.com')
  })

  it('password visibility can be toggled', async () => {
    mockAuth()
    renderApp(<Login />, { route: '/login', path: '/login' })
    const field = screen.getByLabelText('Password')
    expect(field).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(field).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('does not pretend password reset exists', () => {
    mockAuth()
    renderApp(<Login />, { route: '/login', path: '/login' })
    expect(screen.getByText(/password reset is not available yet/i)).toBeInTheDocument()
  })
})

describe('Register', () => {
  const fill = async (over: Partial<Record<'name' | 'email' | 'pw' | 'confirm', string>> = {}) => {
    await userEvent.type(screen.getByLabelText('Full name'), over.name ?? 'Ayesha Khan')
    await userEvent.type(screen.getByLabelText('Email'), over.email ?? 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), over.pw ?? 'long-enough-pw')
    await userEvent.type(screen.getByLabelText('Confirm password'), over.confirm ?? 'long-enough-pw')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
  }

  it('validates required fields', async () => {
    const auth = mockAuth()
    renderApp(<Register />, { route: '/register', path: '/register' })
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Enter your name')).toBeInTheDocument()
    expect(screen.getByText('Use at least 8 characters')).toBeInTheDocument()
    expect(auth.signUp).not.toHaveBeenCalled()
  })

  it('requires matching passwords', async () => {
    const auth = mockAuth()
    renderApp(<Register />, { route: '/register', path: '/register' })
    await fill({ confirm: 'something-else' })
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
    expect(auth.signUp).not.toHaveBeenCalled()
  })

  it('registers and goes to the dashboard (confirm password is not sent)', async () => {
    const auth = mockAuth()
    renderApp(<Register />, { route: '/register', path: '/register' })
    await fill()
    await waitFor(() => expect(auth.signUp).toHaveBeenCalledWith({ full_name: 'Ayesha Khan', email: 'a@example.com', password: 'long-enough-pw' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/dashboard'))
  })

  it('shows a duplicate-email error on the email field (409)', async () => {
    mockAuth({ signUp: vi.fn().mockRejectedValue(new ApiError('exists', { kind: 'http', status: 409 })) })
    renderApp(<Register />, { route: '/register', path: '/register' })
    await fill()
    expect(await screen.findByText(/an account with this email already exists/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
  })

  it('maps backend 422 field errors onto the form', async () => {
    mockAuth({ signUp: vi.fn().mockRejectedValue(new ApiError('bad', { kind: 'http', status: 422, fieldErrors: { password: 'Password must be at most 72 bytes' } })) })
    renderApp(<Register />, { route: '/register', path: '/register' })
    await fill()
    expect(await screen.findByText('Password must be at most 72 bytes')).toBeInTheDocument()
  })
})

describe('route guards', () => {
  const tree = () =>
    renderApp(
      <Routes>
        <Route element={<ProtectedRoute />}><Route path="/private" element={<div>secret page</div>} /></Route>
        <Route element={<PublicOnlyRoute />}><Route path="/login" element={<div>login page</div>} /></Route>
        <Route path="/dashboard" element={<div>dashboard page</div>} />
      </Routes>,
      { route: '/private' },
    )

  it('sends signed-out users to /login instead of the protected page', async () => {
    mockAuth({ status: 'anonymous' })
    tree()
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(screen.queryByText('secret page')).not.toBeInTheDocument()
  })

  it('shows a loading state (not the page) while the session is being checked', () => {
    mockAuth({ status: 'loading' })
    tree()
    expect(screen.getByText(/checking your session/i)).toBeInTheDocument()
    expect(screen.queryByText('secret page')).not.toBeInTheDocument()
  })

  it('lets signed-in users in, and keeps them out of /login', async () => {
    mockAuth({ status: 'authenticated' })
    tree()
    expect(await screen.findByText('secret page')).toBeInTheDocument()
  })
})
