'use client'

import { useEffect, useState } from 'react'
import { Maximize2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { chartTypeLabel, normalizeChartType } from '@/lib/chart-utils'
import type { ChartDataItem } from '@/types/artifacts'
import { ChartCanvas } from './chart-canvas'
import { formatValue } from './types'

export function ChartRenderer({ chart }: { chart: ChartDataItem }) {
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (!expanded) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpanded(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [expanded])

  if (!chart || !chart.type) {
    return (
      <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 text-xs text-muted-foreground">
        Invalid chart data
      </div>
    )
  }

  const chartType = normalizeChartType(chart.type)

  const typeColors: Record<string, string> = {
    bar: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    line: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    scatter: 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20',
    pie: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    histogram: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20',
    heatmap: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
    boxplot: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20',
  }

  const typeBadge = typeColors[chartType] || 'bg-muted/50 text-muted-foreground border-border'

  return (
    <>
      <article className="group flex min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm transition-all duration-200 hover:border-primary/25 hover:shadow-md hover:-translate-y-0.5">
        <div className="mb-2 flex shrink-0 items-center justify-between gap-3 px-4 pt-4">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground" title={chart.title}>
              {chart.title}
            </h3>
            <span className={cn('shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider', typeBadge)}>
              {chartTypeLabel(chart.type)}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground opacity-0 transition-all group-hover:opacity-100 hover:bg-muted hover:text-foreground"
            aria-label={`Expand ${chart.title} fullscreen`}
          >
            <Maximize2 className="size-3" />
          </button>
        </div>
        <div className="h-72 min-h-0 w-full px-4 pb-4">
          <ChartCanvas chart={chart} isExpanded={false} />
        </div>
      </article>

      {expanded && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`${chart.title} (Fullscreen)`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setExpanded(false)}
        >
          <div
            className="flex h-[88vh] w-[94vw] max-w-6xl flex-col rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in zoom-in-95 duration-200"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex shrink-0 items-center justify-between border-b border-border pb-4">
              <div>
                <h2 className="text-lg font-bold text-foreground">{chart.title}</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Interactive Chart View • {chartTypeLabel(chart.type).toUpperCase()}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Close fullscreen chart"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="min-h-0 flex-1 w-full">
              <ChartCanvas chart={chart} isExpanded />
            </div>
          </div>
        </div>
      )}
    </>
  )
}