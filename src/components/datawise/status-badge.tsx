import { cn } from '@/lib/utils'
import { focusRing } from '@/lib/ui-styles'

interface StatusBadgeProps {
  status: string
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const normalized = status.toLowerCase()

  return (
    <span
      className={cn(
        'inline-flex rounded-full px-3 py-1 text-sm font-medium',
        focusRing,
        normalized === 'analyzed' && 'bg-primary/10 text-primary',
        normalized === 'processing' &&
          'bg-amber-500/10 text-amber-700 dark:text-amber-400',
        normalized !== 'analyzed' &&
          normalized !== 'processing' &&
          'bg-muted text-muted-foreground',
        className,
      )}
    >
      {status}
    </span>
  )
}
