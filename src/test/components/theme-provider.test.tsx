import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '../../components/theme-provider'

vi.mock('next-themes', () => ({
  ThemeProvider: ({
    children,
    ...props
  }: {
    children: React.ReactNode
    attribute: string
    defaultTheme?: string
    enableSystem?: boolean
  }) => (
    <div
      data-testid="next-themes-provider"
      data-attribute={props.attribute}
      data-default-theme={props.defaultTheme}
      data-enable-system={String(props.enableSystem)}
    >
      {children}
    </div>
  ),
}))

describe('ThemeProvider', () => {
  it('wraps children in next-themes with class-based theming', () => {
    render(
      <ThemeProvider>
        <p>child</p>
      </ThemeProvider>,
    )
    const provider = screen.getByTestId('next-themes-provider')
    expect(provider).toHaveAttribute('data-attribute', 'class')
    expect(provider).toHaveAttribute('data-default-theme', 'system')
    expect(provider).toHaveAttribute('data-enable-system', 'true')
    expect(screen.getByText('child')).toBeInTheDocument()
  })
})