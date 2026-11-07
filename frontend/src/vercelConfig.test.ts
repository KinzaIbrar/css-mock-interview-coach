import { describe, expect, it } from 'vitest'
import raw from '../vercel.json?raw'

describe('vercel.json', () => {
  const config = JSON.parse(raw)

  it('is valid JSON with an SPA fallback that never swallows the API, assets or the vision files', () => {
    const rule = new RegExp(`^${config.rewrites[0].source}$`)
    expect(config.rewrites[0].destination).toBe('/index.html')
    for (const deepLink of ['/interviews/3/results', '/login', '/history']) expect(rule.test(deepLink)).toBe(true)
    for (const real of ['/api/health', '/assets/index-abc.js', '/vision/pose_landmarker_lite.task', '/favicon.svg']) expect(rule.test(real)).toBe(false)
  })

  it('allows camera and microphone for the app itself only', () => {
    const headers = config.headers[0].headers as { key: string; value: string }[]
    expect(headers.find((h) => h.key === 'Permissions-Policy')?.value).toContain('camera=(self)')
  })
})
