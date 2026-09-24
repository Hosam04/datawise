'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Download, FileText, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { FavoriteButton } from '@/components/favorites/favorite-button'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { reportHref } from '@/lib/app-links'
import { deleteReportApi, downloadReportFile } from '@/lib/api'
import { useReportStore } from '@/stores/report-store'

interface ReportCardProps {
  id: string
  title: string
  dataset: string
  date: string
  type: string
}

export function ReportCard({
  id,
  title,
  dataset,
  date,
  type,
}: ReportCardProps) {
  const removeReport = useReportStore((state) => state.removeReport)
  const [downloading, setDownloading] = useState(false)
  const report = useReportStore((state) =>
    state.reports.find((entry) => entry.id === id),
  )
  const datasetId = report?.datasetId

  // Remove the file extension (e.g., .csv) and append '_report'
  const rawName = (dataset || title).replace(/\.[^/.]+$/, '')
  const displayTitle = `${rawName}_report`

  const handleExport = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (downloading) return

    setDownloading(true)
    const fallbackFilename = `${rawName}_report.pdf`
    try {
      if (!datasetId) throw new Error('Report dataset is unavailable')
      await downloadReportFile(datasetId, fallbackFilename)
      toast.success('Report downloaded', { description: fallbackFilename })
    } catch (err: unknown) {
      toast.error('Failed to download report', {
        description: err instanceof Error ? err.message : 'Please try again.',
      })
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-5 shadow-xs transition-all hover:border-primary/20 hover:shadow-sm">
      <Link
        href={reportHref(id)}
        className="flex min-w-0 flex-1 items-center gap-4 rounded-lg transition-colors hover:opacity-80"
      >
        <div className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <FileText className="size-5 text-primary" />
        </div>

        <div className="min-w-0">
          {/* Now displays the file name in the format: new_york_listings_2024_report */}
          <h3 className="truncate text-sm font-semibold text-foreground">
            {displayTitle}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {type} • {date}
          </p>
        </div>
      </Link>

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={downloading}
          onClick={handleExport}
          title={`Download ${displayTitle}`}
          aria-label={`Export report ${displayTitle}`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
        >
          {downloading ? (
            <Loader2 className="size-3.5 animate-spin text-primary" />
          ) : (
            <Download className="size-3.5" />
          )}
          <span>Export</span>
        </button>

        <FavoriteButton
          item={{
            id,
            name: displayTitle,
            type: 'report',
            description: `${type} • ${date}`,
          }}
        />

        <ConfirmDialog
          title="Delete report?"
          description={`"${displayTitle}" will be permanently removed.`}
          tooltip={`Delete ${displayTitle}`}
          onConfirm={async () => {
            try {
              await deleteReportApi(id)
              removeReport(id)
              toast.success('Report deleted', { description: displayTitle })
            } catch (err: unknown) {
              toast.error('Failed to delete report', {
                description: err instanceof Error ? err.message : 'Please try again.',
              })
            }
          }}
          trigger={
            <button
              type="button"
              aria-label={`Remove ${displayTitle}`}
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