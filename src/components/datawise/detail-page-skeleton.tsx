import { Skeleton } from '@/components/ui/skeleton'

export function DetailPageSkeleton() {
  return (
    <div
      className="mx-auto max-w-5xl space-y-6 p-6"
      aria-busy="true"
      aria-label="Loading details"
    >
      <Skeleton className="h-4 w-48" />

      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-start gap-4">
          <Skeleton className="size-14 rounded-xl" />
          <div className="flex-1 space-y-3">
            <Skeleton className="h-8 w-2/3 max-w-md" />
            <Skeleton className="h-5 w-32 rounded-full" />
            <Skeleton className="h-4 w-40" />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <Skeleton className="h-6 w-28" />
        <Skeleton className="mt-2 h-4 w-56" />
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-16 rounded-lg" />
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="mt-4 h-20 w-full" />
      </div>

      <div className="flex flex-wrap gap-3">
        <Skeleton className="h-10 w-36 rounded-lg" />
        <Skeleton className="h-10 w-40 rounded-lg" />
        <Skeleton className="h-10 w-32 rounded-lg" />
      </div>
    </div>
  )
}
