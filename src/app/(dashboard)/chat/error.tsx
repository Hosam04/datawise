'use client'

import { RouteError } from '@/components/datawise/route-error'

export default function ChatError({
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
      title="Chat error"
      description="Something went wrong while loading the chat workspace. Your messages are saved locally."
      backHref="/"
      backLabel="Back to dashboard"
    />
  )
}
