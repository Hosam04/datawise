import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import FavoritesPage from '../../../../app/(dashboard)/favorites/page'
import { useFavoriteStore } from '../../../../stores/favorite-store'

vi.mock('@/components/favorites/favorite-card', () => ({
  FavoriteCard: ({ id, name }: { id: string; name: string }) => (
    <div data-testid="favorite-card">{name}({id})</div>
  ),
}))
vi.mock('@/components/datawise/animated-list', () => ({
  AnimatedList: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
vi.mock('@/components/datawise/empty-state', () => ({
  EmptyState: () => <div data-testid="empty" />,
}))
vi.mock('@/components/datawise/page-header', () => ({ PageHeader: () => <header /> }))
vi.mock('@/hooks/use-store-hydration', () => ({
  useFavoriteStoreHydration: () => true,
}))

describe('FavoritesPage', () => {
  beforeEach(() => {
    useFavoriteStore.setState({ favorites: [] })
  })

  it('shows the empty state when there are no favorites', async () => {
    render(<FavoritesPage />)
    await act(async () => {})
    expect(screen.getByTestId('empty')).toBeInTheDocument()
  })

  it('renders a card for every favorite', async () => {
    useFavoriteStore.setState({
      favorites: [
        { id: 'd1', name: 'sales.csv', type: 'dataset', description: 'CSV' },
        { id: 'r1', name: 'Report 1', type: 'report', description: 'Summary' },
      ],
    })
    render(<FavoritesPage />)
    await act(async () => {})
    expect(screen.getAllByTestId('favorite-card')).toHaveLength(2)
    expect(screen.getAllByTestId('favorite-card')[0]).toHaveTextContent('sales.csv(d1)')
  })
})