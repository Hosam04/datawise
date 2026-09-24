'use client'

import { RouteError } from '@/components/datawise/route-error'

export default function DatasetDetailError({
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
      title="Dataset error"
      description="Something went wrong while loading this dataset."
      backHref="/datasets"
      backLabel="Back to datasets"
    />
  )
}
