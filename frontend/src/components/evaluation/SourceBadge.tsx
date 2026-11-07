import { Bot, FlaskConical, Layers } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'

/** Evaluation source -> label. Always icon + words, never colour alone. */
export function EvaluationSourceBadge({ source, model }: { source: string | null | undefined; model?: string | null }) {
  if (source === 'gemini') return <Badge tone="primary" icon={Bot}>AI evaluation{model ? ` · ${model}` : ' · Gemini'}</Badge>
  if (source === 'mixed') return <Badge tone="warning" icon={Layers}>Partly AI</Badge>
  if (source === 'dev_heuristic') return <Badge tone="warning" icon={FlaskConical}>Development evaluation · not AI</Badge>
  return null
}

export function FeedbackSourceBadge({ source }: { source: string | null | undefined }) {
  if (source === 'gemini') return <Badge tone="primary" icon={Bot}>AI feedback</Badge>
  if (source === 'dev_rules') return <Badge tone="warning" icon={FlaskConical}>Rule-based feedback · not AI</Badge>
  return null
}
