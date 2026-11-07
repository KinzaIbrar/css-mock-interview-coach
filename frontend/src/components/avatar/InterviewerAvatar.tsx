import { Component, lazy, Suspense, useMemo, type ReactNode } from 'react'
import { Square, UserRound, Volume2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export type AvatarState = 'idle' | 'speaking' | 'listening' | 'waiting'

const AvatarScene = lazy(() => import('./AvatarScene'))

export function webglAvailable(): boolean {
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') || c.getContext('webgl'))
  } catch {
    return false
  }
}

const LABEL: Record<AvatarState, string> = {
  idle: 'Ready',
  speaking: 'Speaking',
  listening: 'Listening',
  waiting: 'Waiting',
}

/** Simple 2D stand-in used when WebGL is missing or the 3D scene fails. Same states, no pretending. */
function FlatAvatar({ state }: { state: AvatarState }) {
  return (
    <div className="grid h-full w-full place-items-center bg-primary-soft" data-testid="avatar-fallback">
      <span className={`grid size-24 place-items-center rounded-full bg-primary text-white ${state === 'speaking' ? 'animate-pulse' : ''}`}>
        <UserRound className="size-12" aria-hidden />
      </span>
    </div>
  )
}

class SceneBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

interface Props {
  state: AvatarState
  /** Text currently being read (shown as a caption, in sync with the speech). */
  caption?: string | null
  speechSupported: boolean
  speaking: boolean
  onRepeat?: () => void
  onStop?: () => void
}

/**
 * The interviewer avatar. The mouth moves in an approximate open/close rhythm while the browser reads text aloud;
 * this is NOT phoneme/viseme lip-sync (the Web Speech API exposes no audio or phoneme data).
 */
export function InterviewerAvatar({ state, caption, speechSupported, speaking, onRepeat, onStop }: Props) {
  const webgl = useMemo(() => webglAvailable(), [])
  const flat = <FlatAvatar state={state} />
  return (
    <section aria-label="Interviewer" className="overflow-hidden rounded-xl border border-line bg-surface">
      <div className="relative aspect-[4/3] w-full bg-gradient-to-b from-primary-soft to-surface">
        {webgl ? (
          <SceneBoundary fallback={flat}>
            <Suspense fallback={flat}><AvatarScene state={state} /></Suspense>
          </SceneBoundary>
        ) : flat}
        <span className="absolute left-2 top-2 rounded-full bg-surface/90 px-2.5 py-0.5 text-xs font-medium text-ink shadow-sm" role="status">
          Interviewer · {LABEL[state]}
        </span>
      </div>
      <div className="space-y-2 p-3">
        {caption && <p className="text-sm leading-snug text-ink" data-testid="avatar-caption">{caption}</p>}
        <div className="flex flex-wrap items-center gap-2">
          {speechSupported ? (
            speaking ? (
              <Button variant="secondary" size="sm" onClick={onStop} icon={<Square className="size-3.5 fill-current" aria-hidden />}>Stop speaking</Button>
            ) : (
              <Button variant="secondary" size="sm" onClick={onRepeat} icon={<Volume2 className="size-4" aria-hidden />}>Repeat question</Button>
            )
          ) : (
            <p className="text-xs text-muted">Spoken questions aren't supported in this browser; read the text instead.</p>
          )}
        </div>
        <p className="text-[11px] leading-snug text-muted">
          {webgl ? 'Mouth movement is approximate, not exact lip-sync.' : '3D avatar unavailable here (WebGL not supported) — showing a simple stand-in.'}
        </p>
      </div>
    </section>
  )
}
