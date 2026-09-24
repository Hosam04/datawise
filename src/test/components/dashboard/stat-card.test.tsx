import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatCard } from '../../../components/dashboard/stat-card'

describe('StatCard', () => {
  it('renders a skeleton while loading and hides the real values', () => {
    const { container } = render(<StatCard label="Datasets" value={3} isLoading />)
    expect(screen.queryByText('Datasets')).not.toBeInTheDocument()
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument()
  })

  it('renders the label and value after mount', async () => {
    render(<StatCard label="Datasets" value={3} />)
    expect(await screen.findByText('Datasets')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('renders the trend and change', async () => {
    render(<StatCard label="Revenue" value="12" trend="up" change="+4%" />)
    expect(await screen.findByText('+4%')).toBeInTheDocument()
  })

  it('wraps in a link when href is provided', async () => {
    render(<StatCard label="Reports" value="2" href="/reports" />)
    const link = await screen.findByText('2')
    expect(link.closest('a')).toHaveAttribute('href', '/reports')
  })
})