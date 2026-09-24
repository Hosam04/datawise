import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Breadcrumbs } from '../../../components/ui/breadcrumbs'

describe('Breadcrumbs', () => {
  it('renders links for non-last items and plain text for the last one', () => {
    render(
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Datasets', href: '/datasets' },
          { label: 'Sales' },
        ]}
      />,
    )
    const home = screen.getByRole('link', { name: 'Home' })
    expect(home).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: 'Datasets' })).toHaveAttribute(
      'href',
      '/datasets',
    )
    const current = screen.getByText('Sales')
    expect(current).toHaveAttribute('aria-current', 'page')
    expect(current.closest('a')).toBeNull()
  })

  it('renders a single item as the current page', () => {
    render(<Breadcrumbs items={[{ label: 'Home', href: '/' }]} />)
    const home = screen.getByText('Home')
    expect(home).toHaveAttribute('aria-current', 'page')
  })
})