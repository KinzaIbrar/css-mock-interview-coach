import { useState, type InputHTMLAttributes, type Ref } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { TextInput } from '@/components/ui/Form'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  error?: string
  hint?: string
  ref?: Ref<HTMLInputElement>
}

/** Password input with an accessible show/hide toggle. */
export function PasswordField({ ref, ...props }: Props) {
  const [visible, setVisible] = useState(false)
  return (
    <TextInput
      ref={ref}
      {...props}
      type={visible ? 'text' : 'password'}
      trailing={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-pressed={visible}
          aria-label={visible ? 'Hide password' : 'Show password'}
          className="rounded-control p-2 text-muted hover:bg-surface-2 hover:text-ink"
        >
          {visible ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
        </button>
      }
    />
  )
}
