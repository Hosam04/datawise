import {
  ListCardSkeletonGroup,
  ListToolbarSkeleton,
  StatCardSkeletonGroup,
} from '@/components/datawise/card-skeleton'
import { DetailPageSkeleton } from '@/components/datawise/detail-page-skeleton'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

function LoadingShell({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'animate-in fade-in duration-300 motion-reduce:animate-none',
        className,
      )}
      aria-busy="true"
      aria-label="Loading page"
    >
      {children}
    </div>
  )
}

export function DashboardPageLoading() {
  return (
    <LoadingShell className="space-y-8 p-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <StatCardSkeletonGroup />
      <section className="rounded-xl border border-border bg-card p-6">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="mt-2 h-4 w-48" />
        <div className="mt-4 flex gap-3">
          <Skeleton className="h-9 w-24 rounded-lg" />
          <Skeleton className="h-9 w-36 rounded-lg" />
        </div>
      </section>
      <section className="space-y-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-56" />
        <ListCardSkeletonGroup count={3} />
      </section>
    </LoadingShell>
  )
}

export function ListPageLoading() {
  return (
    <LoadingShell className="space-y-6 p-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-44" />
        <Skeleton className="h-4 w-80" />
      </div>
      <ListToolbarSkeleton />
      <ListCardSkeletonGroup count={5} spacing="md" padding="md" />
    </LoadingShell>
  )
}

export function DetailPageLoading() {
  return (
    <LoadingShell>
      <DetailPageSkeleton />
    </LoadingShell>
  )
}

export function ChatPageLoading() {
  return (
    <LoadingShell className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col border-r border-border p-4">
        <Skeleton className="h-8 w-48" />
        <div className="mt-6 flex-1 space-y-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-20 w-full rounded-xl" />
          ))}
        </div>
        <Skeleton className="mt-4 h-12 w-full rounded-xl" />
      </div>

      <div className="hidden w-full max-w-md flex-col border-l border-border p-4 xl:flex">
        <Skeleton className="h-8 w-36" />
        <div className="mt-4 flex gap-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-8 w-20 rounded-lg" />
          ))}
        </div>
        <Skeleton className="mt-4 h-64 w-full rounded-xl" />
      </div>
    </LoadingShell>
  )
}

export function UploadPageLoading() {
  return (
    <LoadingShell className="h-full p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="space-y-2 text-center">
          <Skeleton className="mx-auto h-9 w-56" />
          <Skeleton className="mx-auto h-4 w-80 max-w-full" />
        </div>
        <Skeleton className="h-64 w-full rounded-xl" />
        <div className="flex justify-center gap-3">
          <Skeleton className="h-10 w-28 rounded-lg" />
          <Skeleton className="h-10 w-32 rounded-lg" />
        </div>
      </div>
    </LoadingShell>
  )
}

export function SettingsPageLoading() {
  return (
    <LoadingShell className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-4 w-72" />
      </div>

      {Array.from({ length: 3 }, (_, index) => (
        <section
          key={index}
          className="rounded-xl border border-border bg-card p-6"
        >
          <Skeleton className="h-6 w-36" />
          <Skeleton className="mt-2 h-4 w-64" />
          <div className="mt-4 flex flex-wrap gap-3">
            <Skeleton className="h-10 w-28 rounded-lg" />
            <Skeleton className="h-10 w-32 rounded-lg" />
          </div>
        </section>
      ))}
    </LoadingShell>
  )
}

export function ProfilePageLoading() {
  return (
    <LoadingShell className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-4 w-72" />
      </div>

      {Array.from({ length: 2 }, (_, index) => (
        <section
          key={index}
          className="rounded-xl border border-border bg-card p-6"
        >
          <Skeleton className="h-6 w-36" />
          <Skeleton className="mt-2 h-4 w-64" />
          {index === 0 ? (
            <div className="mt-4 flex items-center gap-4">
              <Skeleton className="size-16 rounded-full" />
              <div className="flex-1 space-y-3">
                <Skeleton className="h-9 w-full rounded-lg" />
                <Skeleton className="h-9 w-24 rounded-lg" />
              </div>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <Skeleton className="h-9 w-full rounded-lg" />
              <Skeleton className="h-4 w-40" />
            </div>
          )}
        </section>
      ))}
    </LoadingShell>
  )
}
