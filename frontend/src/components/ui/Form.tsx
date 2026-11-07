import { useId, type InputHTMLAttributes, type ReactNode, type Ref, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

const control =
  'block w-full rounded-control border bg-surface px-3 text-sm text-ink placeholder:text-muted/80 ' +
  'transition-colors hover:border-line-strong disabled:cursor-not-allowed disabled:bg-surface-2 disabled:opacity-70'
const controlBorder = (invalid?: boolean) => (invalid ? 'border-danger' : 'border-line-strong')

interface FieldProps {
  label: string
  htmlFor: string
  error?: string
  hint?: ReactNode
  children: ReactNode
  className?: string
}

/** Label + control + hint + error, wired together for screen readers. */
export function Field({ label, htmlFor, error, hint, children, className }: FieldProps) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-ink">{label}</label>
      {children}
      {hint && !error && <p id={`${htmlFor}-hint`} className="mt-1.5 text-xs text-muted">{hint}</p>}
      {error && <p id={`${htmlFor}-error`} role="alert" className="mt-1.5 text-xs font-medium text-danger">{error}</p>}
    </div>
  )
}

function describedBy(id: string, error?: string, hint?: ReactNode) {
  return error ? `${id}-error` : hint ? `${id}-hint` : undefined
}

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: ReactNode
  ref?: Ref<HTMLInputElement>
  trailing?: ReactNode
}

export function TextInput({ label, error, hint, className, id, trailing, ref, ...rest }: TextInputProps) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <Field label={label} htmlFor={fid} error={error} hint={hint}>
      <div className="relative">
        <input
          id={fid}
          ref={ref}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(fid, error, hint)}
          className={cn(control, 'h-10', controlBorder(!!error), trailing ? 'pr-11' : false, className)}
          {...rest}
        />
        {trailing && <div className="absolute inset-y-0 right-1 flex items-center">{trailing}</div>}
      </div>
    </Field>
  )
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  error?: string
  hint?: ReactNode
  ref?: Ref<HTMLSelectElement>
}

export function SelectField({ label, error, hint, className, id, children, ref, ...rest }: SelectFieldProps) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <Field label={label} htmlFor={fid} error={error} hint={hint}>
      <select
        id={fid}
        ref={ref}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fid, error, hint)}
        className={cn(control, 'h-10', controlBorder(!!error), className)}
        {...rest}
      >
        {children}
      </select>
    </Field>
  )
}

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  error?: string
  hint?: ReactNode
  ref?: Ref<HTMLTextAreaElement>
  hideLabel?: boolean
}

export function TextAreaField({ label, error, hint, className, id, ref, hideLabel, ...rest }: TextAreaProps) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <div>
      <label htmlFor={fid} className={hideLabel ? 'sr-only' : 'mb-1.5 block text-sm font-medium text-ink'}>{label}</label>
      <textarea
        id={fid}
        ref={ref}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fid, error, hint)}
        className={cn(control, 'min-h-40 resize-y py-2.5 leading-relaxed', controlBorder(!!error), className)}
        {...rest}
      />
      {hint && !error && <p id={`${fid}-hint`} className="mt-1.5 text-xs text-muted">{hint}</p>}
      {error && <p id={`${fid}-error`} role="alert" className="mt-1.5 text-xs font-medium text-danger">{error}</p>}
    </div>
  )
}
