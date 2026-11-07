import { useEffect, useRef, type KeyboardEvent, type Ref } from 'react'
import { countWords } from '@/utils/poseMetrics'
import { Send } from 'lucide-react'
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition'
import { Button } from '@/components/ui/Button'
import { TextAreaField } from '@/components/ui/Form'
import { DictationControls } from './VoiceControls'

export const MAX_ANSWER_CHARS = 8000

interface Props {
  label: string
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  submitLabel: string
  disabled?: boolean // true while a request is pending: no edits, no duplicate submit
  error?: string
  placeholder?: string
  textareaRef?: Ref<HTMLTextAreaElement>
  /** Reports dictated words / listening seconds (for the optional speaking-pace observation). Typed text is never counted. */
  onDictation?: (d: { words: number; seconds: number }) => void
}

/** Text answer box with character count, optional dictation, and a submit button that cannot double-fire. */
export function AnswerComposer({ label, value, onChange, onSubmit, submitLabel, disabled, error, placeholder, textareaRef, onDictation }: Props) {
  const valueRef = useRef(value)
  useEffect(() => { valueRef.current = value }, [value])
  const voice = useSpeechRecognition((text) => {
    onDictation?.({ words: countWords(text), seconds: 0 })
    const current = valueRef.current
    onChange(current && !/\s$/.test(current) ? `${current} ${text}` : `${current}${text}`)
  })
  const { listening, stop } = voice
  const listenStart = useRef<number | null>(null)
  useEffect(() => {
    if (listening) { listenStart.current = Date.now(); return }
    if (listenStart.current !== null) {
      onDictation?.({ words: 0, seconds: (Date.now() - listenStart.current) / 1000 })
      listenStart.current = null
    }
  }, [listening, onDictation])
  // Never keep the microphone open while a request is in flight.
  useEffect(() => { if (disabled && listening) stop() }, [disabled, listening, stop])

  const blank = value.trim().length === 0
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !disabled && !blank) { e.preventDefault(); onSubmit() }
  }

  return (
    <div className="space-y-3">
      <TextAreaField
        ref={textareaRef}
        label={label}
        hideLabel
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        maxLength={MAX_ANSWER_CHARS}
        placeholder={placeholder ?? 'Type your answer here. Explain your points as you would to an interview panel.'}
        className="min-h-48 text-[15px]"
        error={error}
        hint="Tip: Ctrl+Enter submits."
      />
      <div className="flex items-center justify-between gap-3 text-xs text-muted">
        <span className="tabular" aria-live="off">{value.length.toLocaleString()} / {MAX_ANSWER_CHARS.toLocaleString()} characters</span>
      </div>
      <DictationControls
        supported={voice.supported} listening={voice.listening} interim={voice.interim} error={voice.error}
        onStart={voice.start} onStop={voice.stop} disabled={disabled}
      />
      <div className="flex justify-end">
        <Button size="lg" onClick={onSubmit} disabled={disabled || blank} icon={<Send className="size-4" aria-hidden />}>
          {submitLabel}
        </Button>
      </div>
    </div>
  )
}
