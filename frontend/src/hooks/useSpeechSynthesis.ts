import { useCallback, useEffect, useState } from 'react'

/** Optional text-to-speech for reading questions aloud. */
export function useSpeechSynthesis() {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined'
  const [speaking, setSpeaking] = useState(false)

  const stop = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  const speak = useCallback((text: string) => {
    if (!supported) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'
    u.rate = 0.95
    u.onend = () => setSpeaking(false)
    u.onerror = () => setSpeaking(false)
    setSpeaking(true)
    window.speechSynthesis.speak(u)
  }, [supported])

  useEffect(() => () => { if (supported) window.speechSynthesis.cancel() }, [supported])

  return { supported, speaking, speak, stop }
}
