import type { ReactNode } from 'react'
import { BadgeCheck, MessagesSquare, TrendingUp } from 'lucide-react'
import { Logo } from './Logo'

const POINTS = [
  { icon: MessagesSquare, text: 'One question at a time, with follow-ups like a real panel.' },
  { icon: BadgeCheck, text: 'Scored on six criteria, with clear labels showing how each answer was evaluated.' },
  { icon: TrendingUp, text: 'Track your progress by subject across sessions.' },
]

export function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="hidden bg-navy p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <Logo inverted />
        <div className="max-w-md">
          <h2 className="text-3xl font-semibold leading-tight text-white">Practise your CSS interview before the real one.</h2>
          <ul className="mt-8 space-y-5">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3 text-white/80">
                <Icon className="mt-0.5 size-5 shrink-0 text-white" aria-hidden />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-white/60">Practice questions and reference answers are unverified study aids, not official CSS material.</p>
      </aside>

      <main id="main" className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md animate-in">
          <Logo className="mb-8 lg:hidden" />
          <h1 className="text-[1.75rem] font-semibold">{title}</h1>
          <p className="mt-1.5 text-sm text-muted">{subtitle}</p>
          <div className="mt-7">{children}</div>
          <div className="mt-6 text-center text-sm text-muted">{footer}</div>
        </div>
      </main>
    </div>
  )
}
