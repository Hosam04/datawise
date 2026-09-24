import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DatasetCard } from '../../../components/datasets/dataset-card'
import { useDatasetStore } from '../../../stores/dataset-store'
import { useWorkspaceStore } from '../../../stores/workspace-store'
import { downloadProcessedDataset, deleteDatasetApi } from '../../../lib/api'

const pushMock = vi.fn()
const pathnameMock = vi.fn(() => '/datasets')

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => pathnameMock(),
  useSearchParams: () => ({ get: () => null }),
}))

vi.mock('@/lib/api', () => ({
  downloadProcessedDataset: vi.fn(),
  deleteDatasetApi: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/components/ui/alert-dialog', () => ({
  ConfirmDialog: ({
    trigger,
    confirmLabel = 'Delete',
    onConfirm,
  }: {
    trigger: React.ReactNode
    confirmLabel?: string
    onConfirm: () => void | Promise<void>
  }) => (
    <div>
      {trigger}
      <button type="button" onClick={() => void onConfirm()}>
        {confirmLabel}
      </button>
    </div>
  ),
}))

describe('DatasetCard', () => {
  beforeEach(() => {
    pushMock.mockReset()
    pathnameMock.mockReset()
    pathnameMock.mockReturnValue('/datasets')
    vi.mocked(downloadProcessedDataset).mockReset()
    vi.mocked(downloadProcessedDataset).mockResolvedValue(undefined)
    vi.mocked(deleteDatasetApi).mockReset()
    vi.mocked(deleteDatasetApi).mockResolvedValue(undefined)
    useDatasetStore.setState({ datasets: [] })
    useWorkspaceStore.setState({ openDatasetIds: [] })
  })

  it('renders the name, size, status, and an Uploaded date', () => {
    render(
      <DatasetCard
        id="d1"
        name="sales.csv"
        size="10 KB"
        status="Analyzed"
        uploadedAt="2025-06-01T10:00:00Z"
      />,
    )
    expect(screen.getByText('sales.csv')).toBeInTheDocument()
    expect(screen.getByText('10 KB')).toBeInTheDocument()
    expect(screen.getByText('Analyzed')).toBeInTheDocument()
    expect(screen.getByText(/Jun 1, 2025/)).toBeInTheDocument()
  })

  it('links to the dataset detail page', () => {
    render(<DatasetCard id="d1" name="sales.csv" size="10 KB" status="Analyzed" />)
    expect(screen.getByRole('link')).toHaveAttribute('href', '/datasets/d1')
  })

  it('downloads the processed dataset for analyzed datasets', async () => {
    render(<DatasetCard id="d1" name="sales.csv" size="10 KB" status="Analyzed" />)
    fireEvent.click(
      screen.getByRole('button', { name: 'Download processed dataset sales.csv' }),
    )
    await waitFor(() => {
      expect(downloadProcessedDataset).toHaveBeenCalledWith(
        'd1',
        'sales_processed.csv',
      )
    })
  })

  it('does not offer a download for non-analyzed datasets', () => {
    render(<DatasetCard id="d1" name="sales.csv" size="10 KB" status="Processing" />)
    expect(
      screen.queryByRole('button', { name: 'Download processed dataset sales.csv' }),
    ).not.toBeInTheDocument()
  })

  it('removes the dataset and navigates away when deleted on its own page', async () => {
    useDatasetStore.setState({
      datasets: [{ id: 'd1', name: 'sales.csv', size: '10 KB', type: 'CSV', status: 'Analyzed' }],
    })
    pathnameMock.mockReturnValue('/datasets/d1')
    render(<DatasetCard id="d1" name="sales.csv" size="10 KB" status="Analyzed" />)

    fireEvent.click(screen.getByRole('button', { name: 'Remove sales.csv' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(useDatasetStore.getState().datasets).toEqual([])
    })
    expect(pushMock).toHaveBeenCalledWith('/datasets')
  })

  it('does not navigate when deleted from the list page', async () => {
    useDatasetStore.setState({
      datasets: [{ id: 'd1', name: 'sales.csv', size: '10 KB', type: 'CSV', status: 'Analyzed' }],
    })
    render(<DatasetCard id="d1" name="sales.csv" size="10 KB" status="Analyzed" />)

    fireEvent.click(screen.getByRole('button', { name: 'Remove sales.csv' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(useDatasetStore.getState().datasets).toEqual([])
    })
    expect(pushMock).not.toHaveBeenCalled()
  })
})