'use client'

import { useState } from 'react'
import { Table, Activity, ShieldAlert } from 'lucide-react'
import { StatCard } from '@/components/dashboard/stat-card'
import { cn } from '@/lib/utils'
import type { ColumnStatistics, StatisticsArtifact } from '@/types/artifacts'
import type { Statistic } from './types'

function formatNumber(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'number') {
    if (Number.isNaN(val)) return '—'
    return val % 1 === 0 ? val.toLocaleString() : val.toFixed(2)
  }
  return String(val)
}

export function DatasetStatisticsView({
  statistics,
}: {
  statistics?: StatisticsArtifact | null
}) {
  const [activeTab, setActiveTab] = useState<'descriptive' | 'correlations' | 'outliers'>('descriptive')

  const descriptive =
    statistics?.descriptive && typeof statistics.descriptive === 'object'
      ? Object.entries(statistics.descriptive)
      : []

  const correlations =
    statistics?.correlations && typeof statistics.correlations === 'object'
      ? (statistics.correlations as Record<string, Record<string, number | null> | string | unknown>)
      : null

  const outliers =
    statistics?.outliers && typeof statistics.outliers === 'object'
      ? (statistics.outliers as Record<string, { count?: number; percentage?: number; note?: string }>)
      : null

  const hasOutliers = outliers && Object.keys(outliers).length > 0
  const hasCorrelations = correlations && Object.keys(correlations).length > 0

  if (!statistics || (descriptive.length === 0 && !hasCorrelations && !hasOutliers)) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-center">
        <Activity className="size-10 text-muted-foreground/50" />
        <p className="text-sm font-medium text-foreground">No numerical statistics available</p>
        <p className="text-xs text-muted-foreground max-w-sm">
          The dataset does not contain sufficient numeric columns or statistics have not finished computing.
        </p>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-hidden">
      {/* Sub-nav */}
      <div className="flex items-center gap-2 border-b border-border pb-3">
        <button
          type="button"
          onClick={() => setActiveTab('descriptive')}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
            activeTab === 'descriptive'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:text-foreground'
          )}
        >
          <Table className="size-3.5" />
          <span>Descriptive ({descriptive.length})</span>
        </button>

        {hasCorrelations && (
          <button
            type="button"
            onClick={() => setActiveTab('correlations')}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
              activeTab === 'correlations'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground'
            )}
          >
            <Activity className="size-3.5" />
            <span>Correlations</span>
          </button>
        )}

        {hasOutliers && (
          <button
            type="button"
            onClick={() => setActiveTab('outliers')}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
              activeTab === 'outliers'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground'
            )}
          >
            <ShieldAlert className="size-3.5" />
            <span>Outliers</span>
          </button>
        )}
      </div>

      {/* Tab: Descriptive — numeric columns show mean/median/std; categorical
          columns surface unique count + top value so every backend field is
          visible, matching the StatisticalEngine output. */}
      {activeTab === 'descriptive' && (
        <div className="flex-1 overflow-auto rounded-xl border border-border">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-muted/80 backdrop-blur-xs">
              <tr className="border-b border-border">
                <th className="px-4 py-3 font-semibold text-foreground">Column</th>
                <th className="px-3 py-3 font-semibold text-foreground">Mean / Mode</th>
                <th className="px-3 py-3 font-semibold text-foreground">Median</th>
                <th className="px-3 py-3 font-semibold text-foreground">Std / Unique</th>
                <th className="px-3 py-3 font-semibold text-foreground">Min</th>
                <th className="px-3 py-3 font-semibold text-foreground">Max</th>
                <th className="px-3 py-3 font-semibold text-foreground">Nulls (%)</th>
                <th className="px-3 py-3 font-semibold text-foreground">Range / Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {descriptive.map(([colName, rawVal]) => {
                const val = (rawVal && typeof rawVal === 'object' ? rawVal : {}) as ColumnStatistics & {
                  unique_count?: number
                  mode?: string | number
                  top_values?: Array<{ value?: string | number; count?: number; percentage?: number }>
                }
                const isNumeric =
                  (val.mean !== undefined && val.mean !== null) ||
                  (val.std !== undefined && val.std !== null) ||
                  (val.median !== undefined && val.median !== null)
                const nullPct =
                  typeof val.null_pct === 'number'
                    ? val.null_pct
                    : val.null_count && val.count
                      ? (Number(val.null_count) / (Number(val.count) + Number(val.null_count))) * 100
                      : 0
                const topValue =
                  val.mode ??
                  (Array.isArray(val.top_values) && val.top_values[0]
                    ? val.top_values[0].value
                    : undefined)
                const uniqueLabel =
                  typeof val.unique_count === 'number' ? val.unique_count : undefined

                return (
                  <tr key={colName} className="hover:bg-muted/40 transition-colors">
                    <td className="px-4 py-2.5 font-medium text-foreground max-w-45 truncate">
                      {colName}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">
                      {isNumeric
                        ? formatNumber(val.mean)
                        : topValue !== undefined
                          ? String(topValue)
                          : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">
                      {isNumeric ? formatNumber(val.median) : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">
                      {isNumeric
                        ? formatNumber(val.std)
                        : uniqueLabel !== undefined
                          ? `${uniqueLabel} unique`
                          : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">{formatNumber(val.min)}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{formatNumber(val.max)}</td>
                    <td className="px-3 py-2.5">
                      {nullPct > 0 ? (
                        <span className="inline-flex items-center rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-400">
                          {formatNumber(nullPct)}%
                        </span>
                      ) : (
                        <span className="text-muted-foreground">0%</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground max-w-50 truncate">
                      {val.note || (val.range !== undefined ? `Range: ${formatNumber(val.range)}` : '—')}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: Correlations */}
      {activeTab === 'correlations' && correlations && (
        <div className="flex-1 overflow-auto rounded-xl border border-border p-4">
          <h3 className="text-sm font-semibold mb-3 text-foreground">Correlation Matrix</h3>
          <div className="overflow-auto">
            <table className="w-full text-center text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-3 py-2 text-left font-semibold text-foreground">Variable</th>
                  {Object.keys(correlations).map((key) => (
                    <th key={key} className="px-3 py-2 font-semibold text-foreground max-w-25 truncate">
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(correlations).map(([rowKey, rowVal]) => (
                  <tr key={rowKey} className="hover:bg-muted/40">
                    <td className="px-3 py-2 text-left font-medium text-foreground max-w-30 truncate">
                      {rowKey}
                    </td>
                    {Object.keys(correlations).map((colKey) => {
                      const cellVal =
                        rowVal && typeof rowVal === 'object' && colKey in rowVal
                          ? (rowVal as Record<string, unknown>)[colKey]
                          : undefined
                      const num = typeof cellVal === 'number' ? cellVal : null

                      return (
                        <td
                          key={colKey}
                          className="px-3 py-2 font-mono text-[11px]"
                          style={{
                            backgroundColor:
                              num !== null
                                ? num > 0
                                  ? `rgba(16, 185, 129, ${Math.min(Math.abs(num), 0.7)})`
                                  : num < 0
                                    ? `rgba(239, 68, 68, ${Math.min(Math.abs(num), 0.7)})`
                                    : undefined
                                : undefined,
                            color: num !== null && Math.abs(num) > 0.4 ? '#ffffff' : undefined,
                          }}
                        >
                          {num !== null ? num.toFixed(2) : '—'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab: Outliers — count/percentage may be numbers or status strings
          (e.g. "N/A" / "Skipped") from the backend outlier view. */}
      {activeTab === 'outliers' && outliers && (
        <div className="flex-1 overflow-auto rounded-xl border border-border p-4">
          <h3 className="text-sm font-semibold mb-3 text-foreground">Detected Outliers</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(outliers).map(([colName, info]) => {
              const raw = (info && typeof info === 'object' ? info : {}) as {
                count?: number | string
                percentage?: number | string
                note?: string
                method?: string
              }
              const countNum = typeof raw.count === 'number' ? raw.count : null
              const pctNum = typeof raw.percentage === 'number' ? raw.percentage : null
              const countLabel =
                countNum !== null
                  ? `${countNum} outliers`
                  : raw.count !== undefined
                    ? String(raw.count)
                    : '0 outliers'
              const pctLabel =
                pctNum !== null
                  ? `${pctNum.toFixed(1)}%`
                  : raw.percentage !== undefined
                    ? String(raw.percentage)
                    : '0%'

              return (
                <div key={colName} className="rounded-xl border border-border bg-card p-4 shadow-xs">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <h4 className="font-semibold text-sm truncate">{colName}</h4>
                    <span className="inline-flex items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
                      {countLabel}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-amber-500"
                        style={{ width: `${Math.min(pctNum ?? 0, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-muted-foreground">{pctLabel}</span>
                  </div>
                  {raw.method && (
                    <p className="text-xs text-muted-foreground">Method: {raw.method}</p>
                  )}
                  {raw.note && <p className="text-xs text-muted-foreground mt-1">{raw.note}</p>}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export function StatisticsContent({ statistics }: { statistics: Statistic[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {statistics.map((stat, i) => (
        <StatCard key={i} label={stat.label} value={stat.value} trend={stat.trend} change={stat.change} />
      ))}
    </div>
  )
}