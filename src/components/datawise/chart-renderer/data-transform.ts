import { normalizeChartType } from '@/lib/chart-utils'
import type { ChartDataItem, ChartOptions } from '@/types/artifacts'
import type { ChartRow } from './types'
import { asNumber, formatValue, formatTick, REPORT_BLUE, truncate } from './types'

export function toRows(chart: ChartDataItem): ChartRow[] {
  const raw = chart.labels.map((label, index) => {
    const row: ChartRow = { label: String(label ?? '') }
    chart.datasets.forEach((dataset, datasetIndex) => {
      row[`series_${datasetIndex}`] = asNumber(dataset.data[index]) ?? 0
    })
    return row
  })

  const isBar = normalizeChartType(chart.type) === 'bar'
  if (!isBar || raw.length <= 1) return raw

  const uniqueLabels = new Set(raw.map((r) => r.label))
  if (uniqueLabels.size === raw.length) return raw

  const seriesKeys = chart.datasets.map((_, i) => `series_${i}`)
  const sums = new Map<string, { count: number; totals: number[] }>()
  for (const row of raw) {
    const key = String(row.label)
    let entry = sums.get(key)
    if (!entry) {
      entry = { count: 0, totals: seriesKeys.map(() => 0) }
      sums.set(key, entry)
    }
    entry.count += 1
    seriesKeys.forEach((sk, i) => {
      entry!.totals[i] += Number(row[sk] ?? 0)
    })
  }

  return Array.from(sums.entries()).map(([label, { count, totals }]) => {
    const row: ChartRow = { label }
    seriesKeys.forEach((sk, i) => {
      row[sk] = count > 0 ? totals[i] / count : 0
    })
    return row
  })
}

export interface BoxStats {
  label: string
  min: number
  q1: number
  median: number
  q3: number
  max: number
  color: string
  outliers: number[]
}

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0
  const position = (sorted.length - 1) * q
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  if (lower === upper) return sorted[lower]
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower)
}

function finiteNumbers(values: unknown): number[] {
  if (!Array.isArray(values)) return []
  return values
    .map(asNumber)
    .filter((value): value is number => value !== undefined)
    .sort((a, b) => a - b)
}

function statsFromValues(values: number[], label: string, color: string): BoxStats {
  const sorted = [...values].sort((a, b) => a - b)
  const q1 = quantile(sorted, 0.25)
  const median = quantile(sorted, 0.5)
  const q3 = quantile(sorted, 0.75)
  const iqr = q3 - q1
  const lowerFence = q1 - 1.5 * iqr
  const upperFence = q3 + 1.5 * iqr
  const inWhisker = sorted.filter((v) => v >= lowerFence && v <= upperFence)
  const outliers = sorted.filter((v) => v < lowerFence || v > upperFence)

  return {
    label,
    min: inWhisker[0] ?? sorted[0] ?? 0,
    q1,
    median,
    q3,
    max: inWhisker[inWhisker.length - 1] ?? sorted[sorted.length - 1] ?? 0,
    color,
    outliers,
  }
}

export function getBoxStats(chart: ChartDataItem): BoxStats[] {
  const options = chart.options as (ChartOptions & {
    boxplot?: Array<{
      label?: string
      min?: number
      q1?: number
      median?: number
      q3?: number
      max?: number
      values?: number[]
      outliers?: number[]
    }>
    box_plot?: Array<{
      label?: string
      min?: number
      q1?: number
      median?: number
      q3?: number
      max?: number
      values?: number[]
      outliers?: number[]
    }>
    boxes?: Array<{
      label?: string
      min?: number
      q1?: number
      median?: number
      q3?: number
      max?: number
      values?: number[]
      outliers?: number[]
    }>
  }) | undefined

  const optionBoxes = options?.boxplot ?? options?.box_plot ?? options?.boxes
  if (Array.isArray(optionBoxes) && optionBoxes.length > 0) {
    return optionBoxes.map((box, index) => {
      const values = finiteNumbers(box.values)
      const fallback = values.length ? statsFromValues(
        values,
        String(box.label ?? chart.labels[index] ?? `Group ${index + 1}`),
        REPORT_BLUE,
      ) : undefined

      const min = asNumber(box.min) ?? fallback?.min ?? 0
      const q1 = asNumber(box.q1) ?? fallback?.q1 ?? min
      const median = asNumber(box.median) ?? fallback?.median ?? q1
      const q3 = asNumber(box.q3) ?? fallback?.q3 ?? median
      const max = asNumber(box.max) ?? fallback?.max ?? q3
      const rawOutliers = finiteNumbers(box.outliers)

      return {
        label: String(box.label ?? chart.labels[index] ?? `Group ${index + 1}`),
        min,
        q1,
        median,
        q3,
        max,
        color: REPORT_BLUE,
        outliers: rawOutliers.length ? rawOutliers : fallback?.outliers ?? [],
      }
    })
  }

  const groupedDatasets = (chart.datasets ?? [])
    .map((dataset, index) => ({
      dataset,
      index,
      values: finiteNumbers(dataset.data as unknown[]),
    }))
    .filter((entry) => entry.values.length > 0)

  if (groupedDatasets.length > 0) {
    return groupedDatasets.map(({ dataset, index, values }) =>
      statsFromValues(
        values,
        dataset.label || String(chart.labels[index] ?? `Group ${index + 1}`),
        REPORT_BLUE,
      ),
    )
  }

  return []
}

export interface HeatmapCell {
  x: string
  y: string
  value: number
}

export function getHeatmapData(chart: ChartDataItem): {
  xLabels: string[]
  yLabels: string[]
  cells: HeatmapCell[]
} {
  const options = chart.options as (ChartOptions & {
    x?: Array<string | number>
    y?: Array<string | number>
    values?: number[][]
    heat_map?: { x?: Array<string | number>; y?: Array<string | number>; z?: number[][] }
    confusion_matrix?: { labels?: Array<string | number>; matrix?: number[][] }
  }) | undefined

  const heatmapOptions = options?.heatmap ?? options?.heat_map
  const confusion = options?.confusion_matrix

  const matrix =
    (Array.isArray(heatmapOptions?.z) && heatmapOptions.z.length > 0 ? heatmapOptions.z : undefined) ??
    (Array.isArray(options?.matrix) && options.matrix.length > 0 ? options.matrix : undefined) ??
    (Array.isArray(options?.z) && options.z.length > 0 ? options.z : undefined) ??
    (Array.isArray(options?.values) && options.values.length > 0 ? options.values : undefined) ??
    (Array.isArray(confusion?.matrix) && confusion.matrix.length > 0 ? confusion.matrix : undefined)

  const xLabels =
    (heatmapOptions?.x?.length ? heatmapOptions.x.map(String) : undefined) ??
    (confusion?.labels?.length ? confusion.labels.map(String) : undefined) ??
    (options?.x?.length ? options.x.map(String) : undefined) ??
    (chart.labels?.length ? chart.labels.map(String) : [])

  const yLabels =
    (heatmapOptions?.y?.length ? heatmapOptions.y.map(String) : undefined) ??
    (confusion?.labels?.length ? confusion.labels.map(String) : undefined) ??
    (options?.y?.length ? options.y.map(String) : undefined) ??
    (options?.yLabels?.length ? options.yLabels.map(String) : undefined) ??
    (chart.datasets?.length ? chart.datasets.map((d) => d.label || 'Series') : [])

  if (matrix && matrix.length > 0) {
    return {
      xLabels,
      yLabels,
      cells: matrix.flatMap((row, rowIndex) =>
        row.map((value, columnIndex) => ({
          x: xLabels[columnIndex] ?? String(columnIndex + 1),
          y: yLabels[rowIndex] ?? String(rowIndex + 1),
          value: asNumber(value) ?? 0,
        })),
      ),
    }
  }

  if (!chart.datasets || chart.datasets.length === 0) {
    return { xLabels, yLabels, cells: [] }
  }

  const cells: HeatmapCell[] = []
  chart.datasets.forEach((dataset, rowIndex) => {
    if (!Array.isArray(dataset.data)) return
    dataset.data.forEach((value, columnIndex) => {
      cells.push({
        x: xLabels[columnIndex] ?? String(columnIndex + 1),
        y: yLabels[rowIndex] ?? dataset.label ?? String(rowIndex + 1),
        value: asNumber(value) ?? 0,
      })
    })
  })

  return { xLabels, yLabels, cells }
}

export { formatValue, formatTick, truncate, asNumber }