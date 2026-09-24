'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Database, FileText, Star, Upload } from 'lucide-react'
import { StatCard } from '@/components/dashboard/stat-card'
import { StatCardSkeletonGroup } from '@/components/datawise/card-skeleton'
import { PageHeader } from '@/components/datawise/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { buttonVariants } from '@/components/ui/button'
import { useDashboardHydration } from '@/hooks/use-store-hydration'
import { cn } from '@/lib/utils'
import { useDatasetStore } from '@/stores/dataset-store'
import { useFavoriteStore } from '@/stores/favorite-store'
import { useReportStore } from '@/stores/report-store'

export default function DashboardPage() {
  const [mounted, setMounted] = useState(false)
  const hydrated = useDashboardHydration()

  const datasets = useDatasetStore((state) => state.datasets)
  const reports = useReportStore((state) => state.reports)
  const favorites = useFavoriteStore((state) => state.favorites)

  useEffect(() => {
    setMounted(true)
  }, [])

  const ready = mounted && hydrated

  return (
    <div className="space-y-8 p-6">
      <PageHeader
        title="Dashboard"
        description="Overview of your datasets, reports, and recent activity."
      />

      {!ready ? (
        <div className="space-y-8">
          <StatCardSkeletonGroup />
          <div className="rounded-xl border border-border bg-card p-6">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="mt-2 h-4 w-48" />
            <div className="mt-4 flex gap-3">
              <Skeleton className="h-9 w-24 rounded-lg" />
              <Skeleton className="h-9 w-36 rounded-lg" />
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              label="Datasets"
              value={datasets.length}
              icon={Database}
              href="/datasets"
            />
            <StatCard
              label="Reports"
              value={reports.length}
              icon={FileText}
              href="/reports"
            />
            <StatCard
              label="Favorites"
              value={favorites.length}
              icon={Star}
              href="/favorites"
            />
          </div>

          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold text-foreground">Quick actions</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Start working with your data.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link href="/upload" className={cn(buttonVariants(), 'gap-2')}>
                <Upload className="size-4" />
                Upload
              </Link>
              <Link
                href="/datasets"
                className={cn(buttonVariants({ variant: 'outline' }), 'gap-2')}
              >
                <Database className="size-4" />
                Browse datasets
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}