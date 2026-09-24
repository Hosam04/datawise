'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { ErrorFallback } from '@/components/datawise/error-fallback'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface RouteErrorProps {
  error: Error & { digest?: string }
  reset: () => void
  title: string
  description?: string
  backHref?: string
  backLabel?: string
}

export function RouteError({
  error,
  reset,
  title,
  description,
  backHref,
  backLabel,
}: RouteErrorProps) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="space-y-4 p-6 animate-in fade-in duration-300 motion-reduce:animate-none">
      <ErrorFallback
        title={title}
        description={
          description ||
          error.message ||
          'Something went wrong while loading this page.'
        }
        onReset={reset}
      />

      {backHref && backLabel && (
        <div className="flex justify-center">
          <Link href={backHref} className={cn(buttonVariants({ variant: 'outline' }))}>
            {backLabel}
          </Link>
        </div>
      )}
    </div>
  )
}
