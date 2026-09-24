// ─── Artifact Status Types ───

export type ArtifactStatus = 'processing' | 'completed' | 'failed'

// ─── Preview & Stats ───

export interface DatasetPreview {
  columns: string[]
  rows: Record<string, unknown>[]
  total_rows: number
  total_cols: number
}

export interface ColumnStatistics {
  count?: number | null
  null_count?: number | null
  null_pct?: number | null
  min?: number | string | null
  max?: number | string | null
  mean?: number | string | null
  median?: number | string | null
  std?: number | string | null
  variance?: number | string | null
  skewness?: number | string | null
  kurtosis?: number | string | null
  range?: number | string | null
  iqr?: number | string | null
  percentiles?: Record<string, number | null>
  note?: string
  [key: string]: unknown
}

export interface StatisticsArtifact {
  descriptive?: Record<string, ColumnStatistics | Record<string, number | string | null | undefined> | null | undefined>
  correlations?: Record<string, Record<string, number | null> | string | unknown> | unknown
  outliers?: Record<string, { count?: number; percentage?: number; note?: string } | unknown> | unknown
}

// ─── Charts ───

export interface ChartArtifact {
  id: number
  url: string
  // Some backend versions attach the full chart payload to the rendered
  // artifact as well. When present, the UI promotes it to an interactive
  // chart instead of rendering the PNG.
  type?: ChartType
  title?: string
  xAxisLabel?: string
  yAxisLabel?: string
  labels?: Array<string | number>
  datasets?: ChartDataSet[]
  options?: ChartOptions
}

export type ChartType =
  | 'bar'
  | 'line'
  | 'scatter'
  | 'pie'
  | 'histogram'
  | 'boxplot'
  | 'box_plot'
  | 'heatmap'
  | 'heat_map'
  | 'confusion_matrix'
  | 'box'

export interface ChartDataSet {
  label: string
  data: Array<number | number[]>
  backgroundColor?: string
  borderColor?: string
  fill?: string | boolean
  pointBackgroundColor?: string
  pointBorderColor?: string
}

export interface ChartOptions {
  [key: string]: unknown
  xAxis?: string
  yAxis?: string
  xAxisLabel?: string
  yAxisLabel?: string
  yLabels?: Array<string | number>
  matrix?: number[][]
  z?: number[][]
  heatmap?: {
    x?: Array<string | number>
    y?: Array<string | number>
    z?: number[][]
  }
  heat_map?: {
    x?: Array<string | number>
    y?: Array<string | number>
    z?: number[][]
  }
  x?: Array<string | number>
  y?: Array<string | number>
  values?: number[][]
  confusion_matrix?: {
    labels?: Array<string | number>
    matrix?: number[][]
  }
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
}

export interface ChartDataItem {
  id: number
  type: ChartType
  title: string
  xAxisLabel?: string
  yAxisLabel?: string
  labels: Array<string | number>
  datasets: ChartDataSet[]
  options?: ChartOptions
}

// ─── Report ───

export interface ReportArtifact {
  url: string
}

// ─── Structured Insights Types ───

export interface InsightFinding {
  title: string
  description: string
  evidence?: string | Record<string, unknown>
  confidence?: 'high' | 'medium' | 'low'
  metrics?: Record<string, string | number>
}

export interface InsightSegment {
  name: string
  description: string
  metrics?: Record<string, string>
}

export interface DataQualityInfo {
  issues: string[]
  score?: number | null
}

export interface StructuredInsights {
  executive_summary: string
  key_findings: InsightFinding[]
  significant_segments: InsightSegment[]
  recommendations: string[]
  limitations: string[]
  data_quality?: DataQualityInfo | null
}

export type Insights = StructuredInsights

// ─── Artifact Contracts ───

export interface CompletedArtifacts {
  status: 'completed'
  preview: DatasetPreview
  statistics: StatisticsArtifact
  insights: StructuredInsights          
  charts: ChartArtifact[]
  chartData?: ChartDataItem[]
  report: ReportArtifact
}

export interface PendingArtifacts {
  status: Exclude<ArtifactStatus, 'completed'>
  error?: string
}

export type DatasetArtifacts = CompletedArtifacts | PendingArtifacts

// ─── Analysis Status (Updated) ───

export interface AnalysisStatus {
  status: ArtifactStatus
  error?: string
  insights?: StructuredInsights
  charts?: ChartArtifact[] | ChartDataItem[]
  report?: ReportArtifact | Record<string, unknown>
}
