'use client'

import type { ChartDataItem } from '@/types/artifacts'
import { normalizeChartType } from '@/lib/chart-utils'
import { CartesianChart } from './cartesian-chart'
import { ScatterChartRenderer } from './scatter-chart'
import { PieChartRenderer } from './pie-chart'
import { BoxPlotRenderer } from './box-plot'
import { HeatmapRenderer } from './heatmap'

export function ChartCanvas({ chart, isExpanded = false }: { chart: ChartDataItem; isExpanded?: boolean }) {
  const normalizedType = normalizeChartType(chart?.type)

  if (normalizedType === 'pie') return <PieChartRenderer chart={chart} isExpanded={isExpanded} />
  if (normalizedType === 'boxplot') return <BoxPlotRenderer chart={chart} isExpanded={isExpanded} />
  if (normalizedType === 'heatmap') return <HeatmapRenderer chart={chart} isExpanded={isExpanded} />
  if (normalizedType === 'scatter') return <ScatterChartRenderer chart={chart} isExpanded={isExpanded} />

  return <CartesianChart chart={chart} isExpanded={isExpanded} />
}