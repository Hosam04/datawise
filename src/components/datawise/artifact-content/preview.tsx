'use client'

import { Table, Activity, FileText } from 'lucide-react'
import type { PreviewMeta } from './types'

export function PreviewContent({
  columns,
  rows,
  meta,
}: {
  columns: string[]
  rows: Record<string, unknown>[]
  meta: PreviewMeta
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
      <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <Table className="size-4" />
          <span>{meta.rows.toLocaleString()} rows</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Activity className="size-4" />
          <span>{meta.columns} columns</span>
        </div>
        <div className="flex items-center gap-1.5">
          <FileText className="size-4" />
          <span>{meta.fileSize}</span>
        </div>
        <span className="text-xs">Updated {meta.lastUpdated}</span>
      </div>

      <div className="flex-1 overflow-auto rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-muted">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="whitespace-nowrap px-4 py-2 font-medium text-muted-foreground"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className="border-b border-border last:border-0 hover:bg-muted/50"
              >
                {columns.map((column) => (
                  <td
                    key={column}
                    className="max-w-xs truncate px-4 py-2 text-foreground"
                  >
                    {String(row[column] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}