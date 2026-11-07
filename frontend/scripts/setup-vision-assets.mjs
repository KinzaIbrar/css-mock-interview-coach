// Copies the MediaPipe WASM runtime from node_modules and downloads the (Apache-2.0) Pose Landmarker "lite" model
// into public/vision/, so the camera features run from LOCAL files (no CDN at runtime). Never fails the build:
// without these files the camera preview still works and the report says "Not enough data".
import { cpSync, existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const out = join(root, 'public', 'vision')
const wasmSrc = join(root, 'node_modules', '@mediapipe', 'tasks-vision', 'wasm')
const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'

try {
  if (existsSync(wasmSrc) && !existsSync(join(out, 'wasm'))) {
    mkdirSync(out, { recursive: true })
    cpSync(wasmSrc, join(out, 'wasm'), { recursive: true })
    console.log('[vision] copied MediaPipe WASM runtime')
  }
  const model = join(out, 'pose_landmarker_lite.task')
  if (!existsSync(model)) {
    mkdirSync(out, { recursive: true })
    const res = await fetch(MODEL_URL)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    writeFileSync(model, Buffer.from(await res.arrayBuffer()))
    console.log('[vision] downloaded pose_landmarker_lite.task')
  }
} catch (e) {
  console.warn(`[vision] could not prepare camera tracking assets (${e instanceof Error ? e.message : e}). The camera preview will work; body metrics will be unavailable.`)
}
