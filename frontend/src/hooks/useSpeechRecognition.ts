import { useCallback, useEffect, useRef, useState } from 'react'

/** Minimal typing for the (still vendor-prefixed in some browsers) Web Speech recognition API. */
interface RecognitionResultItem { transcript: string }
interface RecognitionEvent {
  resultIndex: number
  results: ArrayLike<ArrayLike<RecognitionResultItem> & { isFinal: boolean }>
}
interface RecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  abort: () => void
  onstart: (() => void) | null
  onend: (() => void) | null
  onerror: ((e: { error: string }) => void) | null
  onresult: ((e: RecognitionEvent) => void) | null
}
type RecognitionCtor = new () => RecognitionLike

function getCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function describeRecognitionError(code: string): string {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone access was blocked. Allow the microphone for this site in your browser settings, or type your answer instead.'
    case 'audio-capture':
      return 'No microphone was found. Connect one, or type your answer instead.'
    case 'no-speech':
      return "We didn't hear anything. Try again, or type your answer."
    case 'network':
      return "Your browser's speech service could not be reached. Check your connection, or type your answer."
    case 'aborted':
      return ''
    default:
      return 'Voice input stopped unexpectedly. You can try again or type your answer.'
  }
}

/** Optional voice dictation. `supported` is false in browsers without the Web Speech API (e.g. Firefox). */
export function useSpeechRecognition(onFinalText: (text: string) => void, lang = 'en-US') {
  const supported = getCtor() !== null
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)
  const ref = useRef<RecognitionLike | null>(null)
  const callback = useRef(onFinalText)
  useEffect(() => { callback.current = onFinalText }, [onFinalText])

  const stop = useCallback(() => { ref.current?.stop() }, [])

  const start = useCallback(() => {
    const Ctor = getCtor()
    if (!Ctor || ref.current) return
    setError(null)
    const rec = new Ctor()
    rec.lang = lang
    rec.continuous = true
    rec.interimResults = true
    rec.onstart = () => setListening(true)
    rec.onend = () => { setListening(false); setInterim(''); ref.current = null }
    rec.onerror = (e) => { const msg = describeRecognitionError(e.error); if (msg) setError(msg) }
    rec.onresult = (e) => {
      let live = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const text = e.results[i][0].transcript
        if (e.results[i].isFinal) callback.current(text.trim())
        else live += text
      }
      setInterim(live)
    }
    ref.current = rec
    try { rec.start() } catch { ref.current = null; setError('Voice input could not start. Please try again.') }
  }, [lang])

  useEffect(() => () => { ref.current?.abort(); ref.current = null }, [])

  return { supported, listening, interim, error, start, stop, clearError: () => setError(null) }
}
