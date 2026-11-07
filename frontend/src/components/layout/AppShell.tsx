import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { History, LayoutDashboard, Library, LogOut, Menu, PlayCircle, UserRound, X, type LucideIcon } from 'lucide-react'
import { getHealth } from '@/api/auth'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/utils/cn'
import { describeAiStatus } from '@/utils/aiStatus'
import { Logo } from './Logo'

const NAV: Array<{ to: string; label: string; icon: LucideIcon }> = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/interviews/new', label: 'New interview', icon: PlayCircle },
  { to: '/history', label: 'Interview history', icon: History },
  { to: '/questions', label: 'Question bank', icon: Library },
  { to: '/profile', label: 'Profile', icon: UserRound },
]

/** Whether Gemini can be used right now (key configured AND not paused by quota / rate limit / outage). */
function AiStatus() {
  const { data } = useQuery({ queryKey: ['health'], queryFn: getHealth, staleTime: 60_000, retry: false })
  const status = describeAiStatus(data)
  if (!status) return null
  return (
    <p
      className={cn('rounded-control px-3 py-2 text-xs leading-snug text-white/80', status.degraded ? 'border border-amber-300/40 bg-amber-300/10' : 'bg-white/5')}
      data-testid="ai-status"
    >
      <span className="font-semibold text-white">{status.headline}</span>
      <br />
      {status.detail}
    </p>
  )
}

export function AppShell() {
  const { user, signOut } = useAuth()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-control focus:bg-surface focus:px-3 focus:py-2 focus:shadow-raised">
        Skip to main content
      </a>

      {open && <div className="fixed inset-0 z-30 bg-ink/40 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}

      <aside
        id="sidebar"
        aria-label="Primary"
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-navy px-3 py-4 text-white transition-transform duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between px-2 pb-5">
          <Logo inverted />
          <button className="rounded-control p-1.5 text-white/80 hover:bg-white/10 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <nav className="flex-1 space-y-1" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/interviews/new'}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive ? 'bg-white text-ink' : 'text-white/80 hover:bg-white/10 hover:text-white',
                )
              }
            >
              <Icon className="size-[18px]" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="space-y-3 border-t border-white/10 pt-4">
          <AiStatus />
          <div className="flex items-center gap-3 px-1">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-white/15 text-sm font-semibold" aria-hidden>
              {(user?.full_name ?? '?').slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{user?.full_name}</p>
              <p className="truncate text-xs text-white/65">{user?.email}</p>
            </div>
            <button onClick={signOut} className="rounded-control p-2 text-white/80 hover:bg-white/10 hover:text-white" aria-label="Sign out" title="Sign out">
              <LogOut className="size-[18px]" aria-hidden />
            </button>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-surface/95 px-4 py-3 backdrop-blur lg:hidden">
          <button
            className="rounded-control p-2 text-ink hover:bg-surface-2"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
            aria-expanded={open}
            aria-controls="sidebar"
          >
            <Menu className="size-5" aria-hidden />
          </button>
          <Logo />
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
