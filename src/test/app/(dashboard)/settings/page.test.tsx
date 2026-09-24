import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import SettingsPage from '../../../../app/(dashboard)/settings/page'
import { downloadAppData } from '../../../../lib/app-data'
import { useDatasetStore } from '../../../../stores/dataset-store'
import { useReportStore } from '../../../../stores/report-store'

vi.mock('next-themes', () => ({
  useTheme: () => ({ theme: themeMock(), setTheme: setThemeMock }),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../../../lib/app-data', () => ({
  APP_VERSION: '1.2.3',
  downloadAppData: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  deleteAllDatasetsApi: vi.fn().mockResolvedValue(undefined),
  deleteAllReportsApi: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/components/ui/alert-dialog', () => ({
  ConfirmDialog: ({
    trigger,
    confirmLabel = 'Delete',
    onConfirm,
    disabled,
  }: {
    trigger: React.ReactNode
    confirmLabel?: string
    onConfirm: () => void
    disabled?: boolean
  }) => (
    <div>
      {trigger}
      <button type="button" onClick={onConfirm} disabled={disabled}>
        {confirmLabel}
      </button>
    </div>
  ),
}))

const setThemeMock = vi.fn()
const themeMock = vi.fn(() => 'light')
const toast = (await import('sonner')).toast as unknown as {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
}

const { deleteAllDatasetsApi, deleteAllReportsApi } = await import('../../../../lib/api')

describe('SettingsPage', () => {
  beforeEach(() => {
    setThemeMock.mockClear()
    themeMock.mockClear()
    themeMock.mockReturnValue('light')
    vi.mocked(downloadAppData).mockClear()
    vi.mocked(deleteAllDatasetsApi).mockClear()
    vi.mocked(deleteAllReportsApi).mockClear()
    toast.success.mockClear()
    toast.error.mockClear()

    useDatasetStore.setState({ datasets: [] })
    useReportStore.setState({ reports: [] })

    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      cb(0)
      return 1
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {})
  })

  it('shows the app name and version', () => {
    render(<SettingsPage />)
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByText('1.2.3')).toBeInTheDocument()
  })

  it('highlights the active theme option', () => {
    themeMock.mockReturnValue('dark')
    render(<SettingsPage />)
    const dark = screen.getByRole('button', { name: /Dark/ })
    expect(dark).toHaveAttribute('aria-pressed', 'true')
    const light = screen.getByRole('button', { name: /Light/ })
    expect(light).toHaveAttribute('aria-pressed', 'false')
  })

  it('changes theme when a theme button is clicked', () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole('button', { name: /System/ }))
    expect(setThemeMock).toHaveBeenCalledWith('system')
  })

  it('exports and toasts when exporting data', () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole('button', { name: /Export data as JSON/ }))
    expect(downloadAppData).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith('Data exported', {
      description: 'Your DataWise data was downloaded as JSON.',
    })
  })

  it('cleans datasets and toasts when confirmed', async () => {
    useDatasetStore.setState({
      datasets: [
        {
          id: 'd1',
          name: 'test.csv',
          size: '1 MB',
          status: 'Analyzed',
        } as any,
      ],
    })

    render(<SettingsPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Clean Datasets' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clean datasets' }))

    await waitFor(() => {
      expect(deleteAllDatasetsApi).toHaveBeenCalledTimes(1)
    })
    expect(useDatasetStore.getState().datasets).toHaveLength(0)
    expect(toast.success).toHaveBeenCalledWith('Datasets cleaned', {
      description: 'All datasets removed from database and local storage.',
    })
  })

  it('cleans reports and toasts when confirmed', async () => {
    useReportStore.setState({
      reports: [
        {
          id: 'r1',
          title: 'Report 1',
          dataset: 'test.csv',
          type: 'AI Analysis',
          date: '2025-01-01',
        } as any,
      ],
    })

    render(<SettingsPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Clean Reports' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clean reports' }))

    await waitFor(() => {
      expect(deleteAllReportsApi).toHaveBeenCalledTimes(1)
    })
    expect(useReportStore.getState().reports).toHaveLength(0)
    expect(toast.success).toHaveBeenCalledWith('Reports cleaned', {
      description: 'All reports removed from database and local storage.',
    })
  })
})