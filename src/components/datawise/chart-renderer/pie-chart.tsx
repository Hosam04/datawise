'use client'

import { useMemo } from 'react'
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { ChartDataItem } from '@/types/artifacts'
import { asNumber, DEFAULT_PALETTE, legendProps } from './types'
import { ChartTooltip } from './chart-tooltip'

export function PieChartRenderer({ chart, isExpanded = false }: { chart: ChartDataItem; isExpanded?: boolean }) {
  const dataset = chart.datasets[0]
  const rows = useMemo(() => {
    const raw = chart.labels.map((label, index) => ({
      name: String(label ?? index + 1),
      value: asNumber(dataset?.data[index]) ?? 0,
    }))
    const unique = new Set(raw.map((r) => r.name))
    if (unique.size === raw.length) return raw
    const sums = new Map<string, number>()
    for (const r of raw) sums.set(r.name, (sums.get(r.name) ?? 0) + r.value)
    return Array.from(sums.entries()).map(([name, value]) => ({ name, value }))
  }, [chart, dataset])

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart margin={{ top: 12, right: 12, bottom: 12, left: 12 }}>
        <Tooltip content={<ChartTooltip />} />
        <Legend {...legendProps(isExpanded)} />
        <Pie
          data={rows}
          dataKey="value"
          nameKey="name"
          outerRadius={isExpanded ? '78%' : '68%'}
          innerRadius={isExpanded ? '38%' : '0%'}
          paddingAngle={rows.length > 1 ? 2 : 0}
          stroke="transparent"
          label={isExpanded}
          labelLine={isExpanded}
          isAnimationActive={rows.length <= 60}
        >
          {rows.map((_, index) => (
            <Cell key={index} fill={DEFAULT_PALETTE[index % DEFAULT_PALETTE.length]} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  )
}