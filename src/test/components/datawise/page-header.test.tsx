import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageHeader } from '../../../components/datawise/page-header'

describe('PageHeader', () => {
  it('renders the title and description', () => {
    render(<PageHeader title="Datasets" description="All your data" />)
    expect(screen.getByRole('heading', { name: 'Datasets' })).toBeInTheDocument()
    expect(screen.getByText('All your data')).toBeInTheDocument()
  })

  it('renders actions when provided', () => {
    render(
      <PageHeader
        title="Datasets"
        actions={<button type="button">New dataset</button>}
      />,
    )
    expect(screen.getByRole('button', { name: 'New dataset' })).toBeInTheDocument()
  })

  it('omits the description and actions when not provided', () => {
    const { container } = render(<PageHeader title="Only title" />)
    expect(screen.getByRole('heading', { name: 'Only title' })).toBeInTheDocument()
    expect(container.querySelector('p')).toBeNull()
  })
})