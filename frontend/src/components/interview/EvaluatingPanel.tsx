import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

/** Shown while a Gemini-backed request is pending (can be ~1 minute in a provider outage). */
export function EvaluatingPanel({ title }: { title: string }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const t = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => window.clearInterval(t)
  }, [])
  const detail =
    seconds < 8
      ? 'This usually takes a few seconds.'
      : seconds < 25
        ? 'Still working — the AI service can be slow at busy times. Please keep this page open.'
        : 'The AI service is taking longer than usual. If it does not respond, we will use a clearly labelled development evaluation instead. This can take up to about a minute.'
  return (
    <div role="status" aria-live="polite" className="flex items-start gap-3 rounded-card border border-primary/25 bg-primary-soft px-5 py-4">
      <Loader2 className="mt-0.5 size-5 shrink-0 animate-spin text-primary" aria-hidden />
      <div>
        <p className="font-semibold text-primary-ink">{title}</p>
        <p className="mt-0.5 text-sm text-ink-2">{detail}</p>
        <p className="mt-1 text-xs text-muted tabular">{seconds}s</p>
      </div>
    </div>
  )
}
