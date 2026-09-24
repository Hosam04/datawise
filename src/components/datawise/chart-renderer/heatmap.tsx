'use client'

import { useMemo, useState } from 'react'
import type { ChartDataItem } from '@/types/artifacts'
import { asNumber, formatValue, formatTick, truncate, getHeatmapData, type HeatmapCell } from './data-transform'

export function HeatmapRenderer({ chart, isExpanded = false }: { chart: ChartDataItem; isExpanded?: boolean }) {
  const { xLabels, yLabels, cells } = useMemo(() => getHeatmapData(chart), [chart])
  const [hovered, setHovered] = useState<HeatmapCell | null>(null)

  if (cells.length === 0) {
    return (
      <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
        No heatmap data available.
      </div>
    )
  }

  const values = cells.map((cell) => cell.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const rotateX = xLabels.length > 10
  const width = 1000
  const height = isExpanded ? 560 : 420

  const charW = isExpanded ? 7 : 6.2
  const yTickWidth = Math.max(0, ...yLabels.map((l) => l.length)) * charW
  const left = Math.min(
    260,
    Math.max(90, Math.round(yTickWidth) + (chart.yAxisLabel ? 36 : 20)),
  )

  const top = 42
  const right = 30
  const bottom = rotateX ? Math.min(160, 70 + xLabels.length) : 48
  const plotHeight = height - top - bottom
  const cellWidth = (width - left - right) / Math.max(1, xLabels.length)
  const cellHeight = plotHeight / Math.max(1, yLabels.length)
  const showValues = xLabels.length <= 14 && yLabels.length <= 14 && cellWidth > 34

  const cellColor = (value: number) => {
    const ratio = Math.max(0, Math.min(1, (value - min) / range))
    const start = [247, 251, 255]
    const end = [8, 69, 148]
    const rgb = start.map((channel, i) =>
      Math.round(channel + (end[i] - channel) * ratio),
    )
    return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`
  }

  const cellTextColor = (value: number) => {
    const ratio = Math.max(0, Math.min(1, (value - min) / range))
    return ratio > 0.52 ? '#ffffff' : '#0f172a'
  }

  return (
    <div className="relative size-full overflow-hidden">
      {hovered && (
        <div className="pointer-events-none absolute right-4 top-4 z-10 rounded-lg border border-border bg-card/95 px-3 py-2 text-xs shadow-md">
          <p className="font-semibold text-foreground">{hovered.y}</p>
          <p>{hovered.x}: <span className="tabular-nums">{formatValue(hovered.value)}</span></p>
        </div>
      )}

      <svg viewBox={`0 0 ${width} ${height}`} className="size-full" role="img" aria-label={`${chart.title} heatmap`}>
        {cells.map((cell) => {
          const column = xLabels.indexOf(cell.x)
          const row = yLabels.indexOf(cell.y)
          if (column < 0 || row < 0) return null

          const cx = left + column * cellWidth
          const cy = top + row * cellHeight

          return (
            <g key={`${cell.y}-${cell.x}`}>
              <rect
                x={cx}
                y={cy}
                width={Math.max(1, cellWidth - 1.5)}
                height={Math.max(1, cellHeight - 1.5)}
                rx={2}
                fill={cellColor(cell.value)}
                onMouseEnter={() => setHovered(cell)}
                onMouseLeave={() => setHovered(null)}
                className="cursor-crosshair"
              />
              {showValues && (
                <text
                  x={cx + cellWidth / 2}
                  y={cy + cellHeight / 2 + 3.5}
                  textAnchor="middle"
                  fontSize={isExpanded ? 12 : 10}
                  fill={cellTextColor(cell.value)}
                  pointerEvents="none"
                >
                  {formatTick(cell.value)}
                </text>
              )}
            </g>
          )
        })}

        {xLabels.map((label, index) => {
          const cx = left + index * cellWidth + cellWidth / 2
          const cy = height - bottom + 20
          return (
            <text
              key={`x-${label}-${index}`}
              x={cx}
              y={cy}
              transform={rotateX ? `rotate(-40 ${cx} ${cy})` : undefined}
              textAnchor={rotateX ? 'end' : 'middle'}
              fontSize={isExpanded ? 12 : 10}
              fill="var(--color-muted-foreground)"
            >
              {truncate(label, rotateX ? 12 : isExpanded ? 22 : 14)}
            </text>
          )
        })}

        {yLabels.map((label, index) => (
          <text
            key={`y-${label}-${index}`}
            x={left - 10}
            y={top + index * cellHeight + cellHeight / 2 + 4}
            textAnchor="end"
            fontSize={isExpanded ? 12 : 10}
            fill="var(--color-muted-foreground)"
          >
            {truncate(label, 24)}
          </text>
        ))}

        <defs>
          <linearGradient id={`heatmap-gradient-${chart.id}`} x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#f7fbff" />
            <stop offset="100%" stopColor="#084594" />
          </linearGradient>
        </defs>
        <rect
          x={width - 24}
          y={top}
          width={10}
          height={Math.max(30, plotHeight)}
          fill={`url(#heatmap-gradient-${chart.id})`}
          rx={2}
        />
        <text
          x={width - 8}
          y={top + 4}
          fontSize={9}
          fill="var(--color-muted-foreground)"
        >
          {formatTick(max)}
        </text>
        <text
          x={width - 8}
          y={top + plotHeight}
          fontSize={9}
          fill="var(--color-muted-foreground)"
        >
          {formatTick(min)}
        </text>

        {chart.xAxisLabel && (
          <text
            x={left + (width - left - right) / 2}
            y={height - 4}
            textAnchor="middle"
            fontSize={isExpanded ? 12 : 10}
            fill="var(--color-muted-foreground)"
          >
            {chart.xAxisLabel}
          </text>
        )}
        {chart.yAxisLabel && (
          <text
            x={14}
            y={top + plotHeight / 2}
            textAnchor="middle"
            transform={`rotate(-90 14 ${top + plotHeight / 2})`}
            fontSize={isExpanded ? 12 : 10}
            fill="var(--color-muted-foreground)"
          >
            {chart.yAxisLabel}
          </text>
        )}
      </svg>
    </div>
  )
}