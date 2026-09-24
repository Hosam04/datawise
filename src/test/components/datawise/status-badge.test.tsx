import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from '../../../components/datawise/status-badge'

describe('StatusBadge', () => {
  it('renders the status text as-is', () => {
    render(<StatusBadge status="Analyzed" />)
    expect(screen.getByText('Analyzed')).toBeInTheDocument()
  })

  it('applies the analyzed color variant for lowercase input too', () => {
    const { container } = render(<StatusBadge status="analyzed" />)
    expect(container.firstChild).toHaveClass('bg-primary/10')
    expect(container.firstChild).not.toHaveClass('bg-amber-500/10')
  })

  it('applies the processing variant', () => {
    const { container } = render(<StatusBadge status="Processing" />)
    expect(container.firstChild).toHaveClass('bg-amber-500/10')
  })

  it('falls back to the muted variant for unknown statuses', () => {
    const { container } = render(<StatusBadge status="Failed" />)
    expect(container.firstChild).toHaveClass('bg-muted')
  })
})