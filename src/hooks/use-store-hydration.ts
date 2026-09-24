import { useEffect, useRef } from 'react'
import {
  usePersistHydration,
  usePersistHydrations,
} from '@/hooks/use-persist-hydration'
import { hydrateUserDataFromServer } from '@/lib/hydrate-user-data'
import { useAuthStore } from '@/stores/auth-store'
import { useDatasetStore } from '@/stores/dataset-store'
import { useFavoriteStore } from '@/stores/favorite-store'
import { useReportStore } from '@/stores/report-store'
import { useWorkspaceStore } from '@/stores/workspace-store'

export function useDatasetStoreHydration() {
  return usePersistHydration(useDatasetStore.persist)
}

export function useReportStoreHydration() {
  return usePersistHydration(useReportStore.persist)
}

export function useFavoriteStoreHydration() {
  return usePersistHydration(useFavoriteStore.persist)
}

export function useWorkspaceStoreHydration() {
  return usePersistHydration(useWorkspaceStore.persist)
}

export function useDashboardHydration() {
  return usePersistHydrations(
    useDatasetStore.persist,
    useReportStore.persist,
    useFavoriteStore.persist,
  )
}

export function useDatasetSwitcherHydration() {
  return usePersistHydrations(
    useDatasetStore.persist,
    useWorkspaceStore.persist,
  )
}

/** Once per session after auth rehydrates, pull server favorites + datasets. */
export function useServerDataHydration() {
  const isLoaded = useAuthStore((s) => s.isLoaded)
  const token = useAuthStore((s) => s.accessToken)
  const ran = useRef(false)

  useEffect(() => {
    if (!isLoaded || !token || ran.current) return
    ran.current = true
    void hydrateUserDataFromServer()
  }, [isLoaded, token])
}