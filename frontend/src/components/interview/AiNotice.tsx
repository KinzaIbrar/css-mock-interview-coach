import { Alert } from '@/components/ui/Feedback'

/** What the user must know about how their answer was (or was not) evaluated by AI. */
export function AiNotice({ source, notice, unknown }: { source: string | null; notice: string | null; unknown?: boolean }) {
  if (unknown) {
    return (
      <Alert tone="warning" title="Your answer was saved">
        We could not show how it was evaluated here (the page reconnected after a dropped connection, or the answer was already recorded from another tab). The evaluation details will appear in your report.
      </Alert>
    )
  }
  if (notice) {
    return (
      <Alert tone="warning" title="Not evaluated by AI">
        {notice}
      </Alert>
    )
  }
  if (source === 'gemini') {
    return <Alert tone="info" live="off">Evaluated by the AI. Your scores and feedback will be in your report when you finish.</Alert>
  }
  return null
}
