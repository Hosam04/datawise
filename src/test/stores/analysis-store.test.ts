import { beforeEach, describe, expect, it } from 'vitest'
import { useAnalysisStore } from '../../stores/analysis-store'
import type { CompletedArtifacts } from '../../types/artifacts'

const ARTIFACTS = {
  summary: 's',
  preview: { columns: [], rows: [] },
  charts: [],
  insights: [],
} as unknown as CompletedArtifacts

beforeEach(() => {
  useAnalysisStore.setState({
    sessionId: null,
    fileName: null,
    fileSize: null,
    fileType: null,
    status: 'idle',
    progress: 0,
    error: null,
    artifacts: null,
    isAnalyzing: false,
    lastUpdated: null,
  })
  localStorage.clear()
})

describe('analysis-store initial & lifecycle state', () => {
  it('starts idle with no session', () => {
    const s = useAnalysisStore.getState()
    expect(s.sessionId).toBeNull()
    expect(s.status).toBe('idle')
    expect(s.progress).toBe(0)
    expect(s.error).toBeNull()
    expect(s.artifacts).toBeNull()
    expect(s.isAnalyzing).toBe(false)
  })

  it('startAnalysis sets uploading state', () => {
    useAnalysisStore.getState().startAnalysis({
      sessionId: 'sess-1',
      fileName: 'data.csv',
      fileSize: '10 KB',
      fileType: 'text/csv',
    })
    const s = useAnalysisStore.getState()
    expect(s.sessionId).toBe('sess-1')
    expect(s.fileName).toBe('data.csv')
    expect(s.fileSize).toBe('10 KB')
    expect(s.fileType).toBe('text/csv')
    expect(s.status).toBe('uploading')
    expect(s.progress).toBe(0)
    expect(s.isAnalyzing).toBe(true)
    expect(s.error).toBeNull()
    expect(s.lastUpdated).not.toBeNull()
  })

  it('setProgress clamps to [0, 100]', () => {
    const { setProgress } = useAnalysisStore.getState()
    setProgress(150)
    expect(useAnalysisStore.getState().progress).toBe(100)
    setProgress(-5)
    expect(useAnalysisStore.getState().progress).toBe(0)
    setProgress(42)
    expect(useAnalysisStore.getState().progress).toBe(42)
  })

  it('setStatus controls isAnalyzing and pins progress on completion', () => {
    const { setStatus, setProgress } = useAnalysisStore.getState()
    setProgress(50)
    setStatus('uploading')
    expect(useAnalysisStore.getState().isAnalyzing).toBe(true)

    setStatus('processing')
    expect(useAnalysisStore.getState().isAnalyzing).toBe(true)

    setStatus('completed')
    expect(useAnalysisStore.getState().isAnalyzing).toBe(false)
    expect(useAnalysisStore.getState().progress).toBe(100)

    setStatus('error')
    expect(useAnalysisStore.getState().isAnalyzing).toBe(false)
  })

  it('setArtifacts marks completed with full progress', () => {
    useAnalysisStore.getState().setArtifacts(ARTIFACTS)
    const s = useAnalysisStore.getState()
    expect(s.artifacts).toBe(ARTIFACTS)
    expect(s.status).toBe('completed')
    expect(s.progress).toBe(100)
    expect(s.isAnalyzing).toBe(false)
    expect(s.error).toBeNull()
  })

  it('setError sets error status and stops analyzing', () => {
    useAnalysisStore.getState().setError('boom')
    const s = useAnalysisStore.getState()
    expect(s.error).toBe('boom')
    expect(s.status).toBe('error')
    expect(s.isAnalyzing).toBe(false)
  })

  it('clearError clears the error but keeps status', () => {
    useAnalysisStore.getState().setError('boom')
    useAnalysisStore.getState().setStatus('processing')
    useAnalysisStore.getState().clearError()
    expect(useAnalysisStore.getState().error).toBeNull()
    expect(useAnalysisStore.getState().status).toBe('processing')
  })

  it('setSession updates the session and optionally the filename', () => {
    const { setSession } = useAnalysisStore.getState()
    setSession('sess-2')
    expect(useAnalysisStore.getState().sessionId).toBe('sess-2')
    expect(useAnalysisStore.getState().fileName).toBeNull()

    setSession('sess-3', 'other.csv')
    expect(useAnalysisStore.getState().sessionId).toBe('sess-3')
    expect(useAnalysisStore.getState().fileName).toBe('other.csv')

    setSession('sess-4')
    expect(useAnalysisStore.getState().fileName).toBe('other.csv')
  })

  it('resetAnalysis returns to the initial state', () => {
    useAnalysisStore.getState().startAnalysis({
      sessionId: 'sess-1',
      fileName: 'data.csv',
    })
    useAnalysisStore.getState().setError('boom')
    useAnalysisStore.getState().resetAnalysis()
    const s = useAnalysisStore.getState()
    expect(s.sessionId).toBeNull()
    expect(s.fileName).toBeNull()
    expect(s.status).toBe('idle')
    expect(s.progress).toBe(0)
    expect(s.error).toBeNull()
    expect(s.artifacts).toBeNull()
    expect(s.isAnalyzing).toBe(false)
    expect(s.lastUpdated).not.toBeNull()
  })
})

describe('analysis-store persistence (quota safety)', () => {
  it('never persists artifacts', () => {
    useAnalysisStore.getState().startAnalysis({
      sessionId: 'sess-1',
      fileName: 'data.csv',
    })
    useAnalysisStore.getState().setArtifacts(ARTIFACTS)

    const persisted = JSON.parse(
      localStorage.getItem('datawise-analysis') ?? '{}',
    )
    expect(persisted.state).not.toHaveProperty('artifacts')
    expect(persisted.state.status).toBe('completed')
    expect(persisted.state.progress).toBe(100)
    expect(persisted.state.sessionId).toBe('sess-1')
  })

  it('resets mid-flight statuses to idle on persist', () => {
    useAnalysisStore.getState().startAnalysis({
      sessionId: 'sess-1',
      fileName: 'data.csv',
    })
    useAnalysisStore.getState().setStatus('processing')

    const persisted = JSON.parse(
      localStorage.getItem('datawise-analysis') ?? '{}',
    )
    expect(persisted.state.status).toBe('idle')
    expect(persisted.state.progress).toBe(0)
    expect(persisted.state.sessionId).toBe('sess-1')
  })
})