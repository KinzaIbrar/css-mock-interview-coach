import { Link, Outlet } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Logo } from './Logo'

/** Minimal chrome for the interview room: no navigation to distract, one clear way out. */
export function FocusLayout() {
  return (
    <div className="min-h-screen bg-canvas">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-control focus:bg-surface focus:px-3 focus:py-2 focus:shadow-raised">
        Skip to main content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo />
          <Link to="/dashboard" className="inline-flex items-center gap-1.5 rounded-control px-2 py-1.5 text-sm font-medium text-ink-2 hover:bg-surface-2">
            <ArrowLeft className="size-4" aria-hidden />
            Leave (you can resume later)
          </Link>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
