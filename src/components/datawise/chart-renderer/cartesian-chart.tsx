'use client'

import { useMemo } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { normalizeChartType } from '@/lib/chart-utils'
import type { ChartDataItem } from '@/types/artifacts'
import {
  colorForDataset,
  formatTick,
  legendProps,
  tickStyle,
  type ChartRow,
} from './types'
import { toRows, truncate } from './data-transform'
import { ChartTooltip } from './chart-tooltip'

export function CartesianChart({ chart, isExpanded = false }: { chart: ChartDataItem; isExpanded?: boolean }) {
  const rows = useMemo(() => {
    const built = toRows(chart)
    if (normalizeChartType(chart.type) === 'histogram' && built.length > 1) {
      const allNumeric = built.every((r) => Number.isFinite(Number(r.label)))
      if (allNumeric) {
        return [...built].sort((a, b) => Number(a.label) - Number(b.label))
      }
    }
    return built
  }, [chart])
  const crowded = rows.length > 24
  const hasLegend = chart.datasets.length > 1

  const xAxis = (
    <XAxis
      dataKey="label"
      tick={tickStyle(isExpanded)}
      tickMargin={6}
      interval="preserveStartEnd"
      minTickGap={crowded ? 20 : 8}
      tickFormatter={(v) => truncate(String(v), isExpanded ? 16 : 10)}
      height={chart.xAxisLabel ? 46 : 30}
      label={
        chart.xAxisLabel
          ? {
              value: chart.xAxisLabel,
              position: 'insideBottom',
              offset: -14,
              fill: 'var(--color-muted-foreground)',
              fontSize: isExpanded ? 12 : 11,
            }
          : undefined
      }
    />
  )

  const yAxis = (
    <YAxis
      tick={tickStyle(isExpanded)}
      tickFormatter={formatTick}
      tickMargin={4}
      width={46}
      label={
        chart.yAxisLabel
          ? {
              value: chart.yAxisLabel,
              angle: -90,
              position: 'insideLeft',
              offset: 8,
              fill: 'var(--color-muted-foreground)',
              fontSize: isExpanded ? 12 : 11,
            }
          : undefined
      }
    />
  )

  const grid = (
    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.5} />
  )

  const tooltip = (
    <Tooltip
      content={<ChartTooltip />}
      cursor={
        normalizeChartType(chart.type) === 'bar' || normalizeChartType(chart.type) === 'histogram'
          ? { fill: 'var(--color-muted-foreground)', opacity: 0.08 }
          : undefined
      }
    />
  )

  const margin = {
    top: 12,
    right: 12,
    left: 0,
    bottom: (isExpanded ? 32 : 16) + (hasLegend ? 16 : 0),
  }

  if (normalizeChartType(chart.type) === 'line') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={margin}>
          {grid}
          {xAxis}
          {yAxis}
          {tooltip}
          {hasLegend && <Legend {...legendProps(isExpanded)} />}
          {chart.datasets.map((dataset, index) => (
            <Line
              key={dataset.label || index}
              type="monotone"
              dataKey={`series_${index}`}
              name={dataset.label || `Series ${index + 1}`}
              stroke={colorForDataset(chart, index)}
              strokeWidth={isExpanded ? 2.5 : 2}
              dot={rows.length > 60 ? false : { r: isExpanded ? 3.5 : 2.5 }}
              activeDot={{ r: isExpanded ? 5 : 4 }}
              isAnimationActive={rows.length <= 200}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        data={rows}
        margin={margin}
        barCategoryGap={normalizeChartType(chart.type) === 'histogram' ? '4%' : '22%'}
      >
        {grid}
        {xAxis}
        {yAxis}
        {tooltip}
        {hasLegend && <Legend {...legendProps(isExpanded)} />}
        {chart.datasets.map((dataset, index) => (
          <Bar
            key={dataset.label || index}
            dataKey={`series_${index}`}
            name={dataset.label || `Series ${index + 1}`}
            fill={colorForDataset(chart, index)}
            fillOpacity={0.85}
            radius={normalizeChartType(chart.type) === 'histogram' ? [2, 2, 0, 0] : [4, 4, 0, 0]}
            maxBarSize={normalizeChartType(chart.type) === 'histogram' ? undefined : isExpanded ? 64 : 48}
            isAnimationActive={rows.length <= 200}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}