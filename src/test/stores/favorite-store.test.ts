import { beforeEach, describe, expect, it } from 'vitest'
import { useFavoriteStore } from '../../stores/favorite-store'

beforeEach(() => {
  useFavoriteStore.setState({ favorites: [] })
  localStorage.clear()
})

const DATASET_FAVORITE = {
  id: 'f1',
  name: 'sales.csv',
  type: 'dataset' as const,
  description: '10 KB · Analyzed',
}

const REPORT_FAVORITE = {
  id: 'f2',
  name: 'Sales report',
  type: 'report' as const,
  description: 'summary',
}

describe('favorite-store', () => {
  it('starts with no favorites', () => {
    expect(useFavoriteStore.getState().favorites).toEqual([])
  })

  it('addFavorite appends and keeps insertion order', () => {
    const { addFavorite } = useFavoriteStore.getState()
    addFavorite(DATASET_FAVORITE)
    addFavorite(REPORT_FAVORITE)
    expect(useFavoriteStore.getState().favorites.map((f) => f.id)).toEqual([
      'f1',
      'f2',
    ])
  })

  it('addFavorite dedupes by id', () => {
    const { addFavorite } = useFavoriteStore.getState()
    addFavorite(DATASET_FAVORITE)
    addFavorite(DATASET_FAVORITE)
    expect(useFavoriteStore.getState().favorites).toHaveLength(1)
  })

  it('removeFavorite removes by id', () => {
    const { addFavorite, removeFavorite } = useFavoriteStore.getState()
    addFavorite(DATASET_FAVORITE)
    removeFavorite('f1')
    expect(useFavoriteStore.getState().favorites).toEqual([])
  })

  it('toggleFavorite adds then removes', () => {
    const { toggleFavorite } = useFavoriteStore.getState()
    toggleFavorite(DATASET_FAVORITE)
    expect(useFavoriteStore.getState().isFavorite('f1')).toBe(true)
    expect(useFavoriteStore.getState().favorites).toHaveLength(1)

    toggleFavorite(DATASET_FAVORITE)
    expect(useFavoriteStore.getState().isFavorite('f1')).toBe(false)
    expect(useFavoriteStore.getState().favorites).toEqual([])
  })

  it('isFavorite reflects membership', () => {
    const { addFavorite, isFavorite } = useFavoriteStore.getState()
    expect(isFavorite('f1')).toBe(false)
    addFavorite(DATASET_FAVORITE)
    expect(isFavorite('f1')).toBe(true)
    expect(isFavorite('missing')).toBe(false)
  })

  it('persists favorites to localStorage', () => {
    useFavoriteStore.getState().addFavorite(DATASET_FAVORITE)
    const persisted = JSON.parse(
      localStorage.getItem('datawise-favorites') ?? '{}',
    )
    expect(persisted.state.favorites).toEqual([DATASET_FAVORITE])
  })
})