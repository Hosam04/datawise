'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { AlertCircle, LoaderCircle } from 'lucide-react'
import {
  ArtifactEmptyState,
  DatasetStatisticsView,
  InsightsContent,
  InsightsReportContent,
  PreviewContent,
} from '@/components/datawise/artifact-content'
import { ChartsDashboard } from '@/components/datawise/charts-dashboard'
import { getDatasetArtifacts } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useDatasetStore } from '@/stores/dataset-store'
import { useWorkspaceStore } from '@/stores/workspace-store'
import type {
  ChartArtifact,
  ChartDataItem,
  CompletedArtifacts,
  StatisticsArtifact,
} from '@/types/artifacts'
import { ChartImage } from './chart-image'
import { EmbeddedReportViewer } from './embedded-report-viewer'
import { normalizeStatisticsArtifact } from './statistics-utils'

export const tabs = ['Preview', 'Charts', 'Insights', 'Statistics', 'Report'] as const
export type Tab = (typeof tabs)[number]

export function ArtifactPanel() {
  const searchParams = useSearchParams()
  const activeDatasetId = useWorkspaceStore((state) => state.activeDatasetId)
  const datasetId = searchParams.get('dataset') ?? activeDatasetId
  const dataset = useDatasetStore((state) =>
    state.datasets.find((item) => item.id === datasetId)
  )
  const setDatasetArtifacts = useDatasetStore(
    (state) => state.setDatasetArtifacts
  )
  const [tab, setTab] = useState<Tab>('Preview')
  const [artifacts, setArtifacts] = useState<CompletedArtifacts | undefined>(
    dataset?.artifacts
  )
  const [loading, setLoading] = useState(
    Boolean(datasetId) && !dataset?.artifacts
  )
  const [error, setError] = useState<string>()

  useEffect(() => {
    if (!datasetId) {
      setArtifacts(undefined)
      setLoading(false)
      return
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const load = async () => {
      try {
        const result = await getDatasetArtifacts(datasetId)
        if (cancelled) return
        if (!result || typeof result.status !== 'string') {
          setError('Failed to load artifacts.')
          setLoading(false)
          return
        }
        if (result.status === 'completed') {
          setArtifacts(result)
          setDatasetArtifacts(datasetId, result)
          setLoading(false)
          return
        }
        if (result.status === 'failed') {
          setError(result.error ?? 'Analysis failed.')
          setLoading(false)
          return
        }
        // Still processing — keep spinner and poll.
        setLoading(true)
        timer = setTimeout(load, 2000)
      } catch (reason) {
        if (!cancelled) {
          setError(
            reason instanceof Error
              ? reason.message
              : 'Failed to load artifacts.'
          )
          setLoading(false)
        }
      }
    }

    setError(undefined)

    // Paint from store when we already have a terminal result so we do not
    // refetch (and risk clobbering) completed/failed artifacts. Only hit the
    // API when the store has nothing yet or the analysis is still processing.
    // Do not depend on dataset.artifacts in the effect deps — that causes a
    // fetch loop when we write back via setDatasetArtifacts. setDatasetArtifacts
    // is a stable zustand action so the dependency array size stays constant.
    if (dataset?.artifacts) {
      setArtifacts(dataset.artifacts)
      setLoading(false)
      if (
        dataset.artifacts.status === 'completed' ||
        dataset.artifacts.status === 'failed'
      ) {
        return () => {
          cancelled = true
          if (timer) clearTimeout(timer)
        }
      }
    } else {
      setLoading(true)
    }

    void load()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [datasetId, setDatasetArtifacts])

  // Keep local artifacts in sync when chat (or anything else) updates the store
  // so newly generated charts appear without a full page refresh.
  useEffect(() => {
    if (dataset?.artifacts) {
      setArtifacts(dataset.artifacts)
    }
  }, [dataset?.artifacts])

  const content = () => {
    if (!datasetId || !dataset) return <ArtifactEmptyState tab={tab} />
    if (loading)
      return (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <LoaderCircle className="size-4 animate-spin" />
          Analysis in progress…
        </div>
      )
    if (error)
      return (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )
    if (!artifacts) return <ArtifactEmptyState tab={tab} />

    if (tab === 'Preview') {
      const preview = artifacts.preview ?? {
        columns: [] as string[],
        rows: [] as Record<string, unknown>[],
        total_rows: 0,
        total_cols: 0,
      }
      // Backend may send column names as strings or as { name, type } objects.
      const rawColumns = Array.isArray(preview.columns) ? preview.columns : []
      const columns = rawColumns.map((col) => {
        if (typeof col === 'string') return col
        if (col && typeof col === 'object' && 'name' in col) {
          return String((col as { name: unknown }).name)
        }
        return String(col)
      })
      const rows = Array.isArray(preview.rows) ? preview.rows : []
      return (
        <PreviewContent
          columns={columns}
          rows={rows}
          meta={{
            rows: Number(preview.total_rows) || rows.length,
            columns: Number(preview.total_cols) || columns.length,
            fileSize: 'Cleaned CSV',
            lastUpdated: 'after analysis',
          }}
        />
      )
    }

    if (tab === 'Charts') {
      const apiInteractiveCharts = Array.isArray(artifacts.chartData) ? artifacts.chartData : []
      const staticCharts = Array.isArray(artifacts.charts) ? artifacts.charts : []

      // Support both backend contracts:
      // 1) chartData[] contains the interactive payload directly.
      // 2) charts[] contains the rendered image plus the same payload fields.
      // The second contract lets heatmaps/confusion matrices become interactive
      // without changing the report's rendered PDF.
      const promotedStaticCharts = staticCharts
        .filter(
          (chart): chart is ChartArtifact & {
            type: NonNullable<ChartArtifact['type']>
            title: string
            labels: NonNullable<ChartArtifact['labels']>
            datasets: NonNullable<ChartArtifact['datasets']>
          } =>
            Boolean(
              chart?.type &&
              chart?.title &&
              Array.isArray(chart?.labels) &&
              Array.isArray(chart?.datasets),
            ),
        )
        .map((chart) => ({
          id: Number(chart.id),
          type: chart.type,
          title: chart.title,
          xAxisLabel: chart.xAxisLabel,
          yAxisLabel: chart.yAxisLabel,
          labels: chart.labels,
          datasets: chart.datasets,
          options: chart.options,
        }))

      const byId = new Map<number, ChartDataItem>()
      ;[...apiInteractiveCharts, ...promotedStaticCharts].forEach((chart) => {
        if (!byId.has(Number(chart.id))) byId.set(Number(chart.id), chart)
      })
      const interactiveCharts = Array.from(byId.values()).sort(
        (a, b) => Number(a.id) - Number(b.id),
      )

      if (interactiveCharts.length > 0) {
        return <ChartsDashboard chartData={interactiveCharts} />
      }

      // No interactive data at all — fall back to static images.
      if (staticCharts.length > 0) {
        return (
          <div className="grid grid-cols-1 gap-6 overflow-y-auto md:grid-cols-2">
            {staticCharts.map((chart, index) => (
              <ChartImage key={chart.id} url={chart.url} index={index} />
            ))}
          </div>
        )
      }
      return <ChartsDashboard chartData={[]} />
    }

    if (tab === 'Insights') {
      const insights = artifacts.insights

      if (Array.isArray(insights)) {
        return (
          <InsightsContent
            insights={insights.map((description, index) => ({
              id: String(index),
              title: `Insight ${index + 1}`,
              description,
              tone: index === 0 ? 'positive' : 'neutral',
            }))}
          />
        )
      }

      if (!insights) {
        return <ArtifactEmptyState tab="Insights" />
      }

      return <InsightsReportContent insights={insights} />
    }

    if (tab === 'Statistics') {
      return (
        <DatasetStatisticsView
          statistics={normalizeStatisticsArtifact(artifacts.statistics)}
        />
      )
    }

    // ─── REPORT TAB ───
    if (!artifacts.report?.url) return <ArtifactEmptyState tab="Report" />
    return (
      <EmbeddedReportViewer
        reportUrl={artifacts.report.url}
        datasetName={dataset.name}
      />
    )
  }

  return (
    <section
      aria-label="Artifact panel"
      className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-hidden p-5"
    >
      <div className="flex flex-wrap gap-1 rounded-lg bg-muted p-1">
        {tabs.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setTab(item)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm transition-colors',
              tab === item
                ? 'bg-background font-medium shadow-xs text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {item}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card p-5 shadow-xs"
      >
        {/* min-h-0 is required here: without it this flex child grows to fit
            all of its content (every chart card) instead of respecting the
            panel's height, so anything past the first row gets clipped by
            the parent's overflow-hidden instead of being scrollable. */}
        <div className="flex min-h-0 flex-1 flex-col">{content()}</div>
      </div>
    </section>
  )
}