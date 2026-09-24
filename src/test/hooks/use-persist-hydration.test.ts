import { describe, expect, it } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  usePersistHydration,
  usePersistHydrations,
  type PersistApi,
} from '../../hooks/use-persist-hydration'

function makePersistApi(initialHydrated = false): PersistApi & {
  hydrated: boolean
  listeners: Set<() => void>
  hydrate: () => void
} {
  let hydrated = initialHydrated
  const listeners = new Set<() => void>()
  return {
    get hydrated() {
      return hydrated
    },
    hasHydrated: () => hydrated,
    onFinishHydration: (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    hydrate: () => {
      hydrated = true
      listeners.forEach((cb) => cb())
    },
    listeners,
  }
}

describe('usePersistHydration', () => {
  it('is true immediately when the api is already hydrated', () => {
    const { result } = renderHook(() =>
      usePersistHydration(makePersistApi(true)),
    )
    expect(result.current).toBe(true)
  })

  it('turns true after the api finishes hydrating', async () => {
    const api = makePersistApi(false)
    const { result } = renderHook(() => usePersistHydration(api))
    expect(result.current).toBe(false)

    act(() => api.hydrate())
    expect(result.current).toBe(true)
  })

  it('unsubscribes from the api on finish hydration', () => {
    const api = makePersistApi(false)
    const { unmount } = renderHook(() => usePersistHydration(api))
    expect(api.listeners.size).toBe(1)
    unmount()
    expect(api.listeners.size).toBe(0)
  })
})

describe('usePersistHydrations', () => {
  it('is true when all apis are hydrated', () => {
    const { result } = renderHook(() =>
      usePersistHydrations(makePersistApi(true), makePersistApi(true)),
    )
    expect(result.current).toBe(true)
  })

  it('waits for every api to hydrate before turning true', async () => {
    const a = makePersistApi(false)
    const b = makePersistApi(false)
    const { result } = renderHook(() => usePersistHydrations(a, b))
    expect(result.current).toBe(false)

    act(() => a.hydrate())
    expect(result.current).toBe(false)

    act(() => b.hydrate())
    expect(result.current).toBe(true)
  })

  it('unsubscribes from every api on unmount', () => {
    const a = makePersistApi(false)
    const b = makePersistApi(false)
    const { unmount } = renderHook(() => usePersistHydrations(a, b))
    expect(a.listeners.size).toBe(1)
    expect(b.listeners.size).toBe(1)
    unmount()
    expect(a.listeners.size).toBe(0)
    expect(b.listeners.size).toBe(0)
  })
})