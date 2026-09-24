import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import RootLayout, { metadata, viewport } from '../../app/layout'

vi.mock('next/font/google', () => ({
  Geist: () => ({ className: 'geist' }),
}))

vi.mock('@vercel/analytics/next', () => ({
  Analytics: () => <div data-testid="analytics" />,
}))

vi.mock('@/components/app-toaster', () => ({
  AppToaster: () => <div data-testid="app-toaster" />,
}))

vi.mock('@/components/theme-provider', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="theme-provider">{children}</div>
  ),
}))

describe('RootLayout', () => {
  it('renders children inside the theme provider', () => {
    render(
      <RootLayout>
        <p>page content</p>
      </RootLayout>,
    )
    expect(screen.getByTestId('theme-provider')).toBeInTheDocument()
    expect(screen.getByTestId('app-toaster')).toBeInTheDocument()
    expect(screen.getByText('page content')).toBeInTheDocument()
    expect(screen.queryByTestId('analytics')).not.toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('lang', 'en')
  })

  it('exports static metadata and viewport', () => {
    expect(metadata.title).toBe('DataWise - AI Data Analysis')
    expect(typeof metadata.description).toBe('string')
    expect(viewport.colorScheme).toBe('light dark')
    expect(viewport.themeColor).toHaveLength(2)
  })
})