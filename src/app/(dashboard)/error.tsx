'use client'

import { RouteError } from '@/components/datawise/route-error'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <RouteError
      error={error}
      reset={reset}
      title="Dashboard error"
      backHref="/"
      backLabel="Back to dashboard"
    />
  )
}
