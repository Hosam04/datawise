import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: React.ReactNode
  className?: string
  centered?: boolean
}

export function PageHeader({
  title,
  description,
  actions,
  className,
  centered = false,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between',
        centered && 'sm:flex-col sm:items-center sm:text-center',
        className,
      )}
    >
      <div className={cn(centered && 'max-w-xl')}>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {title}
        </h1>
        {description && (
          <p className="mt-2 text-muted-foreground">{description}</p>
        )}
      </div>

      {actions && (
        <div className={cn('flex shrink-0 flex-wrap items-center gap-2', centered && 'justify-center')}>
          {actions}
        </div>
      )}
    </div>
  )
}