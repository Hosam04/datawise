import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TopBar } from '../../../components/datawise/top-bar'

vi.mock('next-themes', () => ({
  useTheme: () => ({ resolvedTheme: 'light', setTheme: setThemeMock }),
}))

vi.mock('@/components/datawise/dataset-switcher', () => ({
  DatasetSwitcher: () => <div data-testid="dataset-switcher" />,
}))
vi.mock('@/components/datawise/card-skeleton', () => ({
  DatasetSwitcherSkeleton: () => <div data-testid="dataset-switcher-skeleton" />,
}))
vi.mock('@/components/datawise/global-search-provider', () => ({
  GlobalSearchTrigger: ({ variant }: { variant: string }) => (
    <div data-testid={`global-search-${variant}`} />
  ),
}))
vi.mock('@/components/datawise/notifications-dropdown', () => ({
  NotificationsDropdown: () => <div data-testid="notifications-dropdown" />,
}))
vi.mock('@/components/datawise/user-menu', () => ({
  UserMenu: () => <div data-testid="user-menu" />,
}))

const setThemeMock = vi.fn()

describe('TopBar', () => {
  beforeEach(() => {
    setThemeMock.mockClear()
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      cb(0)
      return 1
    })
  })

  it('renders the brand, switcher, search, notifications, and user menu', () => {
    render(<TopBar />)
    expect(screen.getByText('DataWise')).toBeInTheDocument()
    expect(screen.getByTestId('dataset-switcher')).toBeInTheDocument()
    expect(screen.getByTestId('global-search-bar')).toBeInTheDocument()
    expect(screen.getByTestId('global-search-icon')).toBeInTheDocument()
    expect(screen.getByTestId('notifications-dropdown')).toBeInTheDocument()
    expect(screen.getByTestId('user-menu')).toBeInTheDocument()
  })

  it('shows the mobile nav trigger and invokes the callback', () => {
    const onOpen = vi.fn()
    render(<TopBar onOpenMobileNav={onOpen} mobileNavOpen />)
    const navButton = screen.getByRole('button', { name: 'Open navigation menu' })
    expect(navButton).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(navButton)
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('toggles the theme when the theme button is clicked', () => {
    render(<TopBar />)
    const themeButton = screen.getByRole('button', { name: 'Switch to dark mode' })
    fireEvent.click(themeButton)
    expect(setThemeMock).toHaveBeenCalledWith('dark')
  })
})