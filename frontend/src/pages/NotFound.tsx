import { Compass } from 'lucide-react'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/Feedback'

export default function NotFound() {
  return (
    <main id="main" className="grid min-h-screen place-items-center px-4">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="The page you are looking for does not exist or has moved."
        action={<ButtonLink to="/dashboard">Go to dashboard</ButtonLink>}
      />
    </main>
  )
}
