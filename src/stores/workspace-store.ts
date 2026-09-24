import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { createSafeStorage } from '@/lib/safe-storage'

interface WorkspaceStore {
  openDatasetIds: string[]
  activeDatasetId: string | null
  openDataset: (id: string) => void
  setActiveDataset: (id: string) => void
  removeOpenDataset: (id: string) => void
  clearWorkspace: () => void
}

export const useWorkspaceStore = create<WorkspaceStore>()(
  persist(
    (set, get) => ({
      openDatasetIds: [],
      activeDatasetId: null,

      openDataset: (id) =>
        set((state) => {
          const openDatasetIds = state.openDatasetIds.includes(id)
            ? state.openDatasetIds
            : [...state.openDatasetIds, id]

          return {
            openDatasetIds,
            activeDatasetId: id,
          }
        }),

      setActiveDataset: (id) => {
        const { openDatasetIds } = get()
        if (!openDatasetIds.includes(id)) return

        set({ activeDatasetId: id })
      },

      removeOpenDataset: (id) =>
        set((state) => {
          const openDatasetIds = state.openDatasetIds.filter(
            (datasetId) => datasetId !== id,
          )
          const activeDatasetId =
            state.activeDatasetId === id
              ? openDatasetIds[openDatasetIds.length - 1] ?? null
              : state.activeDatasetId

          return { openDatasetIds, activeDatasetId }
        }),

      clearWorkspace: () =>
        set({
          openDatasetIds: [],
          activeDatasetId: null,
        }),
    }),
    {
      name: 'datawise-workspace',
      storage: createJSONStorage(() => createSafeStorage()),
      partialize: (state) => ({
        openDatasetIds: state.openDatasetIds,
        activeDatasetId: state.activeDatasetId,
      }),
    },
  ),
)
