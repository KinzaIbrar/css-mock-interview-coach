import { CheckCircle2, CircleDashed } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'

export function StatusBadge({ status }: { status: string }) {
  return status === 'completed'
    ? <Badge tone="success" icon={CheckCircle2}>Completed</Badge>
    : <Badge tone="primary" icon={CircleDashed}>In progress</Badge>
}
