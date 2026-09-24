import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NotFoundView } from '../../../components/datawise/not-found-view'

describe('NotFoundView', () => {
  it('renders default copy and a dashboard link', () => {
    render(<NotFoundView />)
    expect(
      screen.getByRole('heading', { name: 'Page not found' }),
    ).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'Back to dashboard' })
    expect(link).toHaveAttribute('href', '/')
  })

  it('renders custom title, description, and back target', () => {
    render(
      <NotFoundView
        title="Missing dataset"
        description="This dataset does not exist."
        backHref="/datasets"
        backLabel="All datasets"
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'Missing dataset' }),
    ).toBeInTheDocument()
    expect(screen.getByText('This dataset does not exist.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'All datasets' })).toHaveAttribute(
      'href',
      '/datasets',
    )
  })
})