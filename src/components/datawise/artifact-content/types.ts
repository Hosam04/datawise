export interface Insight {
  id: string
  title: string
  description: string
  tone: 'positive' | 'warning' | 'neutral'
}

export interface Statistic {
  label: string
  value: string
  trend?: 'neutral' | 'up' | 'down'
  change?: string
}

export interface PreviewMeta {
  rows: number
  columns: number
  fileSize: string
  lastUpdated: string
}

export interface Report {
  title: string
  generatedAt: string
  summary: string
  highlights: string[]
  recommendations: string[]
}