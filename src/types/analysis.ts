import type { ArtifactStatus, CompletedArtifacts, StructuredInsights } from './artifacts'

export type AnalysisJobStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'failed' | 'error'

export interface AnalysisSessionMeta {
  sessionId: string
  fileName: string
  fileSize?: string
  fileType?: string
  uploadedAt: string
}

export interface AnalysisState {
  sessionId: string | null
  fileName: string | null
  fileSize?: string | null
  fileType?: string | null
  status: AnalysisJobStatus
  progress: number
  error: string | null
  artifacts: CompletedArtifacts | null
  isAnalyzing: boolean
  lastUpdated: string | null
}

export interface AnalysisStatusResponse {
  status: ArtifactStatus
  error?: string
  session_id?: string
  insights?: StructuredInsights
}

export interface AnalyzeDataResponse {
  status: string
  session_id: string
  check_status?: string
}
