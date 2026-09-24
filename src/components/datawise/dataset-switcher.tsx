'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { ChevronDown, FileSpreadsheet } from 'lucide-react'
import { chatHref } from '@/lib/app-links'
import { cn } from '@/lib/utils'
import { DatasetSwitcherSkeleton } from '@/components/datawise/card-skeleton'
import { useDatasetSwitcherHydration } from '@/hooks/use-store-hydration'
import { useDatasetStore } from '@/stores/dataset-store'
import { useWorkspaceStore } from '@/stores/workspace-store'

export function DatasetSwitcher() {
  const hydrated = useDatasetSwitcherHydration()
  const [hasMounted, setHasMounted] = useState(false)
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const datasets = useDatasetStore((state) => state.datasets)
  const openDatasetIds = useWorkspaceStore((state) => state.openDatasetIds)
  const activeDatasetId = useWorkspaceStore((state) => state.activeDatasetId)
  const openDataset = useWorkspaceStore((state) => state.openDataset)
  const setActiveDataset = useWorkspaceStore((state) => state.setActiveDataset)
  const removeOpenDataset = useWorkspaceStore((state) => state.removeOpenDataset)

  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setHasMounted(true)
  }, [])

  const openDatasets = useMemo(
    () =>
      openDatasetIds
        .map((id) => datasets.find((dataset) => dataset.id === id))
        .filter((dataset): dataset is NonNullable<typeof dataset> =>
          Boolean(dataset),
        ),
    [datasets, openDatasetIds],
  )

  const activeDataset =
    openDatasets.find((dataset) => dataset.id === activeDatasetId) ??
    openDatasets[openDatasets.length - 1] ??
    null

  useEffect(() => {
    const staleIds = openDatasetIds.filter(
      (id) => !datasets.some((dataset) => dataset.id === id),
    )

    staleIds.forEach((id) => removeOpenDataset(id))
  }, [datasets, openDatasetIds, removeOpenDataset])

  useEffect(() => {
    const datasetFromUrl =
      pathname.startsWith('/chat')
        ? searchParams.get('dataset')
        : pathname.startsWith('/datasets/')
          ? pathname.split('/')[2]
          : null

    if (datasetFromUrl && datasets.some((dataset) => dataset.id === datasetFromUrl)) {
      openDataset(datasetFromUrl)
    }
  }, [datasets, openDataset, pathname, searchParams])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (id: string) => {
    setActiveDataset(id)
    setOpen(false)
    router.push(chatHref(id))
  }

  if (!hasMounted) {
    return <DatasetSwitcherSkeleton />
  }

  if (openDatasets.length === 0) {
    return (
      <Link
        href="/datasets"
        className="block w-full truncate rounded-lg border border-dashed border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        Select a dataset
      </Link>
    )
  }

  const canSwitch = openDatasets.length > 1

  return (
    <div ref={containerRef} className="relative min-w-0 w-full">
      <button
        type="button"
        onClick={() => {
          if (canSwitch) {
            setOpen((current) => !current)
            return
          }

          if (activeDataset) {
            router.push(chatHref(activeDataset.id))
          }
        }}
        className={cn(
          'flex w-full max-w-full items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-muted sm:max-w-65',
        )}
        aria-haspopup={canSwitch ? 'listbox' : undefined}
        aria-expanded={canSwitch ? open : undefined}
      >
        <FileSpreadsheet className="size-4 shrink-0 text-primary" />
        <span className="truncate">{activeDataset?.name ?? 'Select a dataset'}</span>
        {canSwitch && (
          <ChevronDown
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-180',
            )}
          />
        )}
      </button>

      {canSwitch && open && (
        <div
          role="listbox"
          className="absolute top-full left-0 z-50 mt-2 min-w-65 overflow-hidden rounded-xl border border-border bg-card p-1 shadow-lg"
        >
          {openDatasets.map((dataset) => {
            const isActive = dataset.id === activeDataset?.id

            return (
              <button
                key={dataset.id}
                type="button"
                role="option"
                aria-selected={isActive}
                onClick={() => handleSelect(dataset.id)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-foreground hover:bg-muted',
                )}
              >
                <FileSpreadsheet className="size-4 shrink-0" />
                <span className="truncate">{dataset.name}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}