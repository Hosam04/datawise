import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FavoriteButton } from '../../../components/favorites/favorite-button'
import { useFavoriteStore } from '../../../stores/favorite-store'
import type { FavoriteItem } from '../../../stores/favorite-store'

const item: FavoriteItem = {
  id: 'd1',
  name: 'sales.csv',
  type: 'dataset',
  description: '10 KB',
}

describe('FavoriteButton', () => {
  beforeEach(() => {
    useFavoriteStore.setState({ favorites: [] })
  })

  it('starts unfavorited and can be toggled on and off', () => {
    render(<FavoriteButton item={item} showLabel />)
    const button = screen.getByRole('button', { name: 'Add sales.csv to favorites' })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('Add to Favorites')).toBeInTheDocument()

    fireEvent.click(button)
    expect(useFavoriteStore.getState().isFavorite('d1')).toBe(true)
    const nowFav = screen.getByRole('button', { name: 'Remove sales.csv from favorites' })
    expect(nowFav).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Saved to Favorites')).toBeInTheDocument()

    fireEvent.click(nowFav)
    expect(useFavoriteStore.getState().isFavorite('d1')).toBe(false)
  })

  it('remembers an existing favorite from the store', () => {
    useFavoriteStore.setState({ favorites: [item] })
    render(<FavoriteButton item={item} showLabel />)
    expect(
      screen.getByRole('button', { name: 'Remove sales.csv from favorites' }),
    ).toHaveAttribute('aria-pressed', 'true')
  })
})