import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { FavoriteCard } from '../../../components/favorites/favorite-card'
import { useFavoriteStore } from '../../../stores/favorite-store'

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn() },
}))

describe('FavoriteCard', () => {
  beforeEach(() => {
    useFavoriteStore.setState({ favorites: [] })
  })

  it('renders name and description with a dataset href', () => {
    render(
      <FavoriteCard
        id="d1"
        name="sales.csv"
        type="dataset"
        description="sales.csv • CSV"
      />,
    )
    expect(screen.getByRole('heading', { name: 'sales.csv' })).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/datasets/d1')
  })

  it('links reports to the report page', () => {
    render(
      <FavoriteCard
        id="sales-report"
        name="Sales report"
        type="report"
        description="Summary"
      />,
    )
    expect(screen.getByRole('link')).toHaveAttribute('href', '/reports/sales-report')
  })

  it('removes the favorite after confirming', async () => {
    useFavoriteStore.setState({
      favorites: [
        { id: 'd1', name: 'sales.csv', type: 'dataset', description: 'x' },
        { id: 'd2', name: 'billing.csv', type: 'dataset', description: 'y' },
      ],
    })
    render(
      <FavoriteCard
        id="d1"
        name="sales.csv"
        type="dataset"
        description="x"
      />,
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Remove sales.csv from favorites' }),
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))
    await waitFor(() => {
      expect(useFavoriteStore.getState().favorites.map((f) => f.id)).toEqual(['d2'])
    })
  })
})