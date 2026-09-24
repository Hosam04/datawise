'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Database, Download, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { FavoriteButton } from '@/components/favorites/favorite-button'
import { StatusBadge } from '@/components/datawise/status-badge'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { downloadProcessedDataset, deleteDatasetApi } from '@/lib/api'
import { formatDisplayDate } from '@/lib/format'
import { getDatasetTimestamp } from '@/lib/sort-utils'
import { useDatasetStore } from '@/stores/dataset-store'
import { useWorkspaceStore } from '@/stores/workspace-store'

export interface DatasetCardProps {
  id: string
  name: string
  size: string
  status: string
  uploadedAt?: string
}

function isAnalyzedStatus(status: string): boolean {
  const s = status.toLowerCase()
  return s === 'analyzed' || s === 'ready' || s === 'completed'
}

export function DatasetCard({
  id,
  name,
  size,
  status,
  uploadedAt,
}: DatasetCardProps) {
  const router = useRouter()
  const pathname = usePathname()
  const removeDataset = useDatasetStore((state) => state.removeDataset)
  const removeOpenDataset = useWorkspaceStore((state) => state.removeOpenDataset)
  const [downloading, setDownloading] = useState(false)

  const uploadedLabel = formatDisplayDate(
    uploadedAt ?? getDatasetTimestamp({ id, name, size, type: '', status, uploadedAt }),
  )

  const handleDownload = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (downloading) return
    setDownloading(true)
    const fallbackFilename = `${name.replace(/\.[^/.]+$/, '')}_processed.csv`
    try {
      await downloadProcessedDataset(id, fallbackFilename)
      toast.success('Processed dataset downloaded', { description: fallbackFilename })
    } catch (err: unknown) {
      toast.error('Failed to download processed dataset', {
        description: err instanceof Error ? err.message : 'Please try again.',
      })
    } finally {
      setDownloading(false)
    }
  }

  const handleDelete = async () => {
    try {
      await deleteDatasetApi(id)
      removeDataset(id)
      removeOpenDataset(id)
      toast.success('Dataset deleted', { description: name })
      // Only navigate away when viewing this dataset's own detail page
      if (pathname === `/datasets/${id}`) {
        router.push('/datasets')
      }
    } catch (err: unknown) {
      toast.error('Failed to delete dataset', {
        description: err instanceof Error ? err.message : 'Please try again.',
      })
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-5 shadow-xs transition-all hover:border-primary/20 hover:shadow-sm">
      <Link
        href={`/datasets/${id}`}
        className="flex min-w-0 flex-1 items-center gap-4 rounded-lg transition-colors hover:opacity-80"
      >
        <div className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Database className="size-5 text-primary" />
        </div>

        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-foreground">{name}</h3>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <span>{size}</span>
            <span aria-hidden>•</span>
            <StatusBadge status={status} />
            <span aria-hidden>•</span>
            <span>Uploaded {uploadedLabel}</span>
          </p>
        </div>
      </Link>

      <div className="flex items-center gap-2">
        {isAnalyzedStatus(status) && (
          <button
            type="button"
            disabled={downloading}
            onClick={handleDownload}
            title={`Download processed dataset ${name}`}
            aria-label={`Download processed dataset ${name}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            {downloading ? (
              <Loader2 className="size-3.5 animate-spin text-primary" />
            ) : (
              <Download className="size-3.5" />
            )}
            <span>Download</span>
          </button>
        )}

        <FavoriteButton
          item={{
            id,
            name,
            type: 'dataset',
            description: `${size} • ${status}`,
          }}
        />

        <ConfirmDialog
          title="Delete dataset?"
          description={`"${name}" will be permanently removed.`}
          tooltip={`Delete ${name}`}
          onConfirm={handleDelete}
          trigger={
            <button
              type="button"
              aria-label={`Remove ${name}`}
              className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
            >
              <Trash2 className="size-4" />
            </button>
          }
        />
      </div>
    </div>
  )
}

export default DatasetCard