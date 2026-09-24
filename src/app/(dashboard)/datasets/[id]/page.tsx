'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { Database, Download, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { DetailPageSkeleton } from '@/components/datawise/detail-page-skeleton'
import { FavoriteButton } from '@/components/favorites/favorite-button'
import {
  ActionBar,
  DetailSection,
  MetadataGrid,
} from '@/components/datawise/detail-section'
import { StatusBadge } from '@/components/datawise/status-badge'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'
import { buttonVariants } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { chatHref, reportHref } from '@/lib/app-links'
import { downloadProcessedDataset } from '@/lib/api'
import { formatDisplayDate, formatFileType } from '@/lib/format'
import { getDatasetTimestamp } from '@/lib/sort-utils'
import { cn } from '@/lib/utils'
import { useDatasetStoreHydration } from '@/hooks/use-store-hydration'
import { useDatasetStore } from '@/stores/dataset-store'
import { useWorkspaceStore } from '@/stores/workspace-store'
import { useReportStore } from '@/stores/report-store'

function isAnalyzedStatus(status: string): boolean {
  const s = status.toLowerCase()
  return s === 'analyzed' || s === 'ready' || s === 'completed'
}

export default function DatasetDetailPage() {
  const hydrated = useDatasetStoreHydration()
  const params = useParams()
  const router = useRouter()
  const id = params.id as string

  const dataset = useDatasetStore((state) =>
    state.datasets.find((entry) => entry.id === id),
  )
  const removeDataset = useDatasetStore((state) => state.removeDataset)
  const removeOpenDataset = useWorkspaceStore(
    (state) => state.removeOpenDataset,
  )
  const report = useReportStore((state) =>
    state.reports.find((entry) => entry.datasetId === id),
  )

  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    if (hydrated && !dataset) {
      router.replace('/datasets')
    }
  }, [hydrated, dataset, router])

  if (!hydrated) {
    return <DetailPageSkeleton />
  }

  if (!dataset) {
    return null
  }

  const uploadedLabel = formatDisplayDate(
    dataset.uploadedAt ?? getDatasetTimestamp(dataset),
  )

  const handleDownload = async () => {
    if (downloading) return
    setDownloading(true)
    const fallbackFilename = `${dataset.name.replace(/\.[^/.]+$/, '')}_processed.csv`

    try {
      await downloadProcessedDataset(dataset.id, fallbackFilename)
      toast.success('Processed dataset downloaded', {
        description: fallbackFilename,
      })
    } catch (err: unknown) {
      toast.error('Failed to download processed dataset', {
        description: err instanceof Error ? err.message : 'Please try again.',
      })
    } finally {
      setDownloading(false)
    }
  }

  const handleDelete = () => {
    removeDataset(dataset.id)
    removeOpenDataset(dataset.id)
    toast.success('Dataset deleted', { description: dataset.name })
    router.push('/datasets')
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <Breadcrumbs
        items={[
          { label: 'Datasets', href: '/datasets' },
          { label: dataset.name },
        ]}
      />

      <div className="rounded-xl border border-primary/20 bg-primary/5 p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex size-14 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Database className="size-7" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-primary">Dataset</p>
              <h1 className="mt-1 text-3xl font-bold text-foreground">
                {dataset.name}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Uploaded {uploadedLabel}
              </p>
              <div className="mt-2">
                <StatusBadge status={dataset.status} />
              </div>
            </div>
          </div>

          {isAnalyzedStatus(dataset.status) && (
            <button
              type="button"
              disabled={downloading}
              onClick={() => void handleDownload()}
              className={cn(buttonVariants(), 'gap-2 shadow-xs')}
            >
              {downloading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Download className="size-4" />
              )}
              {downloading ? 'Downloading...' : 'Download Processed Dataset'}
            </button>
          )}
        </div>
      </div>

      <DetailSection
        title="Overview"
        description="Metadata for this dataset."
      >
        <MetadataGrid
          items={[
            { label: 'File size', value: dataset.size },
            { label: 'File type', value: formatFileType(dataset.type) },
            { label: 'Status', value: dataset.status },
            { label: 'Uploaded', value: uploadedLabel },
          ]}
        />
      </DetailSection>

      <ActionBar>
        <FavoriteButton
          showLabel
          item={{
            id: dataset.id,
            name: dataset.name,
            type: 'dataset',
            description: `${dataset.size} • ${dataset.status}`,
          }}
        />

        <Link
          href={chatHref(dataset.id)}
          className={cn(buttonVariants({ variant: 'outline' }), 'gap-2')}
        >
          Open in chat
        </Link>

        {report && (
          <Link
            href={reportHref(report.id)}
            className={cn(buttonVariants({ variant: 'outline' }), 'gap-2')}
          >
            View report
          </Link>
        )}

        <ConfirmDialog
          title="Delete dataset?"
          description={`"${dataset.name}" will be permanently removed.`}
          tooltip={`Delete ${dataset.name}`}
          onConfirm={handleDelete}
          trigger={
            <button
              type="button"
              aria-label="Delete dataset"
              className={cn(
                buttonVariants({ variant: 'outline' }),
                'gap-2 text-destructive',
              )}
            >
              <Trash2 className="size-4" />
              Delete dataset
            </button>
          }
        />
      </ActionBar>
    </div>
  )
}