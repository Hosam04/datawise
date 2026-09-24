'use client'

import { useMemo, useState } from 'react'
import { ReportCard } from '@/components/reports/report-card'
import { AnimatedList } from '@/components/datawise/animated-list'
import { ListCardSkeletonGroup, ListToolbarSkeleton } from '@/components/datawise/card-skeleton'
import { EmptyState } from '@/components/datawise/empty-state'
import { ListToolbar } from '@/components/datawise/list-toolbar'
import { PageHeader } from '@/components/datawise/page-header'
import { useReportStoreHydration } from '@/hooks/use-store-hydration'
import { sortReports, type ReportSort } from '@/lib/sort-utils'
import { useReportStore } from '@/stores/report-store'

const reportSortOptions = [
  { value: 'date-desc', label: 'Date (newest)' },
  { value: 'date-asc', label: 'Date (oldest)' },
  { value: 'title-asc', label: 'Title (A-Z)' },
  { value: 'title-desc', label: 'Title (Z-A)' },
]

export default function ReportsPage() {
  const hydrated = useReportStoreHydration()
  const reports = useReportStore((state) => state.reports)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [sort, setSort] = useState<ReportSort>('date-desc')

  const typeOptions = useMemo(() => {
    const types = [...new Set(reports.map((report) => report.type))]

    return [
      { value: 'all', label: 'All' },
      ...types.map((type) => ({ value: type, label: type })),
    ]
  }, [reports])

  const filteredReports = useMemo(() => {
    const query = search.trim().toLowerCase()

    const filtered = reports.filter((report) => {
      const matchesSearch =
        query.length === 0 ||
        report.title.toLowerCase().includes(query) ||
        report.dataset.toLowerCase().includes(query)
      const matchesType = typeFilter === 'all' || report.type === typeFilter

      return matchesSearch && matchesType
    })

    return sortReports(filtered, sort)
  }, [reports, search, typeFilter, sort])

  const hasActiveControls =
    search.trim().length > 0 || typeFilter !== 'all' || sort !== 'date-desc'

  const clearFilters = () => {
    setSearch('')
    setTypeFilter('all')
    setSort('date-desc')
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Reports"
        description="Generated analysis reports."
      />

      {!hydrated ? (
        <>
          <ListToolbarSkeleton />
          <ListCardSkeletonGroup count={3} spacing="md" padding="md" />
        </>
      ) : (
        <>
          {reports.length > 0 && (
            <ListToolbar
              search={search}
              onSearchChange={setSearch}
              searchPlaceholder="Search by title or dataset..."
              filter={typeFilter}
              onFilterChange={setTypeFilter}
              filterOptions={typeOptions}
              filterLabel="Type"
              sort={sort}
              onSortChange={(value) => setSort(value as ReportSort)}
              sortOptions={reportSortOptions}
            />
          )}

          {reports.length === 0 ? (
            <EmptyState variant="reports" />
          ) : filteredReports.length === 0 ? (
            <EmptyState
              variant="search"
              primaryAction={{
                label: 'Clear filters',
                href: '#',
                onClick: clearFilters,
              }}
            />
          ) : (
            <AnimatedList className="space-y-4" itemClassName="">
              {filteredReports.map((report) => (
                <ReportCard
                  key={report.id}
                  id={report.id}
                  title={report.title}
                  dataset={report.dataset}
                  type={report.type}
                  date={report.date}
                />
              ))}
            </AnimatedList>
          )}

          {hasActiveControls && filteredReports.length > 0 && (
            <p className="text-sm text-muted-foreground">
              Showing {filteredReports.length} of {reports.length} reports
            </p>
          )}
        </>
      )}
    </div>
  )
}
