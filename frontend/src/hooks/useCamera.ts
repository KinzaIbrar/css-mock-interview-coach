import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import type { CameraAggregates } from '@/api/types'
import { ObservationAggregator, type Landmark } from '@/utils/poseMetrics'

export type CameraStatus = 'off' | 'requesting' | 'on' | 'denied' | 'unsupported' | 'error'
export type TrackingStatus = 'idle' | 'loading' | 'tracking' | 'unavailable'

const SAMPLE_EVERY_MS = 200 // ~5 analyses per second keeps a low-spec laptop cool
const VISION_BASE = '/vision'

interface PoseLike {
  detectForVideo: (v: HTMLVideoElement, ts: number) => { landmarks: Landmark[][] }
  close: () => void
}

export interface CameraControls {
  status: CameraStatus
  tracking: TrackingStatus
  message: string | null
  start: () => Promise<void>
  stop: () => void
  /** Aggregates for everything observed so far (numbers only), or null if the camera was never switched on. */
  collect: () => CameraAggregates | null
}

/**
 * Consent-gated webcam preview with in-browser pose tracking (MediaPipe Tasks Vision, assets served locally).
 * Frames are processed in memory and discarded; only `collect()`'s summary numbers ever leave this hook.
 */
export function useCamera(videoRef: RefObject<HTMLVideoElement | null>): CameraControls {
  const [status, setStatus] = useState<CameraStatus>('off')
  const [tracking, setTracking] = useState<TrackingStatus>('idle')
  const [message, setMessage] = useState<string | null>(null)

  const stream = useRef<MediaStream | null>(null)
  const pose = useRef<PoseLike | null>(null)
  const timer = useRef<number | null>(null)
  const aggregator = useRef(new ObservationAggregator())
  const onSince = useRef<number | null>(null) // when the camera was last switched on
  const onSeconds = useRef(0) // accumulated camera-on time
  const everOn = useRef(false)
  const t0 = useRef(0)

  const stopLoop = () => {
    if (timer.current !== null) { window.clearInterval(timer.current); timer.current = null }
  }

  const stop = useCallback(() => {
    stopLoop()
    stream.current?.getTracks().forEach((t) => t.stop()) // the camera light goes off
    stream.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    if (onSince.current !== null) { onSeconds.current += (Date.now() - onSince.current) / 1000; onSince.current = null }
    setStatus((s) => (s === 'on' || s === 'requesting' ? 'off' : s))
    setTracking('idle')
  }, [videoRef])

  const startTracking = useCallback(async () => {
    setTracking('loading')
    try {
      const vision = await import('@mediapipe/tasks-vision')
      if (!pose.current) {
        const files = await vision.FilesetResolver.forVisionTasks(`${VISION_BASE}/wasm`)
        pose.current = (await vision.PoseLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: `${VISION_BASE}/pose_landmarker_lite.task`, delegate: 'CPU' },
          runningMode: 'VIDEO',
          numPoses: 1,
        })) as unknown as PoseLike
      }
      if (!stream.current) return // switched off while loading
      setTracking('tracking')
      t0.current = performance.now()
      timer.current = window.setInterval(() => {
        const v = videoRef.current
        if (!v || v.readyState < 2 || !pose.current) return
        try {
          const res = pose.current.detectForVideo(v, performance.now())
          aggregator.current.add({ t: (performance.now() - t0.current) / 1000, landmarks: res.landmarks[0] ?? null })
        } catch {
          // a single failed frame is simply not counted
        }
      }, SAMPLE_EVERY_MS)
    } catch {
      setTracking('unavailable') // preview still works; metrics will say "Not enough data"
      setMessage('Posture tracking could not start (the tracking files may be missing). The preview still works, but no body metrics will be recorded.')
    }
  }, [videoRef])

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) { setStatus('unsupported'); setMessage("This browser can't access a camera."); return }
    setStatus('requesting')
    setMessage(null)
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240, facingMode: 'user' }, audio: false })
      stream.current = s
      if (videoRef.current) {
        videoRef.current.srcObject = s
        await videoRef.current.play().catch(() => undefined)
      }
      everOn.current = true
      onSince.current = Date.now()
      setStatus('on')
      void startTracking()
    } catch (e) {
      const name = (e as DOMException)?.name
      if (name === 'NotAllowedError' || name === 'SecurityError') { setStatus('denied'); setMessage('Camera permission was denied. You can continue without it, or allow the camera in your browser and try again.') }
      else if (name === 'NotFoundError') { setStatus('error'); setMessage('No camera was found on this device.') }
      else { setStatus('error'); setMessage('The camera could not be started. It may be in use by another app.') }
    }
  }, [videoRef, startTracking])

  const collect = useCallback((): CameraAggregates | null => {
    if (!everOn.current) return null
    const running = onSince.current !== null ? (Date.now() - onSince.current) / 1000 : 0
    return aggregator.current.finish(onSeconds.current + running)
  }, [])

  // Always release the camera when leaving the page.
  useEffect(() => () => {
    stopLoop()
    stream.current?.getTracks().forEach((t) => t.stop())
    pose.current?.close()
    pose.current = null
  }, [])

  return { status, tracking, message, start, stop, collect }
}
