import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SidebarNav } from '../../../components/datawise/sidebar-nav'
import { sidebarNavItems, sidebarSettingsItem } from '../../../lib/sidebar-nav'

const pathnameMock = vi.fn(() => '/dashboard')

vi.mock('next/navigation', () => ({
  usePathname: () => pathnameMock(),
}))

describe('SidebarNav', () => {
  beforeEach(() => {
    pathnameMock.mockReset()
    pathnameMock.mockReturnValue('/dashboard')
  })

  it('renders all nav items plus the settings link', () => {
    render(<SidebarNav />)
    for (const item of sidebarNavItems) {
      expect(screen.getByRole('link', { name: item.label })).toBeInTheDocument()
    }
    expect(
      screen.getByRole('link', { name: sidebarSettingsItem.label }),
    ).toBeInTheDocument()
  })

  it('marks the active item with aria-current="page"', () => {
    pathnameMock.mockReturnValue('/')
    render(<SidebarNav />)
    const link = screen.getByRole('link', { name: 'Home' })
    expect(link).toHaveAttribute('aria-current', 'page')
  })

  it('invokes onNavigate when a link is clicked', () => {
    const onNavigate = vi.fn()
    render(<SidebarNav onNavigate={onNavigate} variant="drawer" />)
    fireEvent.click(screen.getAllByRole('link')[0])
    expect(onNavigate).toHaveBeenCalledTimes(1)
  })

  it('applies animation delays when animateItems is enabled', () => {
    const { container } = render(<SidebarNav animateItems />)
    const firstItem = container.querySelector('li')
    expect(firstItem).not.toBeNull()
    expect((firstItem as HTMLElement).style.animationDelay).toBe('0ms')
  })
})