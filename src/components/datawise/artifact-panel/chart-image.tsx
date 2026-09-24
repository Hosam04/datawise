'use client'

import { useEffect, useState } from 'react'
import { LoaderCircle, Maximize2, X, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { assetUrl } from '@/lib/api'

export function ChartImage({ url, index }: { url: string; index: number }) {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [expanded, setExpanded] = useState(false)
  const [zoom, setZoom] = useState(1)

  useEffect(() => {
    if (!expanded) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setExpanded(false)
        setZoom(1)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [expanded])

  return (
    <>
      <div className="group relative overflow-hidden rounded-xl border border-border bg-card p-4 shadow-sm transition-all hover:border-primary/20 hover:shadow-md">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="truncate text-sm font-semibold text-foreground">
            Chart {index + 1}
          </h3>
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label={`Expand Chart ${index + 1} fullscreen`}
          >
            <Maximize2 className="size-3.5" />
            <span>Expand</span>
          </button>
        </div>

        <div className="relative flex min-h-64 items-center justify-center overflow-hidden rounded-lg bg-muted/20">
          {state === 'loading' && (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              <LoaderCircle className="mr-2 size-4 animate-spin" />
              Loading chart…
            </div>
          )}
          {state === 'error' && (
            <div className="flex h-64 items-center justify-center text-sm text-destructive">
              Unable to load chart {index + 1}.
            </div>
          )}
          <img
            src={assetUrl(url)}
            alt={`Generated chart ${index + 1}`}
            className={cn(
              'h-auto w-full cursor-zoom-in object-contain transition-transform',
              state !== 'ready' && 'hidden'
            )}
            onLoad={() => setState('ready')}
            onError={() => setState('error')}
            onClick={() => setExpanded(true)}
          />
        </div>
      </div>

      {expanded && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Chart ${index + 1} (Fullscreen)`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => {
            setExpanded(false)
            setZoom(1)
          }}
        >
          <div
            className="flex h-[88vh] w-[94vw] max-w-6xl flex-col rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in zoom-in-95 duration-200"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between border-b border-border pb-4">
              <div>
                <h2 className="text-lg font-bold text-foreground">
                  Chart {index + 1}
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  High Resolution Visualization View
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.min(z + 0.25, 3))}
                  className="rounded-lg border border-border bg-background p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  aria-label="Zoom in"
                >
                  <ZoomIn className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.max(z - 0.25, 0.5))}
                  className="rounded-lg border border-border bg-background p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  aria-label="Zoom out"
                >
                  <ZoomOut className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoom(1)}
                  className="rounded-lg border border-border bg-background p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  aria-label="Reset zoom"
                >
                  <RotateCcw className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setExpanded(false)
                    setZoom(1)
                  }}
                  className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground ml-2"
                  aria-label="Close fullscreen chart"
                >
                  <X className="size-5" />
                </button>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto rounded-xl bg-muted/20 p-4">
              <img
                src={assetUrl(url)}
                alt={`Generated chart ${index + 1} fullscreen`}
                style={{ transform: `scale(${zoom})`, transformOrigin: 'center center' }}
                className="max-h-full max-w-full object-contain transition-transform duration-150"
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}