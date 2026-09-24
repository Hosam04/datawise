import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ReportCard } from '../../../components/reports/report-card'
import { useReportStore } from '../../../stores/report-store'
import { downloadReportFile, deleteReportApi } from '../../../lib/api'

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('@/lib/api', () => ({
  downloadReportFile: vi.fn(),
  deleteReportApi: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/components/favorites/favorite-button', () => ({
  FavoriteButton: () => <button type="button" aria-label="Favorite" />,
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

const toast = (await import('sonner')).toast as unknown as {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
}

describe('ReportCard', () => {
  beforeEach(() => {
    vi.mocked(downloadReportFile).mockReset()
    vi.mocked(downloadReportFile).mockResolvedValue(undefined)
    vi.mocked(deleteReportApi).mockReset()
    vi.mocked(deleteReportApi).mockResolvedValue(undefined)
    toast.success.mockClear()
    toast.error.mockClear()
    useReportStore.setState({
      reports: [
        {
          id: 'sales-report',
          title: 'Sales report',
          dataset: 'sales.csv',
          datasetId: 'sales',
          date: 'x',
          createdAt: 'x',
          type: 'Summary',
        },
      ],
    })
  })

  it('renders title, dataset, date, and a report link', () => {
    render(
      <ReportCard
        id="sales-report"
        title="Sales report"
        dataset="sales.csv"
        date="Jun 1, 2025"
        type="Summary"
      />,
    )
    // Component derives display title as `${datasetWithoutExt}_report`
    const title = screen.getByRole('heading', { name: 'sales_report' })
    expect(title).toBeInTheDocument()
    expect(screen.getByText(/Summary/)).toBeInTheDocument()
    expect(screen.getByText(/Jun 1, 2025/)).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/reports/sales-report')
  })

  it('exports the report and shows a success toast', async () => {
    render(
      <ReportCard
        id="sales-report"
        title="Sales report"
        dataset="sales.csv"
        date="x"
        type="Summary"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Export report sales_report' }))
    await waitFor(() => {
      expect(downloadReportFile).toHaveBeenCalledWith(
        'sales',
        'sales_report.pdf',
      )
    })
    expect(toast.success).toHaveBeenCalledWith('Report downloaded', {
      description: 'sales_report.pdf',
    })
  })

  it('shows an error toast when the export fails', async () => {
    vi.mocked(downloadReportFile).mockRejectedValue(new Error('network'))
    render(
      <ReportCard
        id="sales-report"
        title="Sales report"
        dataset="sales.csv"
        date="x"
        type="Summary"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Export report sales_report' }))
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalled()
    })
  })

  it('removes the report after confirming', async () => {
    useReportStore.setState({
      reports: [
        {
          id: 'sales-report',
          title: 'Sales report',
          dataset: 'sales',
          datasetId: 'sales',
          date: 'x',
          createdAt: 'x',
          type: 'Summary',
        },
        { id: 'other', title: 'Other', dataset: 'a', date: 'y', createdAt: 'y', type: 'Summary' },
      ],
    })
    render(
      <ReportCard
        id="sales-report"
        title="Sales report"
        dataset="sales.csv"
        date="x"
        type="Summary"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Remove sales_report' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(useReportStore.getState().reports.map((r) => r.id)).toEqual(['other'])
    })
  })
})