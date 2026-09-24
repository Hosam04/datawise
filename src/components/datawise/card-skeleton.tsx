import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface ListCardSkeletonProps {
  className?: string
  padding?: 'sm' | 'md'
}

export function ListCardSkeleton({
  className,
  padding = 'sm',
}: ListCardSkeletonProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between rounded-xl border border-border bg-card',
        padding === 'md' ? 'p-5' : 'p-4',
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-4">
        <Skeleton className="size-10 shrink-0 rounded-lg" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-44 max-w-[50vw]" />
          <Skeleton className="h-3 w-28" />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Skeleton className="hidden h-7 w-20 rounded-full sm:block" />
        <Skeleton className="size-8 rounded-lg" />
        <Skeleton className="size-8 rounded-lg" />
      </div>
    </div>
  )
}

interface ListCardSkeletonGroupProps {
  count?: number
  className?: string
  itemClassName?: string
  spacing?: 'sm' | 'md'
  padding?: 'sm' | 'md'
}

export function ListCardSkeletonGroup({
  count = 3,
  className,
  itemClassName,
  spacing = 'sm',
  padding = 'sm',
}: ListCardSkeletonGroupProps) {
  return (
    <div
      className={cn(spacing === 'md' ? 'space-y-4' : 'space-y-3', className)}
      aria-busy="true"
      aria-label="Loading content"
    >
      {Array.from({ length: count }, (_, index) => (
        <ListCardSkeleton
          key={index}
          className={itemClassName}
          padding={padding}
        />
      ))}
    </div>
  )
}

export function StatCardSkeleton({ className }: { className?: string }) {
  const skeletonClassName = cn(
    'rounded-xl border border-border bg-card p-5 block',
    className,
  )

  return (
    <div className={skeletonClassName} aria-hidden="true">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-3">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-8 w-12" />
        </div>
        <Skeleton className="size-10 rounded-lg" />
      </div>
    </div>
  )
}
export function StatCardSkeletonGroup({
  count = 3,
  className,
}: {
  count?: number
  className?: string
}) {
  return (
    <div className={cn('grid gap-4 sm:grid-cols-3', className)}>
      {Array.from({ length: count }, (_, index) => (
        <StatCardSkeleton key={index} />
      ))}
    </div>
  )
}

export function DatasetSwitcherSkeleton() {
  return (
    <Skeleton className="h-9 w-full max-w-30 rounded-lg min-[420px]:max-w-40 sm:max-w-45" />
  )
}

export function ListToolbarSkeleton() {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <Skeleton className="h-10 w-full max-w-md rounded-lg" />
      <div className="flex gap-2">
        <Skeleton className="h-10 w-28 rounded-lg" />
        <Skeleton className="h-10 w-36 rounded-lg" />
      </div>
    </div>
  )
}
