import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { createSafeStorage } from '@/lib/safe-storage'

export interface GoogleUser {
  name?: string
  email?: string
  picture?: string
  locale?: string
  given_name?: string
  family_name?: string
}

export interface LocalUser {
  id?: string
  email: string
  name: string
  picture?: string
}

interface AuthStore {
  user: GoogleUser | LocalUser | null
  accessToken: string | null
  refreshToken: string | null
  isLoaded: boolean
  setUser: (user: GoogleUser | LocalUser | null) => void
  setAccessToken: (token: string | null) => void
  setRefreshToken: (token: string | null) => void
  setTokens: (access: string | null, refresh: string | null) => void
  setIsLoaded: (loaded: boolean) => void
  logout: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoaded: false,

      setUser: (user) => set({ user }),
      setAccessToken: (token) => set({ accessToken: token }),
      setRefreshToken: (token) => set({ refreshToken: token }),
      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),
      setIsLoaded: (isLoaded) => set({ isLoaded }),

      logout: () =>
        set({ user: null, accessToken: null, refreshToken: null }),

      isAuthenticated: () => {
        const { user, accessToken } = get()
        return !!(user && user.email && accessToken)
      },
    }),
    {
      name: 'datawise-auth',
      storage: createJSONStorage(() => createSafeStorage()),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.setIsLoaded(true)
        }
      },
    },
  ),
)
