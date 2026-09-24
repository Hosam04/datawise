'use client'

import { formatValue, type TooltipEntry } from './types'

export function ChartTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipEntry[]
  label?: string | number
}) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div className="max-w-65 rounded-lg border border-border bg-card/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      {label !== undefined && label !== '' && (
        <p className="mb-1 font-semibold text-foreground">{String(label)}</p>
      )}
      <div className="flex flex-col gap-1">
        {payload.slice(0, 8).map((entry, i) => (
          <div key={i} className="flex items-center gap-2">
            <span
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: entry.color || entry.fill || 'var(--color-muted-foreground)' }}
            />
            <span className="text-muted-foreground">{entry.name}:</span>
            <span className="ml-auto pl-3 font-medium text-foreground tabular-nums">
              {formatValue(entry.value)}
            </span>
            {typeof entry.payload?.percent === 'number' && (
              <span className="text-muted-foreground">
                ({(entry.payload.percent * 100).toFixed(1)}%)
              </span>
            )}
          </div>
        ))}
        {payload.length > 8 && (
          <p className="text-muted-foreground">+{payload.length - 8} more…</p>
        )}
      </div>
    </div>
  )
}