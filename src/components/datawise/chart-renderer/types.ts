import type { ChartDataItem, ChartOptions } from '@/types/artifacts'

export interface ChartRendererProps {
  chart: ChartDataItem
}

export type ChartRow = Record<string, string | number>

export const REPORT_BLUE = '#636efa'

export const DEFAULT_PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444',
  '#06b6d4', '#f97316', '#ec4899', '#84cc16', '#6366f1',
]

const compactFmt = new Intl.NumberFormat('en', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

export function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

export function formatTick(value: unknown): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value ?? '')
  return Math.abs(n) >= 1000 ? compactFmt.format(n) : String(Number(n.toFixed(2)))
}

export function formatValue(value: unknown): string {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return String(value ?? '—')
  if (Math.abs(n) >= 10000) return compactFmt.format(n)
  return Number.isInteger(n) ? n.toLocaleString('en') : n.toFixed(2)
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

export function colorForDataset(chart: ChartDataItem, index: number): string {
  const dataset = chart.datasets[index]
  return (
    dataset?.borderColor ||
    dataset?.backgroundColor ||
    DEFAULT_PALETTE[index % DEFAULT_PALETTE.length]
  )
}

export const tickStyle = (isExpanded: boolean) => ({
  fontSize: isExpanded ? 12 : 10,
  fill: 'var(--color-muted-foreground)',
})

export interface TooltipEntry {
  name?: string | number
  value?: number | string
  color?: string
  fill?: string
  payload?: { percent?: number }
}

export const legendProps = (isExpanded: boolean) => ({
  iconType: 'circle' as const,
  iconSize: 7,
  wrapperStyle: {
    fontSize: isExpanded ? 13 : 11,
    paddingTop: 6,
    color: 'var(--color-muted-foreground)',
  },
})

export { toRows } from './data-transform'