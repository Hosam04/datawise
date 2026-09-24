import { useEffect, useState } from 'react'

export interface PersistApi {
  hasHydrated: () => boolean
  onFinishHydration: (callback: () => void) => () => void
}

export function usePersistHydration(persistApi: PersistApi) {
  const [hydrated, setHydrated] = useState(() => persistApi.hasHydrated())

  useEffect(() => {
    if (hydrated) return

    return persistApi.onFinishHydration(() => {
      setHydrated(true)
    })
  }, [hydrated, persistApi])

  return hydrated
}

export function usePersistHydrations(...persistApis: PersistApi[]) {
  const [hydrated, setHydrated] = useState(() =>
    persistApis.every((api) => api.hasHydrated()),
  )

  useEffect(() => {
    if (hydrated) return

    const checkAll = () => persistApis.every((api) => api.hasHydrated())

    if (checkAll()) {
      const frame = window.requestAnimationFrame(() => setHydrated(true))
      return () => window.cancelAnimationFrame(frame)
    }

    const unsubscribers = persistApis.map((api) =>
      api.onFinishHydration(() => {
        if (checkAll()) {
          setHydrated(true)
        }
      }),
    )

    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe())
    }
  }, [hydrated, persistApis])

  return hydrated
}
