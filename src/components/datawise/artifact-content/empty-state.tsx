'use client'

import { BarChart3 } from 'lucide-react'
import { EmptyState } from '@/components/datawise/empty-state'
import { cn } from '@/lib/utils'

interface ArtifactEmptyStateProps {
  tab: string
  className?: string
}

export function ArtifactEmptyState({ tab, className }: ArtifactEmptyStateProps) {
  return (
    <EmptyState
      variant="activity"
      title={`No ${tab.toLowerCase()} yet`}
      description="Upload a dataset or select one from the top bar to preview analysis artifacts here."
      icon={BarChart3}
      className={cn('flex-1 border-0 bg-transparent py-12', className)}
    />
  )
}