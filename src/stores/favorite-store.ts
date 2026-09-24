import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { createSafeStorage } from '@/lib/safe-storage'
import {
  addFavoriteApi,
  fetchFavorites,
  removeFavoriteApi,
} from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'

export interface FavoriteItem {
  id: string
  name: string
  type: 'dataset' | 'report'
  description: string
}

interface FavoriteStore {
  favorites: FavoriteItem[]
  addFavorite: (item: FavoriteItem) => void
  removeFavorite: (id: string) => void
  toggleFavorite: (item: FavoriteItem) => void
  isFavorite: (id: string) => boolean
  setFavorites: (items: FavoriteItem[]) => void
  syncFromServer: () => Promise<void>
}

function hasAuthToken(): boolean {
  return Boolean(useAuthStore.getState().accessToken)
}

export const useFavoriteStore = create<FavoriteStore>()(
  persist(
    (set, get) => ({
      favorites: [],

      setFavorites: (items) => set({ favorites: items }),

      addFavorite: (item) => {
        set((state) => {
          if (state.favorites.some((favorite) => favorite.id === item.id)) {
            return state
          }
          return { favorites: [...state.favorites, item] }
        })
        if (!hasAuthToken()) {
          console.warn(
            'Favorite saved locally only — not logged in (no access token).',
          )
          return
        }
        void addFavoriteApi(item)
          .then(() => {
            console.info('Favorite persisted to server:', item.id)
          })
          .catch((err) => {
            console.error('Failed to persist favorite to database:', err)
          })
      },

      removeFavorite: (id) => {
        set((state) => ({
          favorites: state.favorites.filter((item) => item.id !== id),
        }))
        if (!hasAuthToken()) return
        void removeFavoriteApi(id).catch((err) =>
          console.error('Failed to remove favorite on server:', err),
        )
      },

      toggleFavorite: (item) => {
        const exists = get().favorites.some((favorite) => favorite.id === item.id)
        if (exists) {
          get().removeFavorite(item.id)
        } else {
          get().addFavorite(item)
        }
      },

      isFavorite: (id) => get().favorites.some((item) => item.id === id),

      syncFromServer: async () => {
        if (!hasAuthToken()) return
        try {
          const remote = await fetchFavorites()
          set({
            favorites: remote.map((f) => ({
              id: f.id,
              name: f.name,
              type: f.type === 'report' ? 'report' : 'dataset',
              description: f.description || '',
            })),
          })
        } catch (err) {
          console.warn('Could not sync favorites from server:', err)
        }
      },
    }),
    {
      name: 'datawise-favorites',
      storage: createJSONStorage(() => createSafeStorage()),
      partialize: (state) => ({ favorites: state.favorites }),
    },
  ),
)
