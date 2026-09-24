import { describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import * as persistHydration from '../../hooks/use-persist-hydration'
import {
  useDatasetStoreHydration,
  useReportStoreHydration,
  useFavoriteStoreHydration,
  useWorkspaceStoreHydration,
  useDashboardHydration,
  useDatasetSwitcherHydration,
} from '../../hooks/use-store-hydration'
import { useDatasetStore } from '../../stores/dataset-store'
import { useReportStore } from '../../stores/report-store'
import { useFavoriteStore } from '../../stores/favorite-store'
import { useWorkspaceStore } from '../../stores/workspace-store'

vi.mock('@/hooks/use-persist-hydration', () => ({
  usePersistHydration: vi.fn(() => true),
  usePersistHydrations: vi.fn(() => true),
}))

const mocked = {
  usePersistHydration: vi.mocked(persistHydration.usePersistHydration),
  usePersistHydrations: vi.mocked(persistHydration.usePersistHydrations),
}

describe('useStoreHydration wiring', () => {
  it('individual hooks delegate to usePersistHydration with their persist API', () => {
    renderHook(() => useDatasetStoreHydration())
    renderHook(() => useReportStoreHydration())
    renderHook(() => useFavoriteStoreHydration())
    renderHook(() => useWorkspaceStoreHydration())

    expect(mocked.usePersistHydration).toHaveBeenCalledWith(
      useDatasetStore.persist,
    )
    expect(mocked.usePersistHydration).toHaveBeenCalledWith(
      useReportStore.persist,
    )
    expect(mocked.usePersistHydration).toHaveBeenCalledWith(
      useFavoriteStore.persist,
    )
    expect(mocked.usePersistHydration).toHaveBeenCalledWith(
      useWorkspaceStore.persist,
    )
  })

  it('useDashboardHydration waits on dataset, report, and favorite', () => {
    renderHook(() => useDashboardHydration())
    expect(mocked.usePersistHydrations).toHaveBeenCalledWith(
      useDatasetStore.persist,
      useReportStore.persist,
      useFavoriteStore.persist,
    )
  })

  it('useDatasetSwitcherHydration waits on dataset and workspace', () => {
    renderHook(() => useDatasetSwitcherHydration())
    expect(mocked.usePersistHydrations).toHaveBeenCalledWith(
      useDatasetStore.persist,
      useWorkspaceStore.persist,
    )
  })

  it('all wrappers return the delegated boolean', () => {
    const r1 = renderHook(() => useDatasetStoreHydration())
    expect(r1.result.current).toBe(true)
    const r2 = renderHook(() => useReportStoreHydration())
    expect(r2.result.current).toBe(true)
    const r3 = renderHook(() => useFavoriteStoreHydration())
    expect(r3.result.current).toBe(true)
    const r4 = renderHook(() => useWorkspaceStoreHydration())
    expect(r4.result.current).toBe(true)
    const r5 = renderHook(() => useDashboardHydration())
    expect(r5.result.current).toBe(true)
    const r6 = renderHook(() => useDatasetSwitcherHydration())
    expect(r6.result.current).toBe(true)
  })
})