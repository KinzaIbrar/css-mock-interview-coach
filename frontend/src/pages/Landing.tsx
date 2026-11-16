import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, ArrowRight, BarChart3, Bot, CheckCircle2, ClipboardCheck, Compass, GraduationCap, History,
  LayoutDashboard, Menu, MessageSquareText, Mic, PlayCircle, Sparkles, Target, Workflow, X, type LucideIcon,
} from 'lucide-react'
import { Logo } from '@/components/layout/Logo'
import { Badge } from '@/components/ui/Badge'
import { ButtonLink } from '@/components/ui/Button'
import { Card, CardBody } from '@/components/ui/Card'
import { buttonClass } from '@/utils/buttonStyles'
import { useAuth } from '@/context/AuthContext'

const NAV_LINKS = [
  { href: '#how-it-works', label: 'How it works' },
  { href: '#agents', label: 'AI agents' },
  { href: '#features', label: 'Features' },
]

/** Sticky top nav. CTAs adapt to auth state instead of blindly sending a signed-in visitor to /login. */
function Nav() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <Logo />
        <nav className="hidden items-center gap-6 md:flex" aria-label="Page sections">
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href} className="text-sm font-medium text-ink-2 transition-colors hover:text-ink">{l.label}</a>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          {user ? (
            <ButtonLink to="/dashboard" icon={<LayoutDashboard className="size-4" aria-hidden />}>Go to dashboard</ButtonLink>
          ) : (
            <>
              <ButtonLink to="/login" variant="ghost">Login</ButtonLink>
              <ButtonLink to="/register">Get started</ButtonLink>
            </>
          )}
        </div>
        <button className="rounded-control p-2 text-ink md:hidden" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls="mobile-nav" aria-label={open ? 'Close menu' : 'Open menu'}>
          {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
        </button>
      </div>
      {open && (
        <div id="mobile-nav" className="animate-in border-t border-line bg-surface px-4 py-4 md:hidden">
          <nav className="flex flex-col gap-1" aria-label="Page sections">
            {NAV_LINKS.map((l) => (
              <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="rounded-control px-2 py-2.5 text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink">{l.label}</a>
            ))}
          </nav>
          <div className="mt-3 flex flex-col gap-2 border-t border-line pt-3">
            {user ? (
              <ButtonLink to="/dashboard" icon={<LayoutDashboard className="size-4" aria-hidden />}>Go to dashboard</ButtonLink>
            ) : (
              <>
                <ButtonLink to="/register">Get started</ButtonLink>
                <ButtonLink to="/login" variant="secondary">Login</ButtonLink>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  )
}

/** A faithful, scoreless recreation of the real results page - same cards, icons and labels as the
 * actual product, deliberately with no numbers: a marketing preview must never show a fabricated score. */
function ProductPreview() {
  const dims: { icon: LucideIcon; name: string; blurb: string }[] = [
    { icon: ClipboardCheck, name: 'Constitutional Understanding', blurb: 'Constitutional provisions & legal frameworks' },
    { icon: BarChart3, name: 'Analytical Depth', blurb: 'Reasoning & supporting evidence' },
    { icon: GraduationCap, name: 'Subject Expertise', blurb: 'Subject knowledge & accuracy' },
    { icon: Compass, name: 'Policy Awareness', blurb: 'Current affairs & policy context' },
  ]
  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface shadow-raised">
      <div className="flex items-center gap-2 border-b border-line bg-surface-2 px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-danger/60" aria-hidden /><span className="size-2.5 rounded-full bg-warning/60" aria-hidden /><span className="size-2.5 rounded-full bg-success/60" aria-hidden />
        <span className="ml-2 text-xs text-muted">Interview report</span>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary"><Sparkles className="size-3.5" aria-hidden />Four-dimensional evaluation</div>
        <div className="grid grid-cols-2 gap-3">
          {dims.map((d) => (
            <div key={d.name} className="rounded-control border border-line p-3">
              <span className="grid size-8 place-items-center rounded-control bg-primary-soft text-primary"><d.icon className="size-4" aria-hidden /></span>
              <p className="mt-2 text-xs font-semibold text-ink">{d.name}</p>
              <p className="mt-0.5 text-[11px] text-muted">{d.blurb}</p>
              <div className="mt-2 h-1.5 w-full rounded-full bg-line" aria-hidden />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const AGENTS: { key: string; icon: LucideIcon; tone: string; name: string; description: string }[] = [
  { key: 'interviewer', icon: MessageSquareText, tone: 'bg-primary-soft text-primary-ink', name: 'Interviewer Agent', description: 'Greets you, asks the introduction and main questions, and decides when a follow-up is allowed.' },
  { key: 'evaluator', icon: ClipboardCheck, tone: 'bg-accent-soft text-accent-ink', name: 'Evaluator Agent', description: 'Scores every answer, and every follow-up reply separately, on four CSS-specific dimensions.' },
  { key: 'coaching', icon: GraduationCap, tone: 'bg-warning-soft text-warning', name: 'Coaching Agent', description: 'Finds weak topics and recurring mistakes and recommends practice questions.' },
  { key: 'orchestration', icon: Workflow, tone: 'bg-success-soft text-success', name: 'Orchestration Agent', description: 'Runs the workflow that connects the agents and keeps state between every step.' },
]

const STEPS = [
  { n: '01', icon: Target, title: 'Start your interview', text: 'Choose a CSS subject, difficulty and number of questions, or jump in with a Quick Start.' },
  { n: '02', icon: Mic, title: 'Answer questions', text: 'Work through one question at a time with the AI interviewer, with occasional follow-ups like a real panel.' },
  { n: '03', icon: Bot, title: 'Get AI evaluation', text: 'Each answer is scored across four CSS-specific dimensions, with a clearly labelled fallback if AI is unavailable.' },
  { n: '04', icon: BarChart3, title: 'Improve your performance', text: 'Review strengths, weaknesses and missing points, then revisit weak topics in your next attempt.' },
]

const FEATURES: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Bot, title: 'AI mock interviews', text: 'Practise in a structured, conversational interview with an AI interviewer and an optional on-screen avatar.' },
  { icon: Sparkles, title: 'Intelligent evaluation', text: 'Answers are evaluated by Gemini when available, with a clearly labelled, never-hidden fallback when it is not.' },
  { icon: BarChart3, title: 'Competency-based scoring', text: 'Every answer is scored 0-10 across four CSS-specific dimensions, not a single opaque number.' },
  { icon: MessageSquareText, title: 'Real-time interview experience', text: 'A live conversation transcript, speech input/output, and an optional camera for posture feedback.' },
  { icon: Target, title: 'Performance analytics', text: 'A dashboard with score trends, per-subject and per-dimension performance, built from your real results.' },
  { icon: History, title: 'Interview history', text: 'Search, filter and sort every interview you have taken, and revisit any past report in full.' },
]

const BENEFITS = [
  'Structured preparation across all seven CSS subjects',
  'A realistic, one-question-at-a-time interview environment',
  'Detailed, dimension-by-dimension answer evaluation',
  'Clear identification of strengths and weak topics',
  'Actionable, rule-based improvement recommendations',
  'A full history of every past interview to revisit',
]

export default function Landing() {
  const { user } = useAuth()
  const primaryCta = user ? { to: '/dashboard', label: 'Go to dashboard' } : { to: '/register', label: 'Start practising' }

  return (
    <div className="min-h-screen bg-canvas">
      <Nav />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-accent/20 blur-3xl" aria-hidden />
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:items-center lg:px-8 lg:py-24">
          <div>
            <Badge tone="accent">Built for Pakistan's CSS exam</Badge>
            <h1 className="mt-4 text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
              Prepare smarter. Interview better. Walk in with confidence.
            </h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-ink-2">
              Practise AI-powered CSS mock interviews with a real conversational panel, four-dimensional answer
              evaluation, and personalised feedback — built specifically for Central Superior Services aspirants.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <ButtonLink to={primaryCta.to} size="lg" icon={<PlayCircle className="size-5" aria-hidden />}>{primaryCta.label}</ButtonLink>
              <a href="#features" className={buttonClass('secondary', 'lg')}>Explore features</a>
            </div>
            <p className="mt-4 text-xs text-muted">No payment details needed to get started.</p>
          </div>
          <ProductPreview />
        </div>
      </section>

      {/* Value strip */}
      <section aria-label="What CSS Mock Interview Coach offers" className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-4 py-8 sm:px-6 md:grid-cols-4 lg:px-8">
          {[
            { icon: Bot, text: 'AI-powered mock interviews' },
            { icon: Sparkles, text: 'Intelligent answer evaluation' },
            { icon: BarChart3, text: 'Structured performance feedback' },
            { icon: Compass, text: 'Personalised preparation guidance' },
          ].map((v) => (
            <div key={v.text} className="flex items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-control bg-primary-soft text-primary"><v.icon className="size-5" aria-hidden /></span>
              <span className="text-sm font-medium text-ink">{v.text}</span>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight">How it works</h2>
          <p className="mt-3 text-ink-2">The same four-step flow every interview on the platform actually follows.</p>
        </div>
        <div className="relative mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div className="absolute inset-x-0 top-6 hidden h-px bg-line lg:block" aria-hidden />
          {STEPS.map((s) => (
            <div key={s.n} className="relative">
              <div className="relative z-10 grid size-12 place-items-center rounded-full bg-primary text-white"><s.icon className="size-5" aria-hidden /></div>
              <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Step {s.n}</p>
              <h3 className="mt-1 text-base font-semibold text-ink">{s.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Multi-agent architecture */}
      <section id="agents" className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="flex items-center justify-center gap-2 text-3xl font-bold tracking-tight"><Workflow className="size-7 text-primary" aria-hidden />Four AI agents, one interview panel</h2>
            <p className="mt-3 text-ink-2">Every session is run by the same four specialised agents you can watch work in the interview room itself.</p>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {AGENTS.map((a) => (
              <Card key={a.key} className="transition-shadow hover:shadow-raised">
                <CardBody>
                  <span className={`grid size-10 place-items-center rounded-control ${a.tone}`}><a.icon className="size-5" aria-hidden /></span>
                  <h3 className="mt-3 text-sm font-semibold text-ink">{a.name}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{a.description}</p>
                </CardBody>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight">Everything you need to prepare</h2>
          <p className="mt-3 text-ink-2">Each of these is a real, working part of the platform today.</p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <Card key={f.title} className="transition-shadow hover:shadow-raised">
              <CardBody>
                <span className="grid size-10 place-items-center rounded-control bg-primary-soft text-primary"><f.icon className="size-5" aria-hidden /></span>
                <h3 className="mt-3 text-sm font-semibold text-ink">{f.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.text}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      </section>

      {/* Why choose */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <h2 className="text-3xl font-bold tracking-tight">Why CSS aspirants use this platform</h2>
              <p className="mt-3 text-ink-2">
                Genuine practice, not guesswork. The platform does not guarantee a pass — it gives you a structured
                way to find and fix the gaps in how you answer before the real panel does.
              </p>
            </div>
            <ul className="space-y-3">
              {BENEFITS.map((b) => (
                <li key={b} className="flex items-start gap-3 text-sm text-ink-2">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />{b}
                </li>
              ))}
            </ul>
          </div>
          <p className="mt-8 flex items-center gap-2 text-xs text-muted"><AlertTriangle className="size-3.5 shrink-0" aria-hidden />Sample questions and reference answers are unverified study aids, not official CSS material.</p>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
        <div className="overflow-hidden rounded-card bg-primary px-6 py-14 text-center text-white sm:px-12">
          <h2 className="text-3xl font-bold text-white sm:text-4xl">Your next interview starts with better preparation.</h2>
          <p className="mx-auto mt-3 max-w-xl text-white/75">Start practising with CSS Mock Interview Coach and turn every attempt into an opportunity to improve.</p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <ButtonLink to={primaryCta.to} variant="accent" size="lg" icon={<PlayCircle className="size-5" aria-hidden />}>{primaryCta.label}</ButtonLink>
            {!user && <ButtonLink to="/login" variant="secondary" size="lg">Login</ButtonLink>}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-line">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-8 sm:flex-row sm:justify-between">
            <div className="max-w-sm">
              <Logo />
              <p className="mt-3 text-sm text-muted">AI-powered CSS mock interview practice, with four-dimensional evaluation and personalised feedback for Central Superior Services aspirants.</p>
            </div>
            <div className="flex gap-12">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Platform</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li><a href="#how-it-works" className="text-ink-2 hover:text-ink">How it works</a></li>
                  <li><a href="#agents" className="text-ink-2 hover:text-ink">AI agents</a></li>
                  <li><a href="#features" className="text-ink-2 hover:text-ink">Features</a></li>
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Account</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li><Link to="/login" className="text-ink-2 hover:text-ink">Login</Link></li>
                  <li><Link to="/register" className="text-ink-2 hover:text-ink">Get started</Link></li>
                </ul>
              </div>
            </div>
          </div>
          <div className="mt-8 flex flex-col gap-2 border-t border-line pt-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
            <p>© {new Date().getFullYear()} CSS Mock Interview Coach.</p>
            <p className="flex items-center gap-1.5"><ArrowRight className="size-3.5 rotate-[-45deg]" aria-hidden />Practice questions are unverified study aids, not official CSS material.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
