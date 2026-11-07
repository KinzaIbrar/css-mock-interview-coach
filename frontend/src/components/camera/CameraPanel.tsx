import { Camera, CameraOff, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { CameraControls } from '@/hooks/useCamera'

interface Props {
  camera: CameraControls
  videoRef: React.RefObject<HTMLVideoElement | null>
}

/** Optional camera with explicit consent. Nothing is requested until the user presses "Turn on camera". */
export function CameraPanel({ camera, videoRef }: Props) {
  const { status, tracking, message } = camera
  const on = status === 'on'
  return (
    <section aria-label="Camera (optional)" className="rounded-xl border border-line bg-surface p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Camera <span className="font-normal text-muted">(optional)</span></h2>
        {on && <span className="inline-flex items-center gap-1.5 text-xs font-medium text-danger" role="status"><span className="size-2 rounded-full bg-danger" />Camera on</span>}
      </div>

      <div className={on ? 'overflow-hidden rounded-lg bg-black' : 'hidden'}>
        <video ref={videoRef} muted playsInline className="aspect-[4/3] w-full -scale-x-100 object-cover" aria-label="Your camera preview" />
      </div>

      {!on && (
        <div className="space-y-2 text-xs text-muted" data-testid="camera-consent">
          <p className="flex gap-2"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            <span>
              If you turn this on, your browser analyses the video <strong className="text-ink">on your device only</strong> to note simple
              observable things (face visible, facing the camera, posture steadiness, movement). Video and images are never uploaded or stored; only
              summary numbers are saved with your report. It does <strong className="text-ink">not</strong> judge emotions, confidence or honesty.
            </span>
          </p>
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {on ? (
          <Button variant="secondary" size="sm" onClick={camera.stop} icon={<CameraOff className="size-4" aria-hidden />}>Turn off camera</Button>
        ) : (
          <Button variant="secondary" size="sm" onClick={() => void camera.start()} loading={status === 'requesting'} disabled={status === 'unsupported'} icon={<Camera className="size-4" aria-hidden />}>
            {status === 'off' ? 'Turn on camera' : 'Try again'}
          </Button>
        )}
      </div>

      {on && tracking === 'loading' && <p className="mt-2 text-xs text-muted" role="status">Loading posture tracking…</p>}
      {on && tracking === 'tracking' && <p className="mt-2 text-xs text-muted">Tracking in your browser. Nothing is uploaded.</p>}
      {message && <p className="mt-2 text-xs text-warning" role="alert">{message}</p>}
    </section>
  )
}
