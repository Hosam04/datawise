'use client'

import { useState, useMemo } from 'react'
import {
  BarChart3, LayoutDashboard, Activity, Search, SlidersHorizontal,
  Grid3X3, LayoutList, PieChart, LineChart, BarChart, ScatterChart,
  BoxSelect, AlertCircle, TrendingUp
} from 'lucide-react'
import { ChartRenderer } from '@/components/datawise/chart-renderer'
import type { ChartDataItem } from '@/types/artifacts'
import { cn } from '@/lib/utils'
import { chartTypeLabel, isWideChartType, normalizeChartType } from '@/lib/chart-utils'

interface ChartsDashboardProps {
  chartData: ChartDataItem[] | undefined
}

const TYPE_ICONS: Record<string, React.ElementType> = {
  bar: BarChart,
  line: LineChart,
  pie: PieChart,
  scatter: ScatterChart,
  histogram: BarChart,
  heatmap: Grid3X3,
  boxplot: BoxSelect,
}

function getTypeIcon(type?: string) {
  if (!type) return Activity
  return TYPE_ICONS[normalizeChartType(type)] ?? Activity
}

const TYPE_CATEGORIES: Record<string, string> = {
  bar: 'comparison',
  line: 'trend',
  pie: 'distribution',
  histogram: 'distribution',
  scatter: 'correlation',
  heatmap: 'correlation',
  boxplot: 'distribution',
}

const CATEGORY_LABELS: Record<string, { label: string; icon: React.ElementType }> = {
  all: { label: 'All Charts', icon: LayoutDashboard },
  comparison: { label: 'Comparisons', icon: BarChart },
  trend: { label: 'Trends', icon: TrendingUp },
  distribution: { label: 'Distributions', icon: PieChart },
  correlation: { label: 'Correlations', icon: Activity },
  other: { label: 'Others', icon: SlidersHorizontal },
}

function EmptyFilterState({ filterLabel }: { filterLabel: string }) {
  return (
    <div className="col-span-full flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-muted/30 py-16">
      <div className="rounded-full bg-muted p-3">
        <AlertCircle className="size-6 text-muted-foreground/50" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-muted-foreground">No charts in &quot;{filterLabel}&quot;</p>
        <p className="text-xs text-muted-foreground/60 mt-0.5">Try another category or clear the search</p>
      </div>
    </div>
  )
}

export function ChartsDashboard({ chartData }: ChartsDashboardProps) {
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'compact'>('grid')

  const { categories, typeCounts, chartsByCategory } = useMemo(() => {
    if (!chartData || !Array.isArray(chartData)) {
      return {
        categories: ['all'],
        typeCounts: {} as Record<string, number>,
        chartsByCategory: {} as Record<string, ChartDataItem[]>,
      }
    }
    const counts: Record<string, number> = {}
    const byCat: Record<string, ChartDataItem[]> = {}
    const cats = new Set<string>()
    chartData.forEach(chart => {
      const type = normalizeChartType(chart?.type)
      const cat = TYPE_CATEGORIES[type] || 'other'
      counts[type] = (counts[type] || 0) + 1
      cats.add(cat)
      if (!byCat[cat]) byCat[cat] = []
      byCat[cat].push(chart)
    })
    const sortedCats = Array.from(cats).sort((a, b) => (byCat[b]?.length ?? 0) - (byCat[a]?.length ?? 0))
    return {
      categories: ['all', ...sortedCats],
      typeCounts: counts,
      chartsByCategory: byCat,
    }
  }, [chartData])

  const filteredCharts = useMemo(() => {
    if (!chartData || !Array.isArray(chartData)) return []
    const query = searchQuery.trim().toLowerCase()
    return chartData.filter(chart => {
      const type = normalizeChartType(chart?.type)
      const category = TYPE_CATEGORIES[type] || 'other'
      const title = (chart?.title ?? '').toString().toLowerCase()
      const matchesCategory = activeCategory === 'all' || activeCategory === category
      const matchesSearch = !query || title.includes(query) || type.includes(query)
      return matchesCategory && matchesSearch
    })
  }, [chartData, activeCategory, searchQuery])

  // Keep the exact backend/report order. The previous implementation moved
  // wide charts (box plots/heatmaps) to the front, so the dashboard no longer
  // matched the PDF sequence.
  const sortedCharts = useMemo(() => {
    return [...filteredCharts].sort((a, b) => Number(a?.id ?? 0) - Number(b?.id ?? 0))
  }, [filteredCharts])

  if (chartData === undefined) {
    return (
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="h-80 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      </div>
    )
  }

  if (!chartData || chartData.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-muted-foreground">
        <div className="rounded-full bg-muted p-4">
          <BarChart3 className="size-8" />
        </div>
        <p className="text-sm font-medium">No charts generated</p>
        <p className="text-xs">Upload a dataset to generate visualizations</p>
      </div>
    )
  }

  const activeLabel = CATEGORY_LABELS[activeCategory]?.label ?? activeCategory

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      {/* Single compact toolbar: category filters + search + view toggle.
          The old header + KPI row were meta-stats about the dashboard itself
          (their numbers already live in the chips), so removing them hands
          ~170px of vertical space back to the charts. */}
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {categories.map((cat) => {
          const catInfo = CATEGORY_LABELS[cat] || CATEGORY_LABELS.other
          const CatIcon = catInfo.icon
          const count = cat === 'all'
            ? chartData.length
            : (chartsByCategory[cat]?.length ?? 0)
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all',
                activeCategory === cat
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground'
              )}
            >
              <CatIcon className="size-3.5" />
              <span>{catInfo.label}</span>
              <span className={cn(
                'ml-0.5 rounded-full px-1.5 py-0.5 text-[10px]',
                activeCategory === cat ? 'bg-primary-foreground/20' : 'bg-background'
              )}>
                {count}
              </span>
            </button>
          )
        })}
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search charts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 w-44 rounded-lg border border-border bg-background pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div className="flex rounded-lg border border-border bg-background p-0.5">
            <button
              onClick={() => setViewMode('grid')}
              aria-label="Grid view"
              className={cn('rounded p-1.5 transition-colors', viewMode === 'grid' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground')}
            >
              <Grid3X3 className="size-3.5" />
            </button>
            <button
              onClick={() => setViewMode('compact')}
              aria-label="Compact view"
              className={cn('rounded p-1.5 transition-colors', viewMode === 'compact' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground')}
            >
              <LayoutList className="size-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Charts Grid — this is the region that actually scrolls. It needs both
          flex-1 (to claim the remaining vertical space from the flex column
          above) and min-h-0 (so it doesn't just grow to fit all charts and
          get clipped by an ancestor's overflow-hidden instead of scrolling). */}
      <div className="min-h-0 flex-1 overflow-y-auto pr-1 -mr-1">
        <div className={cn(
          'grid auto-rows-fr gap-5',
          viewMode === 'grid'
            ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
            : 'grid-cols-1 md:grid-cols-2'
        )}>
          {sortedCharts.length === 0 ? (
            <EmptyFilterState filterLabel={activeLabel} />
          ) : (
            sortedCharts.map((chart, index) => {
              const isWide = isWideChartType(chart?.type) || (chart?.labels?.length ?? 0) > 24
              return (
                <div
                  key={chart?.id ?? `chart-${index}`}
                  className={cn('min-w-0', isWide && viewMode === 'grid' && 'md:col-span-2')}
                >
                  <ChartRenderer chart={chart} />
                </div>
              )
            })
          )}
        </div>


        {/* Type Legend */}
        {Object.keys(typeCounts).length > 0 && (
          <div className="mt-5 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-muted/30 px-4 py-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Available types:
            </span>
            {Object.entries(typeCounts).map(([type, count]) => {
              const TypeIcon = getTypeIcon(type)
              return (
                <div key={type} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <TypeIcon className="size-3.5" />
                  <span className="capitalize">{chartTypeLabel(type)}</span>
                  <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] font-medium">
                    ×{count}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}