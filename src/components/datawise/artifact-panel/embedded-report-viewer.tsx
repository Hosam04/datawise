'use client'

import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  LoaderCircle,
  Maximize2,
  Minimize2,
  RotateCcw,
  ScanLine,
  X,
  ZoomIn,
  ZoomOut,
  AlignJustify,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { assetUrl, fetchFile, saveDownloadedFile, type DownloadedFile } from '@/lib/api'
import {
  buildIframeSrc,
  DEFAULT_EMBED_ZOOM,
  DEFAULT_FULLSCREEN_ZOOM,
  formatBytes,
  zoomIn,
  zoomOut,
} from './report-viewer-utils'

export function EmbeddedReportViewer({
  reportUrl,
  datasetName,
}: {
  reportUrl: string
  datasetName?: string
}) {
  const [file, setFile] = useState<DownloadedFile>()
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string>()
  const [expanded, setExpanded] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string>()
  const [retryKey, setRetryKey] = useState(0)

  // Zoom & fit-mode state for fullscreen viewer
  const [fsZoom, setFsZoom] = useState(DEFAULT_FULLSCREEN_ZOOM)
  const [fsFitMode, setFsFitMode] = useState<'width' | 'page' | 'zoom'>('zoom')
  // Embed zoom state
  const [embedZoom] = useState(DEFAULT_EMBED_ZOOM)

  // iframe ref so we can force-reload on zoom change (browser PDF hash doesn't hot-reload)
  const fsIframeRef = useRef<HTMLIFrameElement>(null)
  const [fsIframeKey, setFsIframeKey] = useState(0)

  const fallbackFilename = datasetName
    ? `${datasetName.replace(/\.[^/.]+$/, '')}_report.pdf`
    : 'dataset_report.pdf'

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | undefined

    setLoading(true)
    setError(undefined)
    setFile(undefined)
    setPreviewUrl(undefined)

    const cached = reportFileCache.get(reportUrl)
    if (cached) {
      objectUrl = URL.createObjectURL(cached.blob)
      setPreviewUrl(objectUrl)
      setFile(cached)
      setLoading(false)
      return () => {
        cancelled = true
        if (objectUrl) URL.revokeObjectURL(objectUrl)
      }
    }

    void fetchFile(reportUrl, fallbackFilename)
      .then((result) => {
        if (cancelled) return
        reportFileCache.set(reportUrl, result)
        objectUrl = URL.createObjectURL(result.blob)
        setPreviewUrl(objectUrl)
        setFile(result)
        setLoading(false)
      })
      .catch((reason: unknown) => {
        if (cancelled) return
        setError(reason instanceof Error ? reason.message : 'Failed to load the PDF report.')
        setLoading(false)
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [reportUrl, fallbackFilename, retryKey])

  // Keyboard shortcuts when fullscreen is open
  useEffect(() => {
    if (!expanded) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setExpanded(false)
      } else if (event.key === '+' || event.key === '=') {
        setFsZoom((z) => { const next = zoomIn(z); setFsIframeKey((k) => k + 1); return next })
        setFsFitMode('zoom')
      } else if (event.key === '-') {
        setFsZoom((z) => { const next = zoomOut(z); setFsIframeKey((k) => k + 1); return next })
        setFsFitMode('zoom')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [expanded])

  // Reset zoom each time fullscreen opens
  useEffect(() => {
    if (expanded) {
      setFsZoom(DEFAULT_FULLSCREEN_ZOOM)
      setFsFitMode('zoom')
      setFsIframeKey((k) => k + 1)
    }
  }, [expanded])

  const handleDownload = () => {
    if (!file || downloading) return
    setDownloading(true)
    try {
      saveDownloadedFile(file)
    } finally {
      setDownloading(false)
    }
  }

  const handleFsZoomIn = () => {
    setFsZoom((z) => zoomIn(z))
    setFsFitMode('zoom')
    setFsIframeKey((k) => k + 1)
  }

  const handleFsZoomOut = () => {
    setFsZoom((z) => zoomOut(z))
    setFsFitMode('zoom')
    setFsIframeKey((k) => k + 1)
  }

  const handleFsReset = () => {
    setFsZoom(DEFAULT_FULLSCREEN_ZOOM)
    setFsFitMode('zoom')
    setFsIframeKey((k) => k + 1)
  }

  const handleFitWidth = () => {
    setFsFitMode('width')
    setFsIframeKey((k) => k + 1)
  }

  const handleFitPage = () => {
    setFsFitMode('page')
    setFsIframeKey((k) => k + 1)
  }

  const title = datasetName ? `${datasetName} Analysis Report` : 'Analysis Report'

  return (
    <>
      {/* ── Embedded Preview ─────────────────────────────────────────────── */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
        {/* Header bar */}
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileText className="size-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground">{title}</h3>
              <p className="text-xs text-muted-foreground">
                PDF Document{file ? ` • ${formatBytes(file.blob.size)}` : ''} • Generated by DataWise
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={!previewUrl}
              onClick={() => window.open(previewUrl, '_blank', 'noopener')}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
            >
              <ExternalLink className="size-3.5" />
              <span>Open</span>
            </button>
            <button
              type="button"
              disabled={!file}
              onClick={() => setExpanded(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
            >
              <Maximize2 className="size-3.5" />
              <span>Fullscreen</span>
            </button>
            <button
              type="button"
              disabled={!file || downloading}
              onClick={handleDownload}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
            >
              {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5" />}
              <span>{downloading ? 'Downloading...' : 'Download PDF'}</span>
            </button>
          </div>
        </div>

        {/* PDF iframe — takes all remaining vertical space */}
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-border bg-muted/20 shadow-xs">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 bg-card text-sm text-muted-foreground">
              <LoaderCircle className="size-4 animate-spin" />
              Loading report…
            </div>
          )}

          {error && !loading && (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
              <AlertCircle className="size-6 text-destructive" />
              <p className="text-sm text-destructive">{error}</p>
              <button
                type="button"
                onClick={() => setRetryKey((k) => k + 1)}
                className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
              >
                Try again
              </button>
            </div>
          )}

          {previewUrl && !error && !loading && (
            <iframe
              title="Generated PDF Report"
              src={buildIframeSrc(previewUrl, embedZoom, 'width')}
              className="size-full border-0"
              style={{ display: 'block' }}
            />
          )}
        </div>
      </div>

      {/* ── True Fullscreen dialog ────────────────────────────────────────── */}
      {expanded && previewUrl && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Report Preview Fullscreen"
          className="fixed inset-0 z-[9999] flex flex-col bg-[hsl(var(--background))] animate-in fade-in duration-150"
        >
          {/* Slim toolbar */}
          <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border bg-card/80 px-4 backdrop-blur-sm">
            {/* Left: title */}
            <div className="flex min-w-0 items-center gap-2.5">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <FileText className="size-3.5" />
              </div>
              <p className="truncate text-sm font-semibold text-foreground">{title}</p>
            </div>

            {/* Centre: zoom controls */}
            <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-1">
              <button
                type="button"
                onClick={handleFsZoomOut}
                disabled={fsFitMode !== 'zoom' ? false : fsZoom <= 50}
                className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                aria-label="Zoom out (−)"
                title="Zoom out (−)"
              >
                <ZoomOut className="size-3.5" />
              </button>

              <button
                type="button"
                onClick={handleFsReset}
                className="min-w-[52px] rounded-md px-2 py-1 text-center text-xs font-medium tabular-nums text-foreground transition-colors hover:bg-muted"
                aria-label="Reset zoom"
                title="Reset zoom"
              >
                {fsFitMode === 'width' ? 'Fit W' : fsFitMode === 'page' ? 'Fit P' : `${fsZoom}%`}
              </button>

              <button
                type="button"
                onClick={handleFsZoomIn}
                disabled={fsFitMode !== 'zoom' ? false : fsZoom >= 300}
                className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                aria-label="Zoom in (+)"
                title="Zoom in (+)"
              >
                <ZoomIn className="size-3.5" />
              </button>

              <div className="mx-1 h-4 w-px bg-border" />

              <button
                type="button"
                onClick={handleFitWidth}
                className={cn(
                  'flex size-7 items-center justify-center rounded-md transition-colors',
                  fsFitMode === 'width'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                aria-label="Fit to width"
                title="Fit to Width"
              >
                <AlignJustify className="size-3.5" />
              </button>

              <button
                type="button"
                onClick={handleFitPage}
                className={cn(
                  'flex size-7 items-center justify-center rounded-md transition-colors',
                  fsFitMode === 'page'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                aria-label="Fit to page"
                title="Fit to Page"
              >
                <ScanLine className="size-3.5" />
              </button>
            </div>

            {/* Right: actions */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={!file || downloading}
                onClick={handleDownload}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5" />}
                <span className="hidden sm:inline">{downloading ? 'Downloading...' : 'Download'}</span>
              </button>

              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Exit fullscreen (Esc)"
                title="Exit fullscreen (Esc)"
              >
                <Minimize2 className="size-4" />
              </button>
            </div>
          </div>

          {/* PDF takes 100% of remaining height & width */}
          <div className="min-h-0 flex-1 overflow-hidden bg-muted/10">
            <iframe
              key={fsIframeKey}
              ref={fsIframeRef}
              title="Fullscreen Generated PDF Report"
              src={buildIframeSrc(previewUrl, fsZoom, fsFitMode)}
              className="h-full w-full border-0"
              style={{ display: 'block' }}
            />
          </div>

          {/* Keyboard hint */}
          <div className="flex h-7 shrink-0 items-center justify-center gap-4 border-t border-border bg-card/60 backdrop-blur-sm">
            <span className="text-[10px] text-muted-foreground/60">
              <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[9px]">+</kbd>
              {' / '}
              <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[9px]">−</kbd>
              {' zoom  •  '}
              <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[9px]">Esc</kbd>
              {' close'}
            </span>
          </div>
        </div>
      )}
    </>
  )
}

const reportFileCache = new Map<string, DownloadedFile>()