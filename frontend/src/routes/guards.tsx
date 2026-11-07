import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { PageLoader } from '@/components/ui/Feedback'
import { useAuth } from '@/context/AuthContext'

/** Only signed-in users may pass; everyone else is sent to /login and returned afterwards. */
export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <div className="min-h-screen"><PageLoader label="Checking your session" /></div>
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (status === 'offline') {
    // The saved session could not be verified (network/server problem). It is kept, not discarded.
    return (
      <div className="grid min-h-screen place-items-center p-6 text-center">
        <div className="max-w-sm space-y-3">
          <h1 className="text-lg font-semibold">We can't reach the server</h1>
          <p className="text-sm text-muted">Your session is still saved. Check your connection and try again.</p>
          <button type="button" className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white" onClick={() => window.location.reload()}>Retry</button>
        </div>
      </div>
    )
  }
  return <Outlet />
}

/** Login/registration are for signed-out users; signed-in users go to the dashboard. */
export function PublicOnlyRoute() {
  const { status } = useAuth()
  if (status === 'loading') return <div className="min-h-screen"><PageLoader label="Checking your session" /></div>
  if (status === 'authenticated') return <Navigate to="/dashboard" replace />
  return <Outlet />
}
