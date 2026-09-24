'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import {
  BarChart3,
  Download,
  FileText,
  Lightbulb,
  Loader2,
  Maximize2,
  X,
  RefreshCw,
} from 'lucide-react'
import { toast } from 'sonner'
import { DetailPageSkeleton } from '@/components/datawise/detail-page-skeleton'
import { FavoriteButton } from '@/components/favorites/favorite-button'
import {
  ActionBar,
  DetailSection,
  MetadataGrid,
} from '@/components/datawise/detail-section'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'
import { buttonVariants } from '@/components/ui/button'
import { chatHref, datasetHref } from '@/lib/app-links'
import { downloadReportFile, fetchFile } from '@/lib/api'
import { formatDisplayDate } from '@/lib/format'
import { getReportTimestamp } from '@/lib/sort-utils'
import { cn } from '@/lib/utils'
import { useReportStoreHydration } from '@/hooks/use-store-hydration'
import { useReportStore, type Report } from '@/stores/report-store'

export default function ReportDetailPage() {
  const hydrated = useReportStoreHydration()
  const params = useParams()
  const router = useRouter()
  const id = params.id as string

  const report = useReportStore((state) =>
    state.reports.find((entry) => entry.id === id),
  )

  const [exporting, setExporting] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  
  // State for fetching the Blob to safely display the PDF inside the iframe
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [loadingPdf, setLoadingPdf] = useState(true)
  const [pdfError, setPdfError] = useState<string | null>(null)

  // Determine the correct datasetId with a fallback (API may return dataset_id or datasetId)
  const datasetId =
    report?.datasetId ??
    (report as { dataset_id?: string } | undefined)?.dataset_id ??
    id.replace(/-report$/, '')

  // Prepare the title by removing the .csv extension and appending '_report'
  const rawDatasetName = (report?.dataset || report?.title || '').replace(/\.[^/.]+$/, '')
  const displayReportTitle = rawDatasetName ? `${rawDatasetName}_report` : (report?.title || 'Report')

  useEffect(() => {
    if (hydrated && !report) {
      router.replace('/reports')
    }
  }, [hydrated, report, router])

  // Fetch the PDF using the Bearer token and convert it to a Blob URL for display
  useEffect(() => {
    if (!datasetId || !report) return

    let active = true
    let objectUrl: string | null = null

    const loadPdfPreview = async () => {
      setLoadingPdf(true)
      setPdfError(null)

      try {
        const { blob } = await fetchFile(
          `/datasets/${encodeURIComponent(datasetId)}/report/download`,
          `${rawDatasetName}_report.pdf`
        )
        if (!active) return

        objectUrl = URL.createObjectURL(blob)
        setPdfBlobUrl(objectUrl)
      } catch (err: unknown) {
        if (!active) return
        console.error('Failed to load PDF preview:', err)
        setPdfError(
          err instanceof Error ? err.message : 'Failed to load PDF preview.',
        )
      } finally {
        if (active) setLoadingPdf(false)
      }
    }

    void loadPdfPreview()

    return () => {
      active = false
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [datasetId, report, rawDatasetName])

  useEffect(() => {
    if (!fullscreen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setFullscreen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [fullscreen])

  if (!hydrated) {
    return <DetailPageSkeleton />
  }

  if (!report) {
    return null
  }

  const generatedAt = formatDisplayDate(getReportTimestamp(report))

  const handleExport = async () => {
    if (exporting) return
    setExporting(true)

    const fallbackFilename = `${rawDatasetName}_report.pdf`

    try {
      if (!datasetId) throw new Error('Dataset ID is missing for this report.')
      await downloadReportFile(datasetId, fallbackFilename)
      toast.success('Report downloaded', { description: fallbackFilename })
    } catch (err: unknown) {
      toast.error('Failed to download report', {
        description:
          err instanceof Error ? err.message : 'Please try again later.',
      })
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <Breadcrumbs
        items={[
          { label: 'Reports', href: '/reports' },
          { label: displayReportTitle },
        ]}
      />

      <div className="rounded-xl border border-primary/20 bg-primary/5 p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex size-14 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <FileText className="size-7" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-primary">Report summary</p>
              <h1 className="mt-1 text-3xl font-bold text-foreground">
                {displayReportTitle}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Generated on {generatedAt} • {report.type}
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={exporting}
            onClick={() => void handleExport()}
            className={cn(buttonVariants(), 'gap-2 shadow-xs')}
          >
            {exporting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            {exporting ? 'Exporting...' : 'Export PDF'}
          </button>
        </div>

        <p className="mt-4 leading-7 text-foreground">
          This report summarizes AI analysis for{' '}
          <span className="font-semibold">{report.dataset}</span>. Review the
          sections below for metadata, findings, embedded PDF document, and recommended next steps.
        </p>
      </div>

      {/* Embedded Document Preview */}
      <DetailSection
        title="Document Preview"
        description="Live view of the generated analysis report."
      >
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-primary" />
              <span className="text-sm font-medium text-foreground">{displayReportTitle}</span>
            </div>
            <button
              type="button"
              disabled={!pdfBlobUrl}
              onClick={() => setFullscreen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
            >
              <Maximize2 className="size-3.5" />
              <span>Fullscreen</span>
            </button>
          </div>

          <div className="relative h-130 w-full overflow-hidden rounded-lg border border-border bg-muted/20 flex items-center justify-center">
            {loadingPdf ? (
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <Loader2 className="size-8 animate-spin text-primary" />
                <p className="text-sm">Loading PDF document...</p>
              </div>
            ) : pdfError ? (
              <div className="flex flex-col items-center gap-3 text-center p-4">
                <FileText className="size-10 text-muted-foreground" />
                <p className="text-sm font-medium text-destructive">{pdfError}</p>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                >
                  <RefreshCw className="size-3.5" />
                  Reload Page
                </button>
              </div>
            ) : pdfBlobUrl ? (
              <iframe
                title="PDF Report Viewer"
                src={pdfBlobUrl}
                className="size-full border-0"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <FileText className="size-10" />
                <p className="text-sm">No PDF preview available.</p>
              </div>
            )}
          </div>
        </div>
      </DetailSection>

      <div className="grid gap-6 lg:grid-cols-2">
        <DetailSection
          title="Overview"
          description="High-level context for this analysis report."
        >
          <MetadataGrid
            items={[
              { label: 'Report title', value: displayReportTitle },
              { label: 'Source dataset', value: report.dataset },
              { label: 'Report type', value: report.type },
              { label: 'Generated', value: generatedAt },
            ]}
          />
        </DetailSection>

        <DetailSection
          title="Key findings"
          description="Highlights extracted from the analysis."
        >
          <ul className="space-y-3">
            {[
              'Dataset structure was reviewed successfully.',
              'Primary trends were identified for further exploration.',
              'No critical data quality blockers were detected.',
            ].map((finding) => (
              <li
                key={finding}
                className="flex items-start gap-3 rounded-lg border border-border bg-background p-4 text-sm text-foreground"
              >
                <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" />
                {finding}
              </li>
            ))}
          </ul>
        </DetailSection>
      </div>

      <DetailSection
        title="Analysis details"
        description="What this report covers."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-border bg-background p-4 shadow-xs">
            <BarChart3 className="size-5 text-primary" />
            <h3 className="mt-3 font-semibold text-foreground">Visual trends</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Charts and metrics derived from {report.dataset}.
            </p>
          </div>

          <div className="rounded-lg border border-border bg-background p-4 shadow-xs">
            <FileText className="size-5 text-primary" />
            <h3 className="mt-3 font-semibold text-foreground">Narrative summary</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Plain-language explanation of the most important patterns.
            </p>
          </div>

          <div className="rounded-lg border border-border bg-background p-4 shadow-xs">
            <Lightbulb className="size-5 text-primary" />
            <h3 className="mt-3 font-semibold text-foreground">Recommendations</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Suggested follow-up questions and next analyses to run in chat.
            </p>
          </div>
        </div>
      </DetailSection>

      <ActionBar>
        <FavoriteButton
          showLabel
          item={{
            id: report.id,
            name: displayReportTitle,
            type: 'report',
            description: `${report.dataset} • ${report.type}`,
          }}
        />

        <Link
          href={datasetHref(datasetId)}
          className={cn(buttonVariants({ variant: 'outline' }), 'gap-2')}
        >
          View dataset
        </Link>

        <Link
          href={chatHref(datasetId)}
          className={cn(buttonVariants({ variant: 'outline' }), 'gap-2')}
        >
          Open in chat
        </Link>

        <button
          type="button"
          disabled={exporting}
          onClick={() => void handleExport()}
          className={cn(buttonVariants({ variant: 'outline' }), 'gap-2')}
        >
          {exporting ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Download className="size-4" />
          )}
          {exporting ? 'Exporting...' : 'Export report'}
        </button>
      </ActionBar>

      {fullscreen && pdfBlobUrl && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Report Fullscreen Preview"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setFullscreen(false)}
        >
          <div
            className="flex h-[90vh] w-[95vw] max-w-7xl flex-col rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in zoom-in-95 duration-200"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between border-b border-border pb-4">
              <div>
                <h2 className="text-lg font-bold text-foreground">{displayReportTitle}</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Generated on {generatedAt}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  disabled={exporting}
                  onClick={() => void handleExport()}
                  className={cn(buttonVariants(), 'gap-2')}
                >
                  <Download className="size-4" />
                  <span>Download PDF</span>
                </button>
                <button
                  type="button"
                  onClick={() => setFullscreen(false)}
                  className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  aria-label="Close fullscreen view"
                >
                  <X className="size-5" />
                </button>
              </div>
            </div>

            <div className="min-h-0 flex-1 w-full overflow-hidden rounded-xl border border-border bg-muted/10">
              <iframe
                title="Fullscreen Report Preview"
                src={pdfBlobUrl}
                className="size-full border-0"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}