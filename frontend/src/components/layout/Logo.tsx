import { cn } from '@/utils/cn'

/** Simple wordmark: a speech-bubble mark + name. Pure SVG, no external assets. */
export function Logo({ className, inverted }: { className?: string; inverted?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="8" fill={inverted ? '#ffffff' : '#1d4ed8'} />
        <path d="M9 11.5A2.5 2.5 0 0 1 11.5 9h9a2.5 2.5 0 0 1 2.5 2.5v6a2.5 2.5 0 0 1-2.5 2.5H15l-3.6 3a.5.5 0 0 1-.82-.38V20A2.5 2.5 0 0 1 9 17.5z" fill={inverted ? '#1d4ed8' : '#ffffff'} />
      </svg>
      <span className={cn('text-[15px] font-semibold leading-tight tracking-tight', inverted ? 'text-white' : 'text-ink')}>
        CSS Mock Interview
        <span className={cn('block text-xs font-medium', inverted ? 'text-white/70' : 'text-muted')}>Coach</span>
      </span>
    </span>
  )
}
