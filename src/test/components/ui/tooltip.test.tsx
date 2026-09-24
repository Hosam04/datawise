import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Tooltip, TooltipProvider, IconTooltip } from '../../../components/ui/tooltip'

vi.mock('@base-ui/react/tooltip', () => ({
  Tooltip: {
    Provider: ({ children, delay }: { children: React.ReactNode; delay?: number }) => (
      <div data-testid="tooltip-provider" data-delay={String(delay)}>
        {children}
      </div>
    ),
    Root: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="tooltip-root">{children}</div>
    ),
    Trigger: ({ children, render }: { children?: React.ReactNode; render?: React.ReactNode }) =>
      render ?? children,
    Portal: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="tooltip-portal">{children}</div>
    ),
    Positioner: ({ children, side }: { children: React.ReactNode; side?: string }) => (
      <div data-side={side}>{children}</div>
    ),
    Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  },
}))

describe('TooltipProvider', () => {
  it('renders children and forwards the delay', () => {
    render(
      <TooltipProvider delay={250}>
        <span>content</span>
      </TooltipProvider>,
    )
    expect(screen.getByTestId('tooltip-provider')).toHaveAttribute('data-delay', '250')
    expect(screen.getByText('content')).toBeInTheDocument()
  })
})

describe('Tooltip', () => {
  it('renders children directly when disabled', () => {
    render(
      <Tooltip content="hint" disabled>
        <button type="button">btn</button>
      </Tooltip>,
    )
    expect(screen.queryByTestId('tooltip-root')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'btn' })).toBeInTheDocument()
  })

  it('wraps the trigger and shows the content in the popup', () => {
    render(
      <Tooltip content="Saved!">
        <button type="button">save</button>
      </Tooltip>,
    )
    expect(screen.getByTestId('tooltip-root')).toBeInTheDocument()
    expect(screen.getByTestId('tooltip-portal')).toBeInTheDocument()
  })
})

describe('IconTooltip', () => {
  it('renders a labelled button and disables when disabled', () => {
    render(
      <IconTooltip label="Download" disabled>
        <span>icon</span>
      </IconTooltip>,
    )
    expect(screen.getByRole('button', { name: 'Download' })).toBeDisabled()
  })
})