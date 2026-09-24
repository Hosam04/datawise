'use client'

import { TrendingUp, AlertTriangle, Sparkles, Zap, Layers, CheckCircle2, ShieldAlert, Info, AlertCircle, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StructuredInsights } from '@/types/artifacts'
import { FormattedMarkdown } from './markdown'
import type { Insight } from './types'

const insightToneStyles = {
  positive: {
    icon: TrendingUp,
    className: 'border-emerald-500/20 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300',
  },
  warning: {
    icon: AlertTriangle,
    className: 'border-amber-500/20 bg-amber-500/5 text-amber-700 dark:text-amber-300',
  },
  neutral: {
    icon: Sparkles,
    className: 'border-border bg-muted/40 text-foreground',
  },
} as const

export function InsightsContent({ insights }: { insights: Insight[] }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      {insights.map((insight) => {
        const tone = insightToneStyles[insight.tone]
        const Icon = tone.icon

        return (
          <div
            key={insight.id}
            className={cn('flex items-start gap-3 rounded-lg border p-4', tone.className)}
          >
            <div className="mt-0.5 shrink-0">
              <Icon className="size-5" />
            </div>
            <div className="flex flex-col gap-1">
              <p className="font-semibold text-sm">{insight.title}</p>
              <p className="text-sm opacity-90">{insight.description}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function formatEvidenceValue(key: string, value: unknown) {
  if (value === null || value === undefined) {
    return '-'
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  if (typeof value === 'number') {
    if (key === 'difference_percent') {
      return `${value.toFixed(1)}%`
    }

    if (key === 'p_value') {
      return value.toFixed(4)
    }

    if (key === 'highest_group' || key === 'lowest_group') {
      return Number.isInteger(value) ? value.toString() : value.toFixed(0)
    }

    return value.toFixed(2)
  }

  return String(value)
}

function formatEvidenceKey(key: string) {
  const labels: Record<string, string> = {
    group_column: 'Feature',
    highest_group: 'Higher group',
    highest_value: 'Average target',
    highest_count: 'Sample size',
    lowest_group: 'Compared group',
    lowest_value: 'Compared average',
    lowest_count: 'Compared sample size',
    difference_percent: 'Difference',
    p_value: 'P-value',
    statistically_significant: 'Statistically significant',
    strength: 'Strength',
    f_statistic: 'F-statistic',
    confidence: 'Confidence',
  }

  return labels[key] ?? key
}

export function InsightsReportContent({
  insights,
}: {
  insights?: StructuredInsights | null
}) {
  const safeInsights = insights ?? {
    executive_summary: '',
    key_findings: [],
    recommendations: [],
    limitations: [],
    significant_segments: [],
    data_quality: {
      score: null,
      issues: [],
    },
  }

  const key_findings = Array.isArray(safeInsights.key_findings) ? safeInsights.key_findings : []
  const recommendations = Array.isArray(safeInsights.recommendations) ? safeInsights.recommendations : []
  const limitations = Array.isArray(safeInsights.limitations) ? safeInsights.limitations : []
  const significant_segments = Array.isArray(safeInsights.significant_segments) ? safeInsights.significant_segments : []
  const data_quality_issues = Array.isArray(safeInsights.data_quality?.issues) ? safeInsights.data_quality.issues : []

  const hasContent =
    Boolean(safeInsights.executive_summary) ||
    key_findings.length > 0 ||
    recommendations.length > 0 ||
    limitations.length > 0 ||
    significant_segments.length > 0 ||
    data_quality_issues.length > 0

  if (!hasContent) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 py-12">
        <div className="flex size-16 items-center justify-center rounded-full bg-muted">
          <Sparkles className="size-8 text-muted-foreground/40" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium">Waiting for insights...</p>
          <p className="text-xs text-muted-foreground mt-1">
            The analysis engine is processing dataset evidence.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-8 overflow-y-auto overscroll-contain pr-2 pb-4">
      {/* Executive Summary */}
      <section className="relative shrink-0 overflow-visible rounded-xl border border-border bg-leanier-to-br from-card via-card to-muted/30 p-6 shadow-sm">
        <div className="pointer-events-none absolute -right-4 -top-4 opacity-[0.03]" aria-hidden="true">
          <FileText className="size-32" />
        </div>
        <div className="relative min-w-0">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <FileText className="size-4 text-primary" />
            </div>
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Executive Summary
            </h2>
          </div>
          <div className="min-w-0 max-w-none wrap-break-word text-sm leading-7 text-muted-foreground">
            <FormattedMarkdown
              content={
                typeof safeInsights.executive_summary === 'string'
                  ? safeInsights.executive_summary.trim() ||
                    'Analysis completed. See detailed findings below.'
                  : safeInsights.executive_summary
                    ? JSON.stringify(safeInsights.executive_summary)
                    : 'Analysis completed. See detailed findings below.'
              }
            />
          </div>
        </div>
      </section>

      {/* Key Findings */}
      {key_findings.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-amber-500/10">
              <Zap className="size-4 text-amber-600 dark:text-amber-400" />
            </div>
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Key Findings
            </h2>
            <span className="ml-auto text-xs text-muted-foreground">
              {key_findings.length} finding
              {key_findings.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {key_findings.map((finding, i) => (
              <div
                key={i}
                className="group relative rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:border-primary/20 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3 mb-2.5">
                  <h3 className="font-semibold text-sm leading-tight group-hover:text-primary transition-colors">
                    {finding.title}
                  </h3>
                  {finding.confidence && (
                    <span
                      className={cn(
                        'shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
                        finding.confidence === 'high' &&
                          'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
                        finding.confidence === 'medium' &&
                          'bg-amber-500/10 text-amber-700 dark:text-amber-400',
                        finding.confidence === 'low' &&
                          'bg-red-500/10 text-red-700 dark:text-red-400',
                      )}
                    >
                      {finding.confidence}
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                  {typeof finding.description === 'string'
                    ? finding.description
                    : Object.entries(finding.description || {})
                        .map(([key, value]) => `${key}: ${value}`)
                        .join(' • ')}
                </p>

                {/* Evidence */}
                {finding.evidence && typeof finding.evidence === 'object' && (
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    {Object.entries(finding.evidence)
                      .filter(([key]) => !['_rank_score', 'f_statistic'].includes(key))
                      .map(([key, value]) => (
                        <div key={key} className="rounded-lg bg-muted/50 px-3 py-2">
                          <p className="text-[11px] uppercase text-muted-foreground">
                            {formatEvidenceKey(key)}
                          </p>
                          {key === 'strength' ? (
                            <span className="inline-flex rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-600">
                              {String(value)}
                            </span>
                          ) : (
                            <span className="text-xs font-medium text-foreground">
                              {formatEvidenceValue(key, value)}
                            </span>
                          )}
                        </div>
                      ))}
                  </div>
                )}

                {/* Statistical metrics */}
                {finding.metrics && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {Object.entries(finding.metrics).map(([key, value]) => (
                      <span
                        key={key}
                        className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-foreground"
                      >
                        <span className="text-muted-foreground mr-1">
                          {key}:
                        </span>
                        {String(value)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Significant Segments */}
      {significant_segments.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-violet-500/10">
              <Layers className="size-4 text-violet-600 dark:text-violet-400" />
            </div>
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Significant Segments
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {significant_segments.map((segment, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-5 shadow-sm">
                <h3 className="font-semibold text-sm mb-2">{segment.name}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                  {segment.description}
                </p>
                {segment.metrics &&
                  Object.keys(segment.metrics).length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(segment.metrics).map(([key, value]) => (
                        <span
                          key={key}
                          className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-xs font-medium text-foreground"
                        >
                          <span className="text-muted-foreground mr-1">
                            {key}:
                          </span>
                          {value}
                        </span>
                      ))}
                    </div>
                  )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10">
              <TrendingUp className="size-4 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Recommendations
            </h2>
          </div>
          <div className="flex flex-col gap-3">
            {recommendations.map((rec, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-xl border border-emerald-500/15 bg-emerald-500/3 p-4 transition-colors hover:bg-emerald-500/5"
              >
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                <p className="text-sm leading-relaxed text-foreground">{rec}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Data Quality */}
      {data_quality_issues.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-amber-500/10">
              <ShieldAlert className="size-4 text-amber-600 dark:text-amber-400" />
            </div>
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Data Quality
            </h2>
            {safeInsights.data_quality?.score != null && (
              <div className="ml-auto flex items-center gap-1.5">
                <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-amber-500"
                    style={{ width: `${safeInsights.data_quality.score}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-muted-foreground">
                  {safeInsights.data_quality.score}/100
                </span>
              </div>
            )}
          </div>
          <div className="rounded-xl border border-amber-500/15 bg-amber-500/3 p-5">
            <div className="flex flex-col gap-3">
              {data_quality_issues.map((issue, i) => (
                <div key={i} className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  <p className="text-sm leading-relaxed text-foreground">
                    {issue}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Limitations */}
      {limitations.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-slate-500/10">
              <Info className="size-4 text-slate-600 dark:text-slate-400" />
            </div>
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Limitations
            </h2>
          </div>
          <div className="flex flex-col gap-3">
            {limitations.map((lim, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-xl border border-border bg-muted/30 p-4"
              >
                <AlertCircle className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {lim}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}