import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { createSafeStorage } from '@/lib/safe-storage'

export interface NotificationItem {
  id: string
  action: string
  file: string
  time: string
  href: string
}

interface NotificationStore {
  items: NotificationItem[]
  seenIds: string[]
  dismissedIds: string[]
  addNotification: (item: NotificationItem) => void
  markAllSeen: (ids: string[]) => void
  dismissAll: (ids: string[]) => void
  clearNotifications: () => void
}

const MAX_NOTIFICATIONS = 50

export const useNotificationStore = create<NotificationStore>()(
  persist(
    (set) => ({
      items: [],
      seenIds: [],
      dismissedIds: [],

      addNotification: (item) =>
        set((state) => {
          if (state.items.some((entry) => entry.id === item.id)) {
            return state
          }
          const next = [item, ...state.items].slice(0, MAX_NOTIFICATIONS)
          return { items: next }
        }),

      markAllSeen: (ids) =>
        set((state) => ({
          seenIds: Array.from(new Set([...state.seenIds, ...ids])),
        })),

      dismissAll: (ids) =>
        set((state) => ({
          dismissedIds: Array.from(new Set([...state.dismissedIds, ...ids])),
          seenIds: Array.from(new Set([...state.seenIds, ...ids])),
        })),

      clearNotifications: () =>
        set({ items: [], seenIds: [], dismissedIds: [] }),
    }),
    {
      name: 'datawise-notifications',
      storage: createJSONStorage(() => createSafeStorage()),
      partialize: (state) => ({
        items: state.items,
        seenIds: state.seenIds,
        dismissedIds: state.dismissedIds,
      }),
    },
  ),
)