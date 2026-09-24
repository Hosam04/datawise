'use client'

import { useState } from 'react'
import type { ChartDataItem } from '@/types/artifacts'
import { formatValue, formatTick, truncate, getBoxStats, type BoxStats } from './data-transform'

export function BoxPlotRenderer({ chart, isExpanded = false }: { chart: ChartDataItem; isExpanded?: boolean }) {
  const stats = getBoxStats(chart)
  const [hovered, setHovered] = useState<number | null>(null)

  if (stats.length === 0) {
    return (
      <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
        No box plot data available.
      </div>
    )
  }

  const values = stats.flatMap((item) => [
    item.min, item.q1, item.median, item.q3, item.max, ...item.outliers,
  ])
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const width = 1000
  const height = isExpanded ? 560 : 420
  const left = 90
  const right = 30
  const top = 32
  const bottom = 86
  const plotWidth = width - left - right
  const plotHeight = height - top - bottom
  const xStep = plotWidth / Math.max(1, stats.length)
  const y = (value: number) => top + ((max - value) / range) * plotHeight

  return (
    <div className="relative size-full overflow-hidden">
      {hovered !== null && (
        <div className="pointer-events-none absolute right-4 top-4 z-10 rounded-lg border border-border bg-card/95 px-3 py-2 text-xs shadow-md tabular-nums">
          <p className="font-semibold text-foreground">{stats[hovered].label}</p>
          <p>Min: {formatValue(stats[hovered].min)}</p>
          <p>Q1: {formatValue(stats[hovered].q1)}</p>
          <p>Median: {formatValue(stats[hovered].median)}</p>
          <p>Q3: {formatValue(stats[hovered].q3)}</p>
          <p>Max: {formatValue(stats[hovered].max)}</p>
          {stats[hovered].outliers.length > 0 && (
            <p>Outliers: {stats[hovered].outliers.length}</p>
          )}
        </div>
      )}

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="size-full"
        role="img"
        aria-label={`${chart.title} box plot`}
      >
        <line x1={left} y1={top} x2={left} y2={height - bottom} stroke="var(--color-border)" />
        <line x1={left} y1={height - bottom} x2={width - right} y2={height - bottom} stroke="var(--color-border)" />

        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const value = max - range * tick
          const py = y(value)
          return (
            <g key={tick}>
              <line
                x1={left}
                y1={py}
                x2={width - right}
                y2={py}
                stroke="var(--color-border)"
                opacity={0.35}
                strokeDasharray="4 5"
              />
              <text
                x={left - 10}
                y={py + 4}
                textAnchor="end"
                fontSize={isExpanded ? 13 : 11}
                fill="var(--color-muted-foreground)"
              >
                {formatTick(value)}
              </text>
            </g>
          )
        })}

        {stats.map((item, index) => {
          const cx = left + xStep * index + xStep / 2
          const boxWidth = Math.min(xStep * 0.48, 90)
          const boxX = cx - boxWidth / 2

          return (
            <g
              key={`${item.label}-${index}`}
              onMouseEnter={() => setHovered(index)}
              onMouseLeave={() => setHovered(null)}
              className="cursor-crosshair"
            >
              {/* Whiskers */}
              <line x1={cx} y1={y(item.min)} x2={cx} y2={y(item.max)} stroke={item.color} strokeWidth={2} />
              <line x1={cx - boxWidth * 0.25} y1={y(item.min)} x2={cx + boxWidth * 0.25} y2={y(item.min)} stroke={item.color} strokeWidth={2} />
              <line x1={cx - boxWidth * 0.25} y1={y(item.max)} x2={cx + boxWidth * 0.25} y2={y(item.max)} stroke={item.color} strokeWidth={2} />

              {/* IQR box + median */}
              <rect
                x={boxX}
                y={y(item.q3)}
                width={boxWidth}
                height={Math.max(2, y(item.q1) - y(item.q3))}
                fill={item.color}
                fillOpacity={0.2}
                stroke={item.color}
                strokeWidth={2}
                rx={4}
              />
              <line x1={boxX} y1={y(item.median)} x2={boxX + boxWidth} y2={y(item.median)} stroke={item.color} strokeWidth={3} />

              {/* Outliers: individual points, matching the PDF. */}
              {item.outliers.map((outlier, outlierIndex) => (
                <circle
                  key={`${outlier}-${outlierIndex}`}
                  cx={cx}
                  cy={y(outlier)}
                  r={isExpanded ? 4 : 3}
                  fill={item.color}
                  fillOpacity={0.8}
                />
              ))}

              <text
                x={cx}
                y={height - bottom + 28}
                textAnchor="middle"
                fontSize={isExpanded ? 13 : 11}
                fill="var(--color-muted-foreground)"
              >
                {truncate(item.label, 18)}
              </text>
            </g>
          )
        })}

        {/* Axis titles — were completely missing on box plots */}
        {chart.yAxisLabel && (
          <text
            x={16}
            y={top + plotHeight / 2}
            textAnchor="middle"
            transform={`rotate(-90 16 ${top + plotHeight / 2})`}
            fontSize={isExpanded ? 12 : 11}
            fill="var(--color-muted-foreground)"
          >
            {chart.yAxisLabel}
          </text>
        )}
        {chart.xAxisLabel && (
          <text
            x={left + plotWidth / 2}
            y={height - 10}
            textAnchor="middle"
            fontSize={isExpanded ? 12 : 11}
            fill="var(--color-muted-foreground)"
          >
            {chart.xAxisLabel}
          </text>
        )}
      </svg>
    </div>
  )
}