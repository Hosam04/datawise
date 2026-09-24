import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AppToaster } from '../../components/app-toaster'

vi.mock('next-themes', () => ({
  useTheme: () => ({ resolvedTheme: themeMock() }),
}))

vi.mock('sonner', () => ({
  Toaster: (props: Record<string, unknown>) => (
    <div data-testid="toaster" data-theme={props.theme as string} />
  ),
}))

const themeMock = vi.fn(() => 'light')

describe('AppToaster', () => {
  it('renders a light toaster when the resolved theme is light', () => {
    themeMock.mockReturnValue('light')
    render(<AppToaster />)
    expect(screen.getByTestId('toaster')).toHaveAttribute('data-theme', 'light')
  })

  it('renders a dark toaster when the resolved theme is dark', () => {
    themeMock.mockReturnValue('dark')
    render(<AppToaster />)
    expect(screen.getByTestId('toaster')).toHaveAttribute('data-theme', 'dark')
  })
})