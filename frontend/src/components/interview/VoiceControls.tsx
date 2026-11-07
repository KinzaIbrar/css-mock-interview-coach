import { Mic, MicOff, Square, Volume2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Feedback'

interface Props {
  supported: boolean
  listening: boolean
  interim: string
  error: string | null
  onStart: () => void
  onStop: () => void
  disabled?: boolean
}

/** Optional dictation controls. Typing always works; this never replaces the text box. */
export function DictationControls({ supported, listening, interim, error, onStart, onStop, disabled }: Props) {
  if (!supported) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted">
        <MicOff className="size-4" aria-hidden />
        Voice dictation isn't supported in this browser (it works in recent Chrome and Edge). You can type your answer.
      </p>
    )
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        {listening ? (
          <Button variant="danger" size="sm" onClick={onStop} icon={<Square className="size-3.5 fill-current" aria-hidden />}>Stop dictation</Button>
        ) : (
          <Button variant="secondary" size="sm" onClick={onStart} disabled={disabled} icon={<Mic className="size-4" aria-hidden />}>Dictate answer</Button>
        )}
        {listening && (
          <span role="status" className="inline-flex items-center gap-2 text-sm font-medium text-danger">
            <span className="relative flex size-2.5"><span className="absolute inline-flex size-full animate-ping rounded-full bg-danger opacity-60" /><span className="relative inline-flex size-2.5 rounded-full bg-danger" /></span>
            Listening — speak your answer
          </span>
        )}
      </div>
      {listening && interim && <p className="text-sm italic text-muted" aria-live="off">“{interim}”</p>}
      {!listening && !error && <p className="text-xs text-muted">Optional. Your browser may send audio to its own speech service to transcribe it; the text appears in the box so you can edit it.</p>}
      {error && <Alert tone="warning" live="alert">{error}</Alert>}
    </div>
  )
}

export function ReadAloudButton({ supported, speaking, onSpeak, onStop }: { supported: boolean; speaking: boolean; onSpeak: () => void; onStop: () => void }) {
  if (!supported) return null
  return speaking ? (
    <Button variant="ghost" size="sm" onClick={onStop} icon={<Square className="size-3.5 fill-current" aria-hidden />}>Stop reading</Button>
  ) : (
    <Button variant="ghost" size="sm" onClick={onSpeak} icon={<Volume2 className="size-4" aria-hidden />}>Read aloud</Button>
  )
}
