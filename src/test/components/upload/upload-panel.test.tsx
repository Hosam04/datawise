import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { UploadPanel } from '../../../components/upload/upload-panel'
import { useDatasetStore } from '../../../stores/dataset-store'
import { useAnalysisStore } from '../../../stores/analysis-store'
import { useReportStore } from '../../../stores/report-store'
import { useWorkspaceStore } from '../../../stores/workspace-store'
import { useNotificationStore } from '../../../stores/notification-store'
import type { CompletedArtifacts } from '../../../types/artifacts'

vi.mock('@/lib/api', () => ({
  analyzeData: vi.fn(),
  getAnalysisStatus: vi.fn(),
  getDatasetArtifacts: vi.fn(),
  fetchMyReports: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/upload',
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    message: vi.fn(),
    dismiss: vi.fn(),
  },
}))

import { analyzeData, getAnalysisStatus, getDatasetArtifacts, fetchMyReports } from '../../../lib/api'
import { toast } from 'sonner'

const mocked = {
  analyzeData: vi.mocked(analyzeData),
  getAnalysisStatus: vi.mocked(getAnalysisStatus),
  getDatasetArtifacts: vi.mocked(getDatasetArtifacts),
  fetchMyReports: vi.mocked(fetchMyReports),
  toastError: vi.mocked(toast.error),
}

const FILE = new File(['a,b,c'], 'data.csv', { type: 'text/csv' })

const completedArtifacts: CompletedArtifacts = {
  status: 'completed',
  preview: {
    columns: ['a', 'b'],
    rows: [{ a: 1, b: 2 }],
    total_rows: 1,
    total_cols: 2,
  },
  statistics: {},
  insights: {
    executive_summary: 'ok',
    key_findings: [],
    significant_segments: [],
    recommendations: [],
    limitations: [],
  },
  charts: [],
  report: { url: '/report' },
}

function resetStores() {
  useDatasetStore.getState().addDataset
  useDatasetStore.setState({ datasets: [] })
  useAnalysisStore.getState().resetAnalysis()
  useReportStore.setState({ reports: [] })
  useWorkspaceStore.setState({ openDatasetIds: [], activeDatasetId: null })
  useNotificationStore.setState({ items: [], seenIds: [], dismissedIds: [] })
}

async function selectFile() {
  const { container } = render(<UploadPanel />)
  const input = container.querySelector('input[type="file"]')!
  await act(async () => {
    fireEvent.change(input, { target: { files: [FILE] } })
  })
  return container
}

describe('UploadPanel', () => {
  beforeEach(() => {
    mocked.analyzeData.mockReset()
    mocked.getAnalysisStatus.mockReset()
    mocked.getDatasetArtifacts.mockReset()
    mocked.fetchMyReports.mockReset()
    mocked.fetchMyReports.mockResolvedValue([])
    mocked.toastError.mockClear()

    mocked.analyzeData.mockImplementation(async (_file, _query, onProgress) => {
      onProgress?.(40)
      return {
        session_id: 'sess-1',
        status: 'processing',
      } as any
    })
    vi.useFakeTimers()
    resetStores()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    resetStores()
    document.body.innerHTML = ''
  })

  it('selects a file and reveals the Upload button card', async () => {
    await selectFile()
    expect(screen.getByText('data.csv')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Start Analysis' }),
    ).toBeInTheDocument()
  })

  it('runs the full happy-path: upload, poll, artifacts, stores, and UI', async () => {
    mocked.getAnalysisStatus
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValue({ status: 'completed' })
    mocked.getDatasetArtifacts.mockResolvedValue(completedArtifacts)
    mocked.fetchMyReports.mockResolvedValue([
      {
        id: 'rep-1',
        title: 'data.csv Analysis Report',
        dataset: 'data.csv',
        dataset_id: 'sess-1',
        type: 'AI Analysis',
        created_at: '2025-01-01T00:00:00Z',
      },
    ])

    await selectFile()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start Analysis' }))
    })
    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(mocked.analyzeData).toHaveBeenCalledWith(
      FILE,
      'Analyze this dataset',
      expect.any(Function),
    )
    expect(mocked.getAnalysisStatus).toHaveBeenCalledWith('sess-1')
    expect(mocked.getDatasetArtifacts).toHaveBeenCalledWith('sess-1')

    // Stores
    const dataset = useDatasetStore
      .getState()
      .datasets.find((d) => d.id === 'sess-1')!
    expect(dataset).toMatchObject({
      name: 'data.csv',
      size: '0.00 MB',
      status: 'Analyzed',
    })
    expect(dataset.artifacts).toEqual(completedArtifacts)

    const analysis = useAnalysisStore.getState()
    expect(analysis.sessionId).toBe('sess-1')
    expect(analysis.status).toBe('completed')
    expect(analysis.progress).toBe(100)
    expect(analysis.artifacts).toEqual(completedArtifacts)
    expect(analysis.isAnalyzing).toBe(false)

    const notifications = useNotificationStore.getState().items
    expect(notifications).toHaveLength(2)
    expect(notifications[0]).toMatchObject({
      action: 'Analysis completed',
      href: '/chat?dataset=sess-1',
    })
    expect(notifications[1]).toMatchObject({
      action: 'Dataset uploaded',
      href: '/datasets/sess-1',
    })

    expect(useReportStore.getState().reports).toHaveLength(1)
    expect(useReportStore.getState().reports[0]).toMatchObject({
      title: 'data.csv Analysis Report',
      type: 'AI Analysis',
    })

    expect(useWorkspaceStore.getState().activeDatasetId).toBe('sess-1')

    // UI
    expect(screen.getByText('Analysis Complete')).toBeInTheDocument()
    expect(screen.getByText('data.csv is ready.')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Start Analysis' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Remove file' }),
    ).not.toBeInTheDocument()
  })

  it('drives the upload progress into the analysis store', async () => {
    mocked.getAnalysisStatus.mockResolvedValue({ status: 'completed' })
    mocked.getDatasetArtifacts.mockResolvedValue(completedArtifacts)

    await selectFile()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start Analysis' }))
    })
    await act(async () => {
      await vi.runAllTimersAsync()
    })

    // The uploader shortens progress (~0.00 MB) and completes at 100%.
    expect(useAnalysisStore.getState().progress).toBe(100)
    expect(useAnalysisStore.getState().status).toBe('completed')
    expect(screen.getByText('Analysis Complete')).toBeInTheDocument()
  })

  it('handles a failed analysis: error message, toast, dataset stays Processing', async () => {
    mocked.getAnalysisStatus.mockResolvedValueOnce({
      status: 'failed',
      error: 'model exploded',
    })
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await selectFile()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start Analysis' }))
    })
    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(screen.getByText('Analysis Failed')).toBeInTheDocument()
    expect(screen.getByText('model exploded')).toBeInTheDocument()
    expect(mocked.toastError).toHaveBeenCalledWith('Analysis failed', {
      description: 'model exploded',
    })

    const analysis = useAnalysisStore.getState()
    expect(analysis.status).toBe('error')
    expect(analysis.error).toBe('model exploded')

    const dataset = useDatasetStore
      .getState()
      .datasets.find((d) => d.id === 'sess-1')!
    expect(dataset.status).toBe('Processing')

    expect(useReportStore.getState().reports).toHaveLength(0)
  })

  it('handles a network error during upload', async () => {
    mocked.analyzeData.mockRejectedValue(new Error('Network error. Is the backend running?'))
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await selectFile()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start Analysis' }))
    })
    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(screen.getByText('Analysis Failed')).toBeInTheDocument()
    expect(
      screen.getByText('Network error. Is the backend running?'),
    ).toBeInTheDocument()

    expect(useAnalysisStore.getState().error).toBe(
      'Network error. Is the backend running?',
    )
    expect(useDatasetStore.getState().datasets).toHaveLength(0)
  })

  it('complains when analysis completed without artifacts', async () => {
    mocked.getAnalysisStatus.mockResolvedValue({ status: 'completed' })
    mocked.getDatasetArtifacts.mockResolvedValue({
      status: 'processing',
      error: 'late',
    })
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await selectFile()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start Analysis' }))
    })
    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(
      screen.getByText('Analysis completed without artifacts'),
    ).toBeInTheDocument()
  })
})