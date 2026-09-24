import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as React from 'react'
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from '@testing-library/react'
import { ArtifactPanel } from '../../../components/datawise/artifact-panel'
import { useDatasetStore } from '../../../stores/dataset-store'
import { useWorkspaceStore } from '../../../stores/workspace-store'
import {
  ArtifactEmptyState,
  DatasetStatisticsView,
  InsightsContent,
  InsightsReportContent,
  PreviewContent,
} from '../../../components/datawise/artifact-content'
import { ChartsDashboard } from '../../../components/datawise/charts-dashboard'
import { getDatasetArtifacts, fetchFile, saveDownloadedFile } from '../../../lib/api'
import type { ChartDataItem, CompletedArtifacts } from '../../../types/artifacts'

const params = { get: vi.fn<() => string | null>(() => 'd1') }

vi.mock('next/navigation', () => ({
  useSearchParams: () => params,
}))

vi.mock('@/lib/api', () => ({
  getDatasetArtifacts: vi.fn(),
  assetUrl: (url: string) => url,
  fetchFile: vi.fn(),
  saveDownloadedFile: vi.fn(),
}))

vi.mock('@/components/datawise/artifact-content', () => {
  return {
    ArtifactEmptyState: vi.fn(() =>
      React.createElement('div', { 'data-testid': 'artifact-empty' }),
    ),
    PreviewContent: vi.fn(({ columnCount }: { columnCount?: number }) =>
      React.createElement('div', {
        'data-testid': 'preview-content',
        'data-columns': columnCount ?? '',
      }),
    ),
    InsightsContent: vi.fn(() =>
      React.createElement('div', { 'data-testid': 'insights-content' }),
    ),
    InsightsReportContent: vi.fn(() =>
      React.createElement('div', { 'data-testid': 'insights-report-content' }),
    ),
    DatasetStatisticsView: vi.fn(() =>
      React.createElement('div', { 'data-testid': 'statistics-view' }),
    ),
  }
})

vi.mock('@/components/datawise/charts-dashboard', () => {
  return {
    ChartsDashboard: vi.fn(() =>
      React.createElement('div', { 'data-testid': 'charts-dash' }),
    ),
  }
})

const mockedGetArtifacts = vi.mocked(getDatasetArtifacts)
const mockedChartsDashboard = vi.mocked(ChartsDashboard)
const mockedPreview = vi.mocked(PreviewContent)
const mockedInsights = vi.mocked(InsightsContent)
const mockedInsightsReport = vi.mocked(InsightsReportContent)
const mockedStatistics = vi.mocked(DatasetStatisticsView)
const mockedEmpty = vi.mocked(ArtifactEmptyState)
const mockedFetchFile = vi.mocked(fetchFile)

const imageCharts = [
  { id: 1, url: '/c/1.png', type: 'bar', title: 'A', labels: ['x'], datasets: [{ label: 's', data: [1] }] },
  { id: 2, url: '/c/2.png', type: 'line', title: 'B', labels: ['x'], datasets: [{ label: 's', data: [1] }] },
]

const completed: CompletedArtifacts = {
  status: 'completed',
  preview: {
    columns: ['age', 'city'],
    rows: [{ age: 30, city: 'NYC' }],
    total_rows: 42,
    total_cols: 2,
  },
  chartData: [
    { id: 5, type: 'bar', title: 'From api', labels: ['x'], datasets: [{ label: 's', data: [1] }] },
    ...imageCharts,
  ] as ChartDataItem[],
  charts: [],
  insights: {
    executive_summary: 'Revenue up',
    key_findings: [],
    significant_segments: [],
    recommendations: [],
    limitations: [],
  },
  statistics: {} as CompletedArtifacts['statistics'],
  report: { url: '/report/d1.pdf' },
}

const datasetWithoutArtifacts = {
  id: 'd1',
  name: 'sales.csv',
  size: '1 KB',
  type: 'CSV',
  status: 'Analyzed',
}

function resetStores() {
  useDatasetStore.setState({ datasets: [] })
  useWorkspaceStore.setState({ openDatasetIds: [], activeDatasetId: null })
}

describe('ArtifactPanel', () => {
  beforeEach(() => {
    params.get.mockReset()
    params.get.mockReturnValue('d1')
    mockedGetArtifacts.mockReset()
    mockedChartsDashboard.mockClear()
    mockedPreview.mockClear()
    mockedInsights.mockClear()
    mockedInsightsReport.mockClear()
    mockedStatistics.mockClear()
    mockedEmpty.mockClear()
    resetStores()
  })

  it('shows the empty state when no dataset is selected', () => {
    params.get.mockReturnValue(null)
    render(<ArtifactPanel />)
    expect(screen.getByRole('region', { name: 'Artifact panel' })).toBeInTheDocument()
    expect(screen.getByTestId('artifact-empty')).toBeInTheDocument()
    expect(mockedGetArtifacts).not.toHaveBeenCalled()
  })

  it('starts with an existing in-store analysis and never refetches', () => {
    useDatasetStore.setState({
      datasets: [
        { ...datasetWithoutArtifacts, artifacts: completed },
      ],
    })
    render(<ArtifactPanel />)
    expect(screen.getByTestId('preview-content')).toBeInTheDocument()
    expect(mockedGetArtifacts).not.toHaveBeenCalled()
  })

  it('fetches artifacts when the store lacks them and persists them back', async () => {
    useDatasetStore.setState({ datasets: [datasetWithoutArtifacts] })
    mockedGetArtifacts.mockResolvedValue(completed)

    render(<ArtifactPanel />)
    expect(screen.getByText('Analysis in progress…')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByTestId('preview-content')).toBeInTheDocument()
    })
    expect(mockedGetArtifacts).toHaveBeenCalledWith('d1')
    expect(useDatasetStore.getState().datasets[0].artifacts).toBe(completed)
    expect(mockedPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        // Normalized to string column names (PreviewContent expects string[])
        columns: expect.arrayContaining(['age', 'city']),
        meta: expect.objectContaining({
          rows: 42,
          columns: 2,
        }),
      }),
      undefined,
    )
  })

  it('re-polls every 2s while the analysis is processing', async () => {
    vi.useFakeTimers()
    try {
      useDatasetStore.setState({ datasets: [datasetWithoutArtifacts] })
      mockedGetArtifacts
        .mockResolvedValueOnce({ status: 'processing' } as unknown as CompletedArtifacts)
        .mockResolvedValueOnce({
          status: 'completed',
          preview: completed.preview,
          chartData: [],
          charts: [],
          insights: completed.insights,
          statistics: {} as CompletedArtifacts['statistics'],
          report: completed.report,
        } as CompletedArtifacts)

      render(<ArtifactPanel />)
      expect(mockedGetArtifacts).toHaveBeenCalledTimes(1)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000)
      })
      expect(mockedGetArtifacts).toHaveBeenCalledTimes(2)
      await act(async () => {
        await vi.runAllTimersAsync()
      })
      expect(screen.getByTestId('preview-content')).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('shows the error returned for a failed analysis', async () => {
    useDatasetStore.setState({ datasets: [datasetWithoutArtifacts] })
    mockedGetArtifacts.mockResolvedValue({
      status: 'failed',
      error: 'Cleaning crashed',
    } as unknown as CompletedArtifacts)

    render(<ArtifactPanel />)
    await waitFor(() => {
      expect(screen.getByText('Cleaning crashed')).toBeInTheDocument()
    })
  })

  it('surfaces an error when the fetch itself rejects', async () => {
    useDatasetStore.setState({ datasets: [datasetWithoutArtifacts] })
    mockedGetArtifacts.mockRejectedValue(new Error('network down'))

    render(<ArtifactPanel />)
    await waitFor(() => {
      expect(screen.getByText('network down')).toBeInTheDocument()
    })
  })

  it('promotes static charts with interactive payloads and dedupes by id', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [{ id: 5, type: 'bar', title: 'From api', labels: ['x'], datasets: [{ label: 's', data: [1] }] }],
            charts: [
              { id: 5, url: '/img/dup.png' },
              { id: 2, url: '/img/promoted.png', type: 'bar', title: 'Promoted', labels: ['a', 'b'], datasets: [{ label: 'z', data: [1, 2] }] },
              { id: 7, url: '/img/matrix.png' },
            ],
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Charts' }))
    expect(screen.getByTestId('charts-dash')).toBeInTheDocument()

    const call = mockedChartsDashboard.mock.calls[0][0] as any
    const chartData = call.chartData ?? []
    // Interactive charts are deduped by id and sorted; static charts without
    // a full interactive payload are not passed as extraImages (ChartsDashboard
    // only accepts chartData).
    expect(chartData.map((c: ChartDataItem) => c.id)).toEqual([2, 5])
    expect(chartData[0].title).toBe('Promoted')
    expect(call.extraImages).toBeUndefined()
  })

  it('falls back to static images when no chart carries interactive data', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [],
            charts: [
              { id: 1, url: '/img/matrix.png' },
              { id: 2, url: '/img/props.png' },
            ],
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Charts' }))
    expect(screen.getAllByText('Chart 1').length).toBe(1)
    expect(screen.getByAltText('Generated chart 1')).toBeInTheDocument()
  })

  it('shows an error state when a static chart image fails to load', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [],
            charts: [{ id: 1, url: '/img/broken.png' }],
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Charts' }))
    const img = screen.getByAltText('Generated chart 1')
    fireEvent.error(img)
    expect(screen.getByText('Unable to load chart 1.')).toBeInTheDocument()
  })

  it('allows expanding a static fallback chart into a fullscreen dialog', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [],
            charts: [{ id: 1, url: '/img/matrix.png' }],
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Charts' }))
    fireEvent.click(screen.getByRole('button', { name: 'Expand Chart 1 fullscreen' }))
    expect(
      screen.getByRole('dialog', { name: 'Chart 1 (Fullscreen)' }),
    ).toBeInTheDocument()
  })

  it('renders the Insights tab from a list of descriptions', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [],
            charts: [],
            insights: ['Strong growth', 'Seasonality'],
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Insights' }))
    expect(screen.getByTestId('insights-content')).toBeInTheDocument()
    expect(mockedInsights).toHaveBeenCalledWith(
      expect.objectContaining({
        insights: expect.arrayContaining([
          expect.objectContaining({
            id: '0',
            title: 'Insight 1',
            description: 'Strong growth',
            tone: 'positive',
          }),
          expect.objectContaining({
            id: '1',
            title: 'Insight 2',
            description: 'Seasonality',
            tone: 'neutral',
          }),
        ]),
      }),
      undefined,
    )
  })

  it('renders the report-style Insights tab for structured insights', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [],
            charts: [],
            insights: { summary: 'Revenue up', sections: [] },
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Insights' }))
    expect(screen.getByTestId('insights-report-content')).toBeInTheDocument()
    expect(mockedInsightsReport).toHaveBeenCalledWith(
      expect.objectContaining({ insights: expect.any(Object) }),
      undefined,
    )
  })

  it('shows the empty state when there are no insights at all', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [],
            charts: [],
            insights: null,
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Insights' }))
    expect(screen.getByTestId('artifact-empty')).toBeInTheDocument()
  })

  it('renders the Statistics tab with the dataset statistics', () => {
    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            status: 'completed',
            preview: completed.preview,
            chartData: [],
            charts: [],
            insights: [],
            statistics: { numeric: { age: { count: 42, mean: 30 } } },
          } as unknown as CompletedArtifacts,
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Statistics' }))
    expect(screen.getByTestId('statistics-view')).toBeInTheDocument()
    expect(mockedStatistics).toHaveBeenCalledWith(
      expect.objectContaining({ statistics: expect.any(Object) }),
      undefined,
    )
  })

  it('renders the PDF report and enables download after it loads', async () => {
    URL.createObjectURL = () => 'blob:report'
    URL.revokeObjectURL = () => {}
    mockedFetchFile.mockResolvedValue({
      blob: new Blob(['A4'], { type: 'application/pdf' }),
      filename: 'sales_report.pdf',
    })

    useDatasetStore.setState({
      datasets: [{ ...datasetWithoutArtifacts, artifacts: completed }],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    expect(await screen.findByTitle('Generated PDF Report')).toBeInTheDocument()
    expect(screen.getByText('sales.csv Analysis Report')).toBeInTheDocument()
    expect(mockedFetchFile).toHaveBeenCalledWith('/report/d1.pdf', 'sales_report.pdf')

    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }))
    expect(saveDownloadedFile).toHaveBeenCalledWith(
      expect.objectContaining({ filename: 'sales_report.pdf' }),
    )
  })

  it('shows error state for a failed PDF load with a retry button', async () => {
    URL.createObjectURL = () => 'blob:report'
    URL.revokeObjectURL = () => {}
    mockedFetchFile.mockRejectedValue(new Error('PDF download failed'))

    useDatasetStore.setState({
      datasets: [
        {
          ...datasetWithoutArtifacts,
          artifacts: {
            ...completed,
            report: { url: '/report/retry.pdf' },
          },
        },
      ],
    })

    render(<ArtifactPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Report' }))

    expect(await screen.findByText('PDF download failed')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => {
      expect(screen.getByText('PDF download failed')).toBeInTheDocument()
    })
  })
})