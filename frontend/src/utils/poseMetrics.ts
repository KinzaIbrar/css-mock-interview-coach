/**
 * Pure, documented rules that turn pose-landmark frames into a few OBSERVABLE aggregates.
 *
 * Nothing here infers emotion, confidence, honesty or personality. Landmarks are processed in the browser,
 * reduced to the numbers below and discarded; only the aggregates are ever sent to the server.
 *
 * Landmarks are normalised image coordinates {x, y, visibility} from MediaPipe Pose (indices: 0 nose, 7/8 ears,
 * 11/12 shoulders).
 */
import type { CameraAggregates } from '@/api/types'

export interface Landmark { x: number; y: number; visibility?: number }

export interface Frame {
  /** Seconds since the camera started. */
  t: number
  /** Landmarks of the first detected person, or null when nobody was detected. */
  landmarks: Landmark[] | null
}

export const VISIBLE_MIN = 0.5 // a landmark counts as seen above this visibility
export const FACING_MAX_OFFSET = 0.35 // nose offset from the ear midpoint, as a fraction of the ear-to-ear distance
export const MIN_SHOULDER_WIDTH = 0.08 // smaller than this the person is too far away to measure movement
export const STABLE_MAX = 0.04 // sway (std-dev / shoulder width) below this -> "stable"
export const MODERATE_MAX = 0.1
export const MOVE_LOW_MAX = 0.015 // mean per-sample displacement / shoulder width
export const MOVE_MODERATE_MAX = 0.04

const seen = (l?: Landmark) => !!l && (l.visibility ?? 1) >= VISIBLE_MIN

export interface FrameFacts {
  /** Nose and both eyes/ears region is visible. */
  faceVisible: boolean
  /** Head roughly pointing at the camera (null when it cannot be estimated). */
  facing: boolean | null
  /** Shoulder-midpoint position and width (null when the shoulders are not both visible). */
  shoulder: { x: number; y: number; width: number } | null
  /** 0..1 how many of the landmarks we rely on were visible. */
  quality: number
}

export function analyseFrame(landmarks: Landmark[] | null): FrameFacts {
  if (!landmarks) return { faceVisible: false, facing: null, shoulder: null, quality: 0 }
  const [nose, leftEar, rightEar, leftShoulder, rightShoulder] = [0, 7, 8, 11, 12].map((i) => landmarks[i])
  const used = [nose, leftEar, rightEar, leftShoulder, rightShoulder]
  const quality = used.filter(seen).length / used.length
  const faceVisible = seen(nose)

  let facing: boolean | null = null
  if (seen(nose) && seen(leftEar) && seen(rightEar)) {
    const span = Math.abs(rightEar.x - leftEar.x)
    if (span > 1e-6) {
      const mid = (leftEar.x + rightEar.x) / 2
      facing = Math.abs(nose.x - mid) / span <= FACING_MAX_OFFSET
    }
  } else if (seen(nose) && (seen(leftEar) !== seen(rightEar))) {
    facing = false // only one ear visible: the head is turned away
  }

  let shoulder: FrameFacts['shoulder'] = null
  if (seen(leftShoulder) && seen(rightShoulder)) {
    const width = Math.hypot(rightShoulder.x - leftShoulder.x, rightShoulder.y - leftShoulder.y)
    if (width >= MIN_SHOULDER_WIDTH) {
      shoulder = { x: (leftShoulder.x + rightShoulder.x) / 2, y: (leftShoulder.y + rightShoulder.y) / 2, width }
    }
  }
  return { faceVisible, facing, shoulder, quality }
}

const pct = (n: number, d: number) => (d > 0 ? Math.round((n / d) * 1000) / 10 : undefined)

/** Accumulates per-frame facts into counters only: no frame or landmark history is kept. */
export class ObservationAggregator {
  private samples = 0
  private usable = 0
  private visible = 0
  private facingKnown = 0
  private facingYes = 0
  private qualitySum = 0
  private lastT = 0
  private analysedSeconds = 0
  // running mean/variance (Welford) of the normalised shoulder position
  private n = 0
  private meanX = 0
  private meanY = 0
  private m2 = 0
  private prev: { x: number; y: number; width: number } | null = null
  private moveSum = 0
  private moveCount = 0

  add(frame: Frame): void {
    const facts = analyseFrame(frame.landmarks)
    const dt = Math.max(0, Math.min(frame.t - this.lastT, 1)) // cap: a stalled tab must not count as analysed time
    this.lastT = frame.t
    this.samples += 1
    this.qualitySum += facts.quality
    if (facts.faceVisible) this.visible += 1
    if (facts.facing !== null) { this.facingKnown += 1; if (facts.facing) this.facingYes += 1 }
    if (facts.quality >= 0.6) { this.usable += 1; this.analysedSeconds += dt }
    if (facts.shoulder) {
      const s = facts.shoulder
      // normalise by shoulder width so distance from the camera does not matter
      const nx = s.x / s.width
      const ny = s.y / s.width
      this.n += 1
      const dx = nx - this.meanX
      const dy = ny - this.meanY
      this.meanX += dx / this.n
      this.meanY += dy / this.n
      this.m2 += dx * (nx - this.meanX) + dy * (ny - this.meanY)
      if (this.prev) {
        this.moveSum += Math.hypot(s.x - this.prev.x, s.y - this.prev.y) / s.width
        this.moveCount += 1
      }
      this.prev = s
    }
  }

  finish(totalSeconds: number): CameraAggregates {
    const sway = this.n > 1 ? Math.sqrt(this.m2 / (this.n - 1)) : undefined
    const move = this.moveCount > 0 ? this.moveSum / this.moveCount : undefined
    return {
      enabled: true,
      total_seconds: Math.round(totalSeconds * 10) / 10,
      analysed_seconds: Math.round(Math.min(this.analysedSeconds, totalSeconds) * 10) / 10,
      samples: this.samples,
      face_visible_pct: pct(this.visible, this.samples),
      facing_camera_pct: pct(this.facingYes, this.facingKnown),
      posture_stability: sway === undefined ? undefined : sway <= STABLE_MAX ? 'stable' : sway <= MODERATE_MAX ? 'moderate' : 'variable',
      movement_level: move === undefined ? undefined : move <= MOVE_LOW_MAX ? 'low' : move <= MOVE_MODERATE_MAX ? 'moderate' : 'high',
      tracking_quality_pct: pct(this.qualitySum, this.samples),
    }
  }
}

/** Words in a dictated chunk of text (used for speaking pace; typed text is never counted). */
export const countWords = (text: string): number => (text.trim() ? text.trim().split(/\s+/).length : 0)
