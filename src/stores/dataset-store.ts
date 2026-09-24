import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { CompletedArtifacts } from '@/types/artifacts'
import { createSafeStorage } from '@/lib/safe-storage'

export interface Dataset {
  id: string
  name: string
  size: string
  type: string
  rows?: number
  status: string
  uploadedAt?: string
  /** In-memory only — never written to localStorage (too large for quota). */
  artifacts?: CompletedArtifacts
}

interface DatasetStore {
  datasets: Dataset[]
  addDataset: (dataset: Dataset) => void
  removeDataset: (id: string) => void
  updateDatasetStatus: (id: string, status: string) => void
  setDatasetArtifacts: (id: string, artifacts: CompletedArtifacts) => void
}

/** Strip heavy artifacts before persisting. */
function lightweightDatasets(datasets: Dataset[]): Dataset[] {
  return datasets.map(({ artifacts: _a, ...meta }) => meta)
}

export const useDatasetStore = create<DatasetStore>()(
  persist(
    (set) => ({
      datasets: [],

      addDataset: (dataset) =>
        set((state) => {
          const existingIndex = state.datasets.findIndex((d) => d.id === dataset.id)
          if (existingIndex !== -1) {
            // Update existing dataset with new info (status, size, uploadedAt, etc.)
            const updated = [...state.datasets]
            updated[existingIndex] = { ...updated[existingIndex], ...dataset }
            return { datasets: updated }
          }
          return {
            datasets: [...state.datasets, dataset],
          }
        }),

      removeDataset: (id) =>
        set((state) => ({
          datasets: state.datasets.filter((dataset) => dataset.id !== id),
        })),

      updateDatasetStatus: (id, status) =>
        set((state) => ({
          datasets: state.datasets.map((dataset) =>
            dataset.id === id ? { ...dataset, status } : dataset,
          ),
        })),

      setDatasetArtifacts: (id, artifacts) =>
        set((state) => ({
          datasets: state.datasets.map((dataset) =>
            dataset.id === id ? { ...dataset, artifacts } : dataset,
          ),
        })),
    }),
    {
      name: 'datawise-datasets',
      storage: createJSONStorage(() => createSafeStorage()),
      // CRITICAL: never persist full artifacts (preview/charts/insights) —
      // they blow past the ~5MB localStorage quota on large datasets.
      partialize: (state) => ({
        datasets: lightweightDatasets(state.datasets),
      }),
      merge: (persisted, current) => {
        const p = persisted as { datasets?: Dataset[] } | undefined
        const persistedDatasets = Array.isArray(p?.datasets) ? p!.datasets! : []
        // Rehydrate metadata only; artifacts stay undefined until fetched from API
        return {
          ...current,
          datasets: persistedDatasets.map(({ artifacts: _a, ...meta }) => meta),
        }
      },
    },
  ),
)
