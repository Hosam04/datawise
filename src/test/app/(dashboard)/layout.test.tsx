import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import DashboardLayout from '../../../app/(dashboard)/layout'

vi.mock('@/components/datawise/dashboard-shell', () => ({
  DashboardShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="shell">{children}</div>
  ),
}))

describe('DashboardLayout', () => {
  it('wraps children in the dashboard shell', () => {
    render(
      <DashboardLayout>
        <p>page content</p>
      </DashboardLayout>,
    )
    expect(screen.getByTestId('shell')).toBeInTheDocument()
    expect(screen.getByText('page content')).toBeInTheDocument()
  })
})