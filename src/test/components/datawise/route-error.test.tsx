import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RouteError } from '../../../components/datawise/route-error'

describe('RouteError', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('shows the title and error message along with a back link', () => {
    render(
      <RouteError
        error={new Error('boom')}
        reset={() => {}}
        title="Custom title"
        backHref="/datasets"
        backLabel="Back to datasets"
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'Custom title' }),
    ).toBeInTheDocument()
    expect(screen.getByText('boom')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to datasets' })).toHaveAttribute(
      'href',
      '/datasets',
    )
  })

  it('uses the description prop when provided', () => {
    render(
      <RouteError
        error={new Error('boom')}
        reset={() => {}}
        title="Title"
        description="Friendly description"
      />,
    )
    expect(screen.getByText('Friendly description')).toBeInTheDocument()
  })

  it('invokes reset through the Try again button', () => {
    const reset = vi.fn()
    render(<RouteError error={new Error('x')} reset={reset} title="T" />)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(reset).toHaveBeenCalledTimes(1)
  })

  it('logs the error to console.error on mount', () => {
    const error = new Error('logged')
    render(<RouteError error={error} reset={() => {}} title="T" />)
    expect(console.error).toHaveBeenCalledWith(error)
  })

  it('does not render a back link when omitted', () => {
    render(<RouteError error={new Error('x')} reset={() => {}} title="T" />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})