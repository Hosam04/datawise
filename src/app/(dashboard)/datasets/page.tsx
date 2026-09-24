'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useDatasetStore } from '@/stores/dataset-store'
import DatasetCard from '@/components/datasets/dataset-card'
import { AnimatedList } from '@/components/datawise/animated-list'
import { ListCardSkeletonGroup, ListToolbarSkeleton } from '@/components/datawise/card-skeleton'
import { EmptyState } from '@/components/datawise/empty-state'
import { ListToolbar } from '@/components/datawise/list-toolbar'
import { PageHeader } from '@/components/datawise/page-header'
import { sortDatasets, type DatasetSort } from '@/lib/sort-utils'
import { hydrateUserDataFromServer } from '@/lib/hydrate-user-data'
import { useAuthStore } from '@/stores/auth-store'
import { useDatasetStoreHydration } from '@/hooks/use-store-hydration'

type DatasetCardProps = {
  id: string
  name: string
  size: string
  status: string
  uploadedAt?: string
}

const TypedDatasetCard = DatasetCard as unknown as React.ComponentType<DatasetCardProps>

const datasetSortOptions = [
  { value: 'date-desc', label: 'Date (newest)' },
  { value: 'date-asc', label: 'Date (oldest)' },
  { value: 'name-asc', label: 'Name (A-Z)' },
  { value: 'name-desc', label: 'Name (Z-A)' },
  { value: 'size-desc', label: 'Size (largest)' },
  { value: 'size-asc', label: 'Size (smallest)' },
]

export default function DatasetsPage() {
  const [mounted, setMounted] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const hydrated = useDatasetStoreHydration()
  const datasets = useDatasetStore((state) => state.datasets)
  const token = useAuthStore((s) => s.accessToken)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState<DatasetSort>('date-desc')

  const refreshFromServer = useCallback(async () => {
    if (!token) return
    setRefreshing(true)
    try {
      await hydrateUserDataFromServer()
    } finally {
      setRefreshing(false)
    }
  }, [token])

  useEffect(() => {
    setMounted(true)
  }, [])

  // Always re-sync datasets when entering this page (fixes empty list after login / refresh)
  useEffect(() => {
    if (!mounted || !hydrated || !token) return
    void refreshFromServer()
  }, [mounted, hydrated, token, refreshFromServer])

  const statusOptions = useMemo(() => {
    const statuses = [...new Set(datasets.map((dataset) => dataset.status))]
    return [
      { value: 'all', label: 'All' },
      ...statuses.map((status) => ({ value: status, label: status })),
    ]
  }, [datasets])

  const filteredDatasets = useMemo(() => {
    const query = search.trim().toLowerCase()
    const filtered = datasets.filter((dataset) => {
      const matchesSearch =
        query.length === 0 || dataset.name.toLowerCase().includes(query)
      const matchesStatus =
        statusFilter === 'all' || dataset.status === statusFilter
      return matchesSearch && matchesStatus
    })
    return sortDatasets(filtered, sort)
  }, [datasets, search, statusFilter, sort])

  const hasActiveControls =
    search.trim().length > 0 || statusFilter !== 'all' || sort !== 'date-desc'

  const clearFilters = () => {
    setSearch('')
    setStatusFilter('all')
    setSort('date-desc')
  }

  // Avoid hydration mismatch: show skeleton until client + store are ready
  if (!mounted || !hydrated) {
    return (
      <div className="space-y-6 p-6">
        <PageHeader
          title="Datasets"
          description="Manage your uploaded datasets."
        />
        <ListToolbarSkeleton />
        <ListCardSkeletonGroup count={4} />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Datasets"
        description="Manage your uploaded datasets."
      />

      {datasets.length > 0 && (
        <ListToolbar
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search by name..."
          filter={statusFilter}
          onFilterChange={setStatusFilter}
          filterOptions={statusOptions}
          filterLabel="Status"
          sort={sort}
          onSortChange={(value) => setSort(value as DatasetSort)}
          sortOptions={datasetSortOptions}
        />
      )}

      {refreshing && datasets.length === 0 ? (
        <ListCardSkeletonGroup count={4} />
      ) : datasets.length === 0 ? (
        <EmptyState variant="datasets" />
      ) : filteredDatasets.length === 0 ? (
        <EmptyState
          variant="search"
          primaryAction={{
            label: 'Clear filters',
            href: '#',
            onClick: clearFilters,
          }}
        />
      ) : (
        <AnimatedList>
          {filteredDatasets.map((dataset) => (
            <TypedDatasetCard
              key={dataset.id}
              id={dataset.id}
              name={dataset.name}
              size={dataset.size}
              status={dataset.status}
              uploadedAt={dataset.uploadedAt}
            />
          ))}
        </AnimatedList>
      )}

      {hasActiveControls && filteredDatasets.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Showing {filteredDatasets.length} of {datasets.length} datasets
        </p>
      )}
    </div>
  )
}