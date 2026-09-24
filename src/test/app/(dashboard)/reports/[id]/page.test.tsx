import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ReportDetailPage from '../../../../../app/(dashboard)/reports/[id]/page'
import { useReportStore } from '../../../../../stores/report-store'
import { downloadReportFile, fetchFile } from '../../../../../lib/api'

const router = { replace: vi.fn() }

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
  assetUrl: (p: string) => `/asset${p}`,
  downloadReportFile: vi.fn(),
  fetchFile: vi.fn(),
}))

vi.mock('@/lib/format', () => ({
  formatDisplayDate: () => 'Jan 1, 2026',
}))

vi.mock('@/lib/sort-utils', () => ({
  getReportTimestamp: () => 100,
}))

vi.mock('@/lib/utils', () => ({ cn: (...args: unknown[]) => args.filter(Boolean).join(' ') }))
vi.mock('@/lib/app-links', () => ({
  chatHref: (id: string) => `/chat?dataset=${id}`,
  datasetHref: (id: string) => `/datasets/${id}`,
}))
vi.mock('@/components/ui/button', () => ({ buttonVariants: () => 'btn' }))
vi.mock('@/components/ui/breadcrumbs', () => ({
  Breadcrumbs: ({ items }: { items: { label: string }[] }) => (
    <nav>{items.map((i) => i.label).join(' / ')}</nav>
  ),
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
vi.mock('@/hooks/use-store-hydration', () => ({
  useReportStoreHydration: () => hydratedMock(),
}))

const paramsMock = vi.fn()
const hydratedMock = vi.fn(() => true)
const toast = (await import('sonner')).toast as unknown as {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
}

const report = {
  id: 'sales-report',
  title: 'Sales report',
  dataset: 'sales.csv',
  datasetId: 'sales',
  createdAt: 'x',
  date: '2026-01-01',
  type: 'Summary',
}

describe('ReportDetailPage', () => {
  beforeEach(() => {
    router.replace.mockClear()
    paramsMock.mockReset()
    paramsMock.mockReturnValue({ id: 'sales-report' })
    hydratedMock.mockReturnValue(true)
    vi.mocked(downloadReportFile).mockReset()
    vi.mocked(downloadReportFile).mockResolvedValue(undefined)
    vi.mocked(fetchFile).mockReset()
    vi.mocked(fetchFile).mockResolvedValue({
      blob: new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
      filename: 'sales_report.pdf',
    })
    URL.createObjectURL = vi.fn(() => 'blob:pdf-preview')
    URL.revokeObjectURL = vi.fn()
    toast.success.mockClear()
    toast.error.mockClear()
    useReportStore.setState({ reports: [report] })
  })

  it('shows the report summary, metadata, and preview frame', async () => {
    render(<ReportDetailPage />)
    // Page derives title as `${datasetWithoutExt}_report`
    expect(screen.getByRole('heading', { name: 'sales_report' })).toBeInTheDocument()
    expect(screen.getByText('Generated on Jan 1, 2026 • Summary')).toBeInTheDocument()
    expect(screen.getAllByText('sales.csv').length).toBeGreaterThan(0)
    await waitFor(() => {
      expect(screen.getByTitle('PDF Report Viewer')).toBeInTheDocument()
    })
  })

  it('renders the skeleton until stores have hydrated', () => {
    hydratedMock.mockReturnValue(false)
    render(<ReportDetailPage />)
    expect(screen.getByTestId('skeleton')).toBeInTheDocument()
  })

  it('redirects to the reports list when the report does not exist', () => {
    paramsMock.mockReturnValue({ id: 'missing' })
    render(<ReportDetailPage />)
    expect(router.replace).toHaveBeenCalledWith('/reports')
  })

  it('exports the report and shows a success toast', async () => {
    render(<ReportDetailPage />)
    fireEvent.click(screen.getByRole('button', { name: /Export PDF/ }))
    await waitFor(() => {
      expect(downloadReportFile).toHaveBeenCalledWith('sales', 'sales_report.pdf')
    })
    expect(toast.success).toHaveBeenCalledWith('Report downloaded', {
      description: 'sales_report.pdf',
    })
  })

  it('shows an error toast when the export fails', async () => {
    vi.mocked(downloadReportFile).mockRejectedValue(new Error('network'))
    render(<ReportDetailPage />)
    fireEvent.click(screen.getByRole('button', { name: /Export PDF/ }))
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to download report', {
        description: 'network',
      })
    })
  })

  it('opens the fullscreen preview and closes it with Escape', async () => {
    render(<ReportDetailPage />)
    const fullscreenBtn = await waitFor(() => {
      const btn = screen.getByRole('button', { name: /Fullscreen/ })
      expect(btn).not.toBeDisabled()
      return btn
    })
    fireEvent.click(fullscreenBtn)
    const dialog = screen.getByRole('dialog', { name: 'Report Fullscreen Preview' })
    expect(dialog).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})