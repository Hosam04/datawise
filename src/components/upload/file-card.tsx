'use client'



import { CheckCircle2, X } from 'lucide-react'

import { FileTypeIcon } from '@/components/upload/file-type-icon'

import { formatFileSize, getFileKind, getFileKindLabel } from '@/lib/upload-utils'

import { cn } from '@/lib/utils'
import { IconTooltip } from '@/components/ui/tooltip'



interface FileCardProps {

  file: File

  onRemove: () => void

  disableRemove?: boolean

  variant?: 'default' | 'success'

}



export function FileCard({

  file,

  onRemove,

  disableRemove = false,

  variant = 'default',

}: FileCardProps) {

  const kind = getFileKind(file)

  const isSuccess = variant === 'success'



  return (

    <div

      className={cn(

        'flex items-center justify-between rounded-xl border bg-card p-4 shadow-sm',

        isSuccess

          ? 'border-emerald-500/30 bg-emerald-500/5'

          : 'border-border',

      )}

    >

      <div className="flex min-w-0 items-center gap-3">

        {kind ? (

          <FileTypeIcon kind={kind} />

        ) : (

          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">

            <CheckCircle2 className="size-5 text-primary" />

          </div>

        )}



        <div className="min-w-0">

          <div className="flex items-center gap-2">

            <h3 className="truncate text-sm font-medium text-foreground">

              {file.name}

            </h3>



            {isSuccess && (

              <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />

            )}

          </div>



          <p className="text-xs text-muted-foreground">

            {formatFileSize(file.size)}

            {kind && ` · ${getFileKindLabel(kind)}`}

          </p>

        </div>

      </div>



      {!isSuccess && (
        <IconTooltip
          label="Remove file"
          onClick={onRemove}
          disabled={disableRemove}
          side="top"
          className="rounded-lg p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
        >
          <X className="size-4" />
        </IconTooltip>
      )}

    </div>

  )

}

