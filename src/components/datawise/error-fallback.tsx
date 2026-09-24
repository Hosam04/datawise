'use client'

import { AlertTriangle, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { focusRing } from '@/lib/ui-styles'
import { cn } from '@/lib/utils'

interface ErrorFallbackProps {
  title?: string
  description?: string
  onReset?: () => void
  className?: string
}

export function ErrorFallback({
  title = 'Something went wrong',
  description = 'An unexpected error occurred. Try again or return to the dashboard.',
  onReset,
  className,
}: ErrorFallbackProps) {
  return (
    <div
      className={cn(
        'flex min-h-[320px] items-center justify-center p-6',
        className,
      )}
    >
      <div className="max-w-md rounded-xl border border-destructive/30 bg-card p-8 text-center">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-destructive/10">
          <AlertTriangle className="size-7 text-destructive" />
        </div>

        <h2 className="mt-4 text-xl font-semibold text-foreground">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>

        {onReset && (
          <Button
            type="button"
            onClick={onReset}
            className={cn('mt-5 gap-2', focusRing)}
          >
            <RotateCcw className="size-4" />
            Try again
          </Button>
        )}
      </div>
    </div>
  )
}
