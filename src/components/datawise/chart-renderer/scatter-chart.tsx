'use client'

import { useMemo } from 'react'
import {
  CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { normalizeChartType } from '@/lib/chart-utils'
import type { ChartDataItem } from '@/types/artifacts'
import {
  colorForDataset,
  formatTick,
  legendProps,
  tickStyle,
  asNumber,
} from './types'
import { ChartTooltip } from './chart-tooltip'

export function ScatterChartRenderer({ chart, isExpanded = false }: { chart: ChartDataItem; isExpanded?: boolean }) {
  const series = useMemo(
    () =>
      chart.datasets.map((dataset, index) => ({
        name: dataset.label || `Series ${index + 1}`,
        color: colorForDataset(chart, index),
        points: dataset.data.map((value, i) => ({
          x: asNumber(chart.labels[i]) ?? i,
          y: asNumber(value) ?? 0,
        })),
      })),
    [chart],
  )
  const hasLegend = chart.datasets.length > 1

  const margin = {
    top: 12,
    right: 12,
    left: 0,
    bottom: (isExpanded ? 32 : 16) + (hasLegend ? 16 : 0),
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={margin}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.5} />
        <XAxis
          type="number"
          dataKey="x"
          name={chart.xAxisLabel || 'x'}
          domain={['dataMin', 'dataMax']}
          tick={tickStyle(isExpanded)}
          tickFormatter={formatTick}
          tickMargin={6}
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
        <YAxis
          type="number"
          dataKey="y"
          name={chart.yAxisLabel || 'y'}
          domain={['auto', 'auto']}
          tick={tickStyle(isExpanded)}
          tickFormatter={formatTick}
          width={46}
        />
        <Tooltip
          content={<ChartTooltip />}
          cursor={{ strokeDasharray: '4 4', stroke: 'var(--color-muted-foreground)' }}
        />
        {hasLegend && <Legend {...legendProps(isExpanded)} />}
        {series.map((s) => (
          <Scatter
            key={s.name}
            name={s.name}
            data={s.points}
            fill={s.color}
            fillOpacity={0.75}
            shape="circle"
            isAnimationActive={s.points.length <= 300}
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  )
}