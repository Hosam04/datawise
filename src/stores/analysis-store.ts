import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { CompletedArtifacts } from '@/types/artifacts'
import type { AnalysisJobStatus } from '@/types/analysis'
import { createSafeStorage } from '@/lib/safe-storage'

export interface AnalysisStoreState {
  sessionId: string | null
  fileName: string | null
  fileSize: string | null
  fileType: string | null
  status: AnalysisJobStatus
  progress: number
  error: string | null
  /** In-memory only — never persisted (quota). */
  artifacts: CompletedArtifacts | null
  isAnalyzing: boolean
  lastUpdated: string | null

  // Actions
  startAnalysis: (info: {
    sessionId: string
    fileName: string
    fileSize?: string
    fileType?: string
  }) => void
  setProgress: (progress: number) => void
  setStatus: (status: AnalysisJobStatus) => void
  setArtifacts: (artifacts: CompletedArtifacts) => void
  setError: (error: string) => void
  clearError: () => void
  setSession: (sessionId: string, fileName?: string) => void
  resetAnalysis: () => void
}

const initialState = {
  sessionId: null,
  fileName: null,
  fileSize: null,
  fileType: null,
  status: 'idle' as AnalysisJobStatus,
  progress: 0,
  error: null,
  artifacts: null,
  isAnalyzing: false,
  lastUpdated: null,
}

export const useAnalysisStore = create<AnalysisStoreState>()(
  persist(
    (set) => ({
      ...initialState,

      startAnalysis: ({ sessionId, fileName, fileSize, fileType }) =>
        set({
          sessionId,
          fileName,
          fileSize: fileSize ?? null,
          fileType: fileType ?? null,
          status: 'uploading',
          progress: 0,
          error: null,
          artifacts: null,
          isAnalyzing: true,
          lastUpdated: new Date().toISOString(),
        }),

      setProgress: (progress) =>
        set({
          progress: Math.min(100, Math.max(0, progress)),
          lastUpdated: new Date().toISOString(),
        }),

      setStatus: (status) =>
        set((state) => ({
          status,
          isAnalyzing: status === 'uploading' || status === 'processing',
          progress: status === 'completed' ? 100 : state.progress,
          lastUpdated: new Date().toISOString(),
        })),

      setArtifacts: (artifacts) =>
        set({
          artifacts,
          status: 'completed',
          progress: 100,
          isAnalyzing: false,
          error: null,
          lastUpdated: new Date().toISOString(),
        }),

      setError: (error) =>
        set({
          error,
          status: 'error',
          isAnalyzing: false,
          lastUpdated: new Date().toISOString(),
        }),

      clearError: () => set({ error: null }),

      setSession: (sessionId, fileName) =>
        set((state) => ({
          sessionId,
          fileName: fileName ?? state.fileName,
          lastUpdated: new Date().toISOString(),
        })),

      resetAnalysis: () =>
        set({ ...initialState, lastUpdated: new Date().toISOString() }),
    }),
    {
      name: 'datawise-analysis',
      storage: createJSONStorage(() => createSafeStorage()),
      // Do NOT persist artifacts — they exceed localStorage quota on large datasets.
      partialize: (state) => ({
        sessionId: state.sessionId,
        fileName: state.fileName,
        fileSize: state.fileSize,
        fileType: state.fileType,
        // Reset to idle on reload if we were mid-flight; keep completed metadata only.
        status:
          state.status === 'uploading' || state.status === 'processing'
            ? 'idle'
            : state.status,
        progress: state.status === 'completed' ? 100 : 0,
        lastUpdated: state.lastUpdated,
      }),
    },
  ),
)
