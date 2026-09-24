import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DashboardShell } from '../../../components/datawise/dashboard-shell'
import { useAuthStore } from '../../../stores/auth-store'

vi.mock('@/hooks/use-require-auth', () => ({
  useRequireAuth: () => true,
}))
vi.mock('@/components/datawise/global-search-provider', () => ({
  GlobalSearchProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="global-search-provider">{children}</div>
  ),
}))
vi.mock('@/components/ui/tooltip', () => ({
  TooltipProvider: ({ children, delay }: { children: React.ReactNode; delay?: number }) => (
    <div data-testid="tooltip-provider" data-delay={String(delay)}>
      {children}
    </div>
  ),
}))
vi.mock('@/components/datawise/top-bar', () => ({
  TopBar: () => <div data-testid="top-bar" />,
}))
vi.mock('@/components/datawise/mobile-sidebar', () => ({
  MobileSidebar: () => <div data-testid="mobile-sidebar" />,
}))
vi.mock('@/components/datawise/sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}))

describe('DashboardShell', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: { email: 'a@b.com' }, isLoaded: true })
  })

  it('renders the providers around the layout and page content', () => {
    render(
      <DashboardShell>
        <p>page body</p>
      </DashboardShell>,
    )
    expect(screen.getByTestId('global-search-provider')).toBeInTheDocument()
    expect(screen.getByTestId('tooltip-provider')).toBeInTheDocument()
    expect(screen.getByTestId('top-bar')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar')).toBeInTheDocument()
    expect(screen.getByText('page body')).toBeInTheDocument()
  })
})