import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Sidebar } from '../../../components/datawise/sidebar'

vi.mock('@/components/datawise/sidebar-nav', () => ({
  SidebarNav: ({ variant }: { variant: string }) => (
    <nav data-testid="sidebar-nav" data-variant={variant} />
  ),
}))

describe('Sidebar', () => {
  it('renders the compact sidebar navigation', () => {
    render(<Sidebar />)
    expect(screen.getByTestId('sidebar-nav')).toHaveAttribute(
      'data-variant',
      'compact',
    )
  })
})