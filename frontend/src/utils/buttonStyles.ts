import { cn } from './cn'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent'
export type ButtonSize = 'sm' | 'md' | 'lg'

const base =
  'inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-colors select-none ' +
  'disabled:cursor-not-allowed disabled:opacity-55 whitespace-nowrap'

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-hover shadow-card',
  secondary: 'bg-surface text-ink border border-line-strong hover:bg-surface-2 shadow-card',
  ghost: 'text-ink-2 hover:bg-surface-2 hover:text-ink',
  danger: 'bg-danger text-white hover:opacity-90 shadow-card',
  /** The brand lime accent: reserved for CTAs on a dark (primary) background, never for plain-surface buttons. */
  accent: 'bg-accent text-accent-ink hover:bg-accent/90 shadow-card',
}
const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-3.5 text-sm',
  md: 'h-10 px-5 text-sm',
  lg: 'h-12 px-7 text-base',
}

export const buttonClass = (variant: ButtonVariant = 'primary', size: ButtonSize = 'md', extra?: string) =>
  cn(base, variants[variant], sizes[size], extra)
