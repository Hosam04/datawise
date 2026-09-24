'use client'

import { TrendingUp } from 'lucide-react'
import type { Report } from './types'

export function ReportContent({ report }: { report: Report }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto pr-2">
      <div>
        <h2 className="text-xl font-bold">{report.title}</h2>
        <p className="text-sm text-muted-foreground">
          Generated at {report.generatedAt}
        </p>
      </div>

      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <h3 className="mb-2 font-semibold text-sm">Summary</h3>
        <p className="text-sm leading-relaxed text-foreground">
          {report.summary}
        </p>
      </div>

      <div>
        <h3 className="mb-3 font-semibold text-sm">Key Highlights</h3>
        <ul className="flex flex-col gap-2">
          {report.highlights.map((h, i) => (
            <li
              key={i}
              className="flex items-start gap-2 rounded-md border border-border bg-card p-3 text-sm"
            >
              <span className="mt-0.5 size-1.5 shrink-0 rounded-full bg-primary" />
              {h}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="mb-3 font-semibold text-sm">Recommendations</h3>
        <ul className="flex flex-col gap-2">
          {report.recommendations.map((r, i) => (
            <li
              key={i}
              className="flex items-start gap-2 rounded-md border border-emerald-500/20 bg-emerald-500/5 p-3 text-sm text-emerald-700 dark:text-emerald-300"
            >
              <TrendingUp className="mt-0.5 size-4 shrink-0" />
              {r}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}