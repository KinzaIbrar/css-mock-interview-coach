import { useQuery } from '@tanstack/react-query'
import { Bot, Calendar, Clock, Info, KeyRound, LogOut, Mail, Pencil, ShieldCheck, User, UserRound } from 'lucide-react'
import { getHealth } from '@/api/auth'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { useAuth } from '@/context/AuthContext'
import { describeAiStatus } from '@/utils/aiStatus'
import { formatDate } from '@/utils/format'

function Row({ label, value, icon: Icon }: { label: string; value: string; icon: typeof User }) {
  return (
    <div className="flex items-start gap-3 py-3">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
      <div className="min-w-0 flex-1 sm:flex sm:items-center sm:justify-between sm:gap-3">
        <dt className="text-sm text-muted">{label}</dt>
        <dd className="mt-0.5 text-sm font-medium text-ink break-words sm:mt-0">{value}</dd>
      </div>
    </div>
  )
}

/** What isn't built yet, said plainly - never a button that looks clickable but does nothing. */
function ComingSoonRow({ icon: Icon, text }: { icon: typeof User; text: string }) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <span className="grid size-8 shrink-0 place-items-center rounded-control bg-surface-2 text-muted"><Icon className="size-4" aria-hidden /></span>
      <span className="min-w-0 flex-1 text-sm text-ink-2">{text}</span>
      <Badge tone="warning">Coming soon</Badge>
    </li>
  )
}

export default function Profile() {
  const { user, signOut } = useAuth()
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, staleTime: 5 * 60_000, retry: false })
  if (!user) return null
  const ai = describeAiStatus(health.data)
  const initial = (user.full_name || '?').slice(0, 1).toUpperCase()

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-[2rem] font-bold tracking-tight"><UserRound className="size-7 text-primary" aria-hidden />Profile</h1>
        <p className="mt-1.5 text-sm text-muted">Your account details and how your answers are evaluated.</p>
      </div>

      <Card className="transition-shadow hover:shadow-raised">
        <CardBody className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
          <span className="grid size-20 shrink-0 place-items-center rounded-full bg-accent text-3xl font-semibold text-accent-ink" aria-hidden>{initial}</span>
          <div className="min-w-0 flex-1">
            <p className="text-xl font-bold text-ink">{user.full_name}</p>
            <p className="mt-1 flex items-center justify-center gap-1.5 text-sm text-muted sm:justify-start"><Mail className="size-4 shrink-0" aria-hidden />{user.email}</p>
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2 sm:justify-start">
              <Badge tone="success" icon={ShieldCheck}>Signed in</Badge>
              <Badge icon={Calendar}>Member since {formatDate(user.created_at)}</Badge>
            </div>
          </div>
        </CardBody>
      </Card>

      <Card className="transition-shadow hover:shadow-raised">
        <CardHeader title={<span className="flex items-center gap-2"><User className="size-4 text-primary" aria-hidden />Account details</span>} />
        <CardBody>
          <dl className="divide-y divide-line">
            <Row label="Full name" value={user.full_name} icon={User} />
            <Row label="Email address" value={user.email} icon={Mail} />
            <Row label="Member since" value={formatDate(user.created_at)} icon={Calendar} />
          </dl>
        </CardBody>
      </Card>

      <Card className="transition-shadow hover:shadow-raised">
        <CardHeader title={<span className="flex items-center gap-2"><Bot className="size-4 text-primary" aria-hidden />AI evaluation</span>} />
        <CardBody className="space-y-3 text-sm text-ink-2">
          {health.isPending && <p className="text-muted">Checking…</p>}
          {ai && (
            <p>
              <span className="font-semibold text-ink">{ai.headline}.</span> {ai.detail}{' '}
              Whenever an answer is not evaluated by the AI it is evaluated by a simple keyword check and clearly labelled "not AI".
            </p>
          )}
        </CardBody>
      </Card>

      <Card className="transition-shadow hover:shadow-raised">
        <CardHeader title={<span className="flex items-center gap-2"><LogOut className="size-4 text-primary" aria-hidden />Session</span>} />
        <CardBody className="space-y-4">
          <p className="text-sm text-ink-2">Signing out removes your session from this browser. Your interviews and reports stay saved on your account.</p>
          <Button variant="secondary" onClick={signOut} icon={<LogOut className="size-4" aria-hidden />}>Sign out</Button>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={<span className="flex items-center gap-2"><Clock className="size-4 text-muted" aria-hidden />More profile options are coming</span>} />
        <CardBody>
          <ul className="divide-y divide-line">
            <ComingSoonRow icon={Pencil} text="Editing your name, email or preferences" />
            <ComingSoonRow icon={KeyRound} text="Changing or resetting your password" />
            <ComingSoonRow icon={LogOut} text="Signing out on the server (sessions last 12 hours; signing out here only clears this browser)" />
          </ul>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-muted"><Info className="size-3.5 shrink-0" aria-hidden />These need new backend features — nothing on this page is simulated.</p>
        </CardBody>
      </Card>
    </div>
  )
}
