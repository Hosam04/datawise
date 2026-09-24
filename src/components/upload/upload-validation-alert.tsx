'use client'

import { AlertCircle, X } from 'lucide-react'
import type { UploadValidationError } from '@/lib/upload-utils'
import { IconTooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

const errorTitles: Record<UploadValidationError, string> = {
  unsupported: 'Unsupported file type',
  too_large: 'File too large',
}

interface UploadValidationAlertProps {
  error: UploadValidationError
  message: string
  onDismiss?: () => void
  className?: string
}

export function UploadValidationAlert({
  error,
  message,
  onDismiss,
  className,
}: UploadValidationAlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3',
        className,
      )}
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-destructive">
          {errorTitles[error]}
        </p>
        <p className="mt-0.5 text-sm text-muted-foreground">{message}</p>
      </div>

      {onDismiss && (
        <IconTooltip
          label="Dismiss error"
          onClick={onDismiss}
          side="top"
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-foreground"
        >
          <X className="size-4" />
        </IconTooltip>
      )}
    </div>
  )
}
