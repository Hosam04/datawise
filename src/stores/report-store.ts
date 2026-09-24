import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { createSafeStorage } from '@/lib/safe-storage'

export interface Report {
  id: string
  title: string
  dataset: string
  datasetId?: string
  type: string
  date: string
  createdAt?: string
}

interface ReportStore {
  reports: Report[]
  addReport: (report: Report) => void
  removeReport: (id: string) => void
}

export const useReportStore = create<ReportStore>()(
  persist(
    (set) => ({
      reports: [],

      addReport: (report) =>
        set((state) => {
          if (state.reports.some((entry) => entry.id === report.id)) {
            return state
          }

          return {
            reports: [...state.reports, report],
          }
        }),

      removeReport: (id) =>
        set((state) => ({
          reports: state.reports.filter((report) => report.id !== id),
        })),
    }),
    {
      name: 'datawise-reports',
      storage: createJSONStorage(() => createSafeStorage()),
      partialize: (state) => ({ reports: state.reports }),
    },
  ),
)
