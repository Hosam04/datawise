import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorFallback } from '../../../components/datawise/error-fallback'

describe('ErrorFallback', () => {
  it('renders the default copy', () => {
    render(<ErrorFallback />)
    expect(
      screen.getByRole('heading', { name: 'Something went wrong' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/An unexpected error occurred/),
    ).toBeInTheDocument()
  })

  it('renders custom title and description', () => {
    render(<ErrorFallback title="Crash" description="It broke." />)
    expect(screen.getByRole('heading', { name: 'Crash' })).toBeInTheDocument()
    expect(screen.getByText('It broke.')).toBeInTheDocument()
  })

  it('invokes onReset when Try again is clicked', () => {
    const onReset = vi.fn()
    render(<ErrorFallback onReset={onReset} />)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(onReset).toHaveBeenCalledTimes(1)
  })

  it('does not render the reset button without onReset', () => {
    render(<ErrorFallback />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})