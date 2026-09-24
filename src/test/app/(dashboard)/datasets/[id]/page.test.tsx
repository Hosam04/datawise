import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DatasetDetailPage from '../../../../../app/(dashboard)/datasets/[id]/page'
import { useDatasetStore } from '../../../../../stores/dataset-store'
import { useWorkspaceStore } from '../../../../../stores/workspace-store'
import { useReportStore } from '../../../../../stores/report-store'

const router = { replace: vi.fn(), push: vi.fn() }
const paramsMock = vi.fn()
const hydratedMock = vi.fn(() => true)

const downloadProcessedDataset = vi.fn()
const deleteDatasetApi = vi.fn()

vi.mock('next/navigation', () => ({
  useParams: () => paramsMock(),
  useRouter: () => router,
}))

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/lib/api', () => ({
  downloadProcessedDataset: (...args: unknown[]) => downloadProcessedDataset(...args),
  deleteDatasetApi: (...args: unknown[]) => deleteDatasetApi(...args),
}))

vi.mock('@/lib/format', () => ({
  formatDisplayDate: () => 'Jan 1, 2026',
  formatFileType: (t: string) => t.toUpperCase(),
}))

vi.mock('@/lib/sort-utils', () => ({
  getDatasetTimestamp: () => 100,
}))

vi.mock('@/lib/utils', () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(' '),
}))

vi.mock('@/lib/app-links', () => ({
  chatHref: (id: string) => `/chat?dataset=${id}`,
  reportHref: (id: string) => `/reports/${id}`,
}))

vi.mock('@/components/ui/button', () => ({
  buttonVariants: () => 'btn',
}))

vi.mock('@/components/ui/breadcrumbs', () => ({
  Breadcrumbs: ({ items }: { items: { label: string }[] }) => (
    <nav>{items.map((i) => i.label).join(' / ')}</nav>
  ),
}))

vi.mock('@/components/datawise/status-badge', () => ({
  StatusBadge: ({ status }: { status: string }) => <span>{status}</span>,
}))

vi.mock('@/components/datawise/detail-section', () => ({
  ActionBar: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DetailSection: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
  MetadataGrid: ({ items }: { items: { label: string; value: string }[] }) => (
    <dl>
      {items.map((i) => (
        <div key={i.label}>
          <dt>{i.label}</dt>
          <dd>{i.value}</dd>
        </div>
      ))}
    </dl>
  ),
}))

vi.mock('@/components/datawise/detail-page-skeleton', () => ({
  DetailPageSkeleton: () => <div data-testid="skeleton" />,
}))

vi.mock('@/components/favorites/favorite-button', () => ({
  FavoriteButton: () => <button type="button" aria-label="Favorite" />,
}))

// Keep ConfirmDialog real (uses real Button). Only stub the buttonVariants module above.
// Provide a minimal Button so ConfirmDialog can render if it imports it.
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

vi.mock('@/hooks/use-store-hydration', () => ({
  useDatasetStoreHydration: () => hydratedMock(),
}))

const toast = (await import('sonner')).toast as unknown as {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
}

const dataset = {
  id: 'd1',
  name: 'sales.csv',
  size: '10 KB',
  type: 'CSV' as const,
  status: 'Analyzed' as const,
  uploadedAt: 'x',
}

describe('DatasetDetailPage', () => {
  beforeEach(() => {
    router.replace.mockClear()
    router.push.mockClear()
    paramsMock.mockReset()
    paramsMock.mockReturnValue({ id: 'd1' })
    hydratedMock.mockReturnValue(true)
    downloadProcessedDataset.mockReset()
    downloadProcessedDataset.mockResolvedValue(undefined)
    deleteDatasetApi.mockReset()
    deleteDatasetApi.mockResolvedValue(undefined)
    toast.success.mockClear()
    toast.error.mockClear()
    useDatasetStore.setState({ datasets: [dataset] })
    useWorkspaceStore.setState({ openDatasetIds: [], activeDatasetId: null })
    useReportStore.setState({ reports: [] })
  })

  it('shows the dataset header and metadata', () => {
    render(<DatasetDetailPage />)
    expect(screen.getByRole('heading', { name: 'sales.csv' })).toBeInTheDocument()
    expect(screen.getByText('Uploaded Jan 1, 2026')).toBeInTheDocument()
    expect(screen.getByText('File size')).toBeInTheDocument()
    expect(screen.getByText('CSV')).toBeInTheDocument()
  })

  it('renders the skeleton until stores have hydrated', () => {
    hydratedMock.mockReturnValue(false)
    render(<DatasetDetailPage />)
    expect(screen.getByTestId('skeleton')).toBeInTheDocument()
  })

  it('redirects to the datasets list when the dataset does not exist', () => {
    paramsMock.mockReturnValue({ id: 'missing' })
    render(<DatasetDetailPage />)
    expect(router.replace).toHaveBeenCalledWith('/datasets')
  })

  it('downloaded button only appears for analyzed datasets and shows a toast', async () => {
    render(<DatasetDetailPage />)
    fireEvent.click(screen.getByRole('button', { name: /Download Processed Dataset/ }))
    await waitFor(() => {
      expect(downloadProcessedDataset).toHaveBeenCalledWith('d1', 'sales_processed.csv')
    })
    expect(toast.success).toHaveBeenCalledWith('Processed dataset downloaded', {
      description: 'sales_processed.csv',
    })
  })

  it('hides the download button while the dataset is processing', () => {
    useDatasetStore.setState({ datasets: [{ ...dataset, status: 'Processing' }] })
    render(<DatasetDetailPage />)
    expect(
      screen.queryByRole('button', { name: /Download Processed Dataset/ }),
    ).not.toBeInTheDocument()
  })

  it('shows a report link when a related report exists', () => {
    useReportStore.setState({
      reports: [
        {
          id: 'd1-report',
          title: 'Report',
          datasetId: 'd1',
          dataset: 'sales.csv',
          createdAt: 'x',
          date: 'x',
          type: 'Summary',
        },
      ],
    })
    render(<DatasetDetailPage />)
    expect(screen.getByRole('link', { name: /View report/ })).toHaveAttribute(
      'href',
      '/reports/d1-report',
    )
  })

  it('deletes the dataset after confirming', async () => {
    render(<DatasetDetailPage />)
    fireEvent.click(screen.getByRole('button', { name: /Delete dataset/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(useDatasetStore.getState().datasets).toHaveLength(0)
    })
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual([])
    expect(toast.success).toHaveBeenCalledWith('Dataset deleted', { description: 'sales.csv' })
    expect(router.push).toHaveBeenCalledWith('/datasets')
  })
})