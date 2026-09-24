import { AlertCircle, CheckCircle2, Loader2, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

interface UploadProgressProps {
  progress: number
  status: 'idle' | 'uploading' | 'processing' | 'completed' | 'error'
  fileName?: string
  errorMessage?: string
}

export function UploadProgress({
  progress,
  status,
  fileName,
  errorMessage,
}: UploadProgressProps) {
  const isComplete = status === 'completed'
  const isProcessing = status === 'processing'
  const isUploading = status === 'uploading'
  const isError = status === 'error'

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl border bg-card p-3 shadow-sm transition-all',
        isComplete
          ? 'border-emerald-500/20 bg-emerald-500/[0.03]'
          : isError
            ? 'border-red-500/20 bg-red-500/[0.03]'
            : isProcessing
              ? 'border-primary/20 bg-primary/[0.03]'
              : 'border-border/60',
      )}
    >
      {isProcessing && (
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-primary/5" />
      )}

      <div className="relative flex items-start gap-3">
        <div
          className={cn(
            'flex size-8 shrink-0 items-center justify-center rounded-lg',
            isComplete
              ? 'bg-emerald-500/10'
              : isError
                ? 'bg-red-500/10'
                : isProcessing
                  ? 'bg-primary/10'
                  : 'bg-muted',
          )}
        >
          {isComplete ? (
            <CheckCircle2 className="size-4 text-emerald-500" />
          ) : isError ? (
            <AlertCircle className="size-4 text-red-500" />
          ) : isProcessing ? (
            <Sparkles className="size-4 text-primary animate-pulse" />
          ) : (
            <Loader2 className="size-4 animate-spin text-primary" />
          )}
        </div>

        <div className="min-w-0 flex-1 pt-0.5">
          <div className="flex items-center justify-between gap-2">
            <p
              className={cn(
                'text-sm font-semibold',
                isComplete
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : isError
                    ? 'text-red-500'
                    : 'text-foreground',
              )}
            >
              {isComplete
                ? 'Analysis Complete'
                : isError
                  ? 'Analysis Failed'
                  : isProcessing
                    ? 'Processing Dataset...'
                    : 'Uploading Dataset...'}
            </p>

            <div className="shrink-0">
              {isUploading && (
                <span className="text-xs font-mono font-semibold tabular-nums text-foreground">
                  {progress}%
                </span>
              )}
              {isProcessing && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-semibold text-primary">
                  <span className="relative flex size-1.5">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-75" />
                    <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
                  </span>
                  Analyzing
                </span>
              )}
              {isComplete && (
                <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                  100%
                </span>
              )}
            </div>
          </div>

          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {isComplete
              ? fileName
                ? `${fileName} is ready.`
                : 'Your dataset is ready.'
              : isError
                ? errorMessage || 'Something went wrong.'
                : isProcessing
                  ? 'AI agents are analyzing your data...'
                  : fileName || 'Sending file to server...'}
          </p>
        </div>
      </div>

      
      <div className="relative mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
        {isProcessing ? (
          <div className="h-full w-2/5 animate-[progress_1.6s_ease-in-out_infinite] rounded-full bg-primary" />
        ) : isError ? (
          <div className="h-full w-full rounded-full bg-red-500/40" />
        ) : (
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500 ease-out',
              isComplete
                ? 'bg-emerald-500'
                : 'bg-primary',
            )}
            style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
          />
        )}
      </div>
    </div>
  )
}