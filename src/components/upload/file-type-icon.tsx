import { FileBraces, Sheet, Table2 } from 'lucide-react'
import type { FileKind } from '@/lib/upload-utils'
import { cn } from '@/lib/utils'

const fileKindConfig: Record<
  FileKind,
  {
    icon: typeof Table2
    label: string
    iconClassName: string
    containerClassName: string
  }
> = {
  csv: {
    icon: Table2,
    label: 'CSV',
    iconClassName: 'text-sky-600 dark:text-sky-400',
    containerClassName: 'bg-sky-500/10',
  },
  excel: {
    icon: Sheet,
    label: 'Excel',
    iconClassName: 'text-emerald-600 dark:text-emerald-400',
    containerClassName: 'bg-emerald-500/10',
  },
  json: {
    icon: FileBraces,
    label: 'JSON',
    iconClassName: 'text-amber-600 dark:text-amber-400',
    containerClassName: 'bg-amber-500/10',
  },
}

interface FileTypeIconProps {
  kind: FileKind
  size?: 'sm' | 'md'
  showLabel?: boolean
  className?: string
}

export function FileTypeIcon({
  kind,
  size = 'md',
  showLabel = false,
  className,
}: FileTypeIconProps) {
  const config = fileKindConfig[kind]
  const Icon = config.icon
  const boxSize = size === 'sm' ? 'size-8' : 'size-10'
  const iconSize = size === 'sm' ? 'size-4' : 'size-5'

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div
        className={cn(
          'flex shrink-0 items-center justify-center rounded-lg',
          boxSize,
          config.containerClassName,
        )}
      >
        <Icon className={cn(iconSize, config.iconClassName)} aria-hidden="true" />
      </div>

      {showLabel && (
        <span className="text-xs font-medium text-muted-foreground">
          {config.label}
        </span>
      )}
    </div>
  )
}
