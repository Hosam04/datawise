import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import SettingsPage from '../../../../app/(dashboard)/settings/page'
import { clearAllAppData, downloadAppData } from '../../../../lib/app-data'

vi.mock('next-themes', () => ({
  useTheme: () => ({ theme: themeMock(), setTheme: setThemeMock }),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn() },
}))

vi.mock('../../../../lib/app-data', () => ({
  APP_VERSION: '1.2.3',
  clearAllAppData: vi.fn(),
  downloadAppData: vi.fn(),
}))

vi.mock('@/components/ui/alert-dialog', () => ({
  ConfirmDialog: ({
    trigger,
    confirmLabel = 'Delete',
    onConfirm,
  }: {
    trigger: React.ReactNode
    confirmLabel?: string
    onConfirm: () => void
  }) => (
    <div>
      {trigger}
      <button type="button" onClick={onConfirm}>
        {confirmLabel}
      </button>
    </div>
  ),
}))

const setThemeMock = vi.fn()
const themeMock = vi.fn(() => 'light')
const toast = (await import('sonner')).toast as unknown as {
  success: ReturnType<typeof vi.fn>
}

describe('SettingsPage', () => {
  beforeEach(() => {
    setThemeMock.mockClear()
    themeMock.mockClear()
    themeMock.mockReturnValue('light')
    vi.mocked(clearAllAppData).mockClear()
    vi.mocked(downloadAppData).mockClear()
    toast.success.mockClear()
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

  it('clears all data and toasts when confirmed', async () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole('button', { name: /Clear all data/ }))
    expect(screen.getByRole('button', { name: 'Clear all' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    await waitFor(() => {
      expect(clearAllAppData).toHaveBeenCalledTimes(1)
    })
    expect(toast.success).toHaveBeenCalledWith('All data cleared', {
      description: 'Datasets, reports, and favorites were removed.',
    })
  })
})