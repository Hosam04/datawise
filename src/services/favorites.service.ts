import { authFetch, API_URL, errorMessage } from '@/lib/api'
import type { FavoriteDto } from '@/lib/api'

export async function fetchFavorites(): Promise<FavoriteDto[]> {
  const response = await authFetch(`${API_URL}/favorites`)
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to load favorites'))
  }
  return (await response.json()) as FavoriteDto[]
}

export async function addFavoriteApi(item: FavoriteDto): Promise<FavoriteDto> {
  const response = await authFetch(`${API_URL}/favorites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  })
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to save favorite'))
  }
  return (await response.json()) as FavoriteDto
}

export async function removeFavoriteApi(itemId: string): Promise<void> {
  const response = await authFetch(`${API_URL}/favorites/${encodeURIComponent(itemId)}`, {
    method: 'DELETE',
  })
  if (!response.ok && response.status !== 404) {
    throw new Error(await errorMessage(response, 'Failed to remove favorite'))
  }
}

export type { FavoriteDto }