import { useQuery } from '@tanstack/react-query'
import { Info, LogOut } from 'lucide-react'
import { getHealth } from '@/api/auth'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Alert } from '@/components/ui/Feedback'
import { useAuth } from '@/context/AuthContext'
import { describeAiStatus } from '@/utils/aiStatus'
import { formatDate } from '@/utils/format'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 py-3 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-sm font-medium text-ink break-words">{value}</dd>
    </div>
  )
}

export default function Profile() {
  const { user, signOut } = useAuth()
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, staleTime: 5 * 60_000, retry: false })
  if (!user) return null
  const ai = describeAiStatus(health.data)

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-[1.75rem] font-semibold">Profile</h1>
        <p className="mt-1 text-sm text-muted">Your account details.</p>
      </div>

      <Card>
        <CardHeader title="Account" />
        <CardBody>
          <dl className="divide-y divide-line">
            <Row label="Name" value={user.full_name} />
            <Row label="Email" value={user.email} />
            <Row label="Member since" value={formatDate(user.created_at)} />
          </dl>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="AI evaluation" />
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

      <Card>
        <CardHeader title="Session" />
        <CardBody className="space-y-4">
          <p className="text-sm text-ink-2">Signing out removes your session from this browser. Your interviews and reports stay saved on your account.</p>
          <Button variant="secondary" onClick={signOut} icon={<LogOut className="size-4" aria-hidden />}>Sign out</Button>
        </CardBody>
      </Card>

      <Alert tone="info" title="Not available yet" live="off">
        <ul className="mt-1 list-disc space-y-1 pl-5">
          <li>Editing your name, email or preferences.</li>
          <li>Changing or resetting your password.</li>
          <li>Signing out on the server (sessions last 12 hours; signing out only clears this browser).</li>
        </ul>
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted"><Info className="size-3.5" aria-hidden />These need new backend features; nothing here is simulated.</p>
      </Alert>
    </div>
  )
}
