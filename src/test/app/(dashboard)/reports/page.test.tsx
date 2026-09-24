import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import ReportsPage from '../../../../app/(dashboard)/reports/page'
import { useReportStore } from '../../../../stores/report-store'

vi.mock('@/components/reports/report-card', () => ({
  ReportCard: ({ id, title }: { id: string; title: string }) => (
    <div data-testid="report-card">{title}({id})</div>
  ),
}))
vi.mock('@/components/datawise/animated-list', () => ({
  AnimatedList: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
vi.mock('@/components/datawise/card-skeleton', () => ({
  ListCardSkeletonGroup: () => <div data-testid="skeleton" />,
  ListToolbarSkeleton: () => <div data-testid="toolbar-skeleton" />,
}))
vi.mock('@/components/datawise/empty-state', () => ({
  EmptyState: ({ variant }: { variant: string }) => <div data-testid={`empty-${variant}`} />,
}))
vi.mock('@/components/datawise/list-toolbar', () => ({
  ListToolbar: ({
    search,
    onSearchChange,
filter,
  onFilterChange,
  sort,
  onSortChange,
  filterOptions,
}: {
  search: string
  onSearchChange: (v: string) => void
  filter: string
  onFilterChange: (v: string) => void
  sort: string
  onSortChange: (v: string) => void
  filterOptions: { value: string; label: string }[]
}) => (
    <div>
      <input
        aria-label="search"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
      />
      <select
        aria-label="type"
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
      >
        {filterOptions.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <select
        aria-label="sort"
        value={sort}
        onChange={(e) => onSortChange(e.target.value)}
      >
        <option value="date-desc">Date (newest)</option>
        <option value="title-asc">Title (A-Z)</option>
      </select>
    </div>
  ),
}))
vi.mock('@/components/datawise/page-header', () => ({ PageHeader: () => <header /> }))
vi.mock('@/hooks/use-store-hydration', () => ({
  useReportStoreHydration: () => true,
}))

const report = (over: { id: string; title?: string; dataset?: string; date?: string; type?: string }) => ({
  id: over.id,
  title: over.title ?? 'Sales Report',
  dataset: over.dataset ?? 'sales.csv',
  date: over.date ?? 'x',
  type: over.type ?? 'Summary',
})

describe('ReportsPage', () => {
  beforeEach(() => {
    useReportStore.setState({ reports: [] })
  })

  it('shows the empty state when there are no reports', async () => {
    render(<ReportsPage />)
    await act(async () => {})
    expect(screen.getByTestId('empty-reports')).toBeInTheDocument()
  })

  it('renders a card for every report', async () => {
    useReportStore.setState({ reports: [report({ id: 'r1' }), report({ id: 'r2', title: 'Other' })] })
    render(<ReportsPage />)
    await act(async () => {})
    expect(screen.getAllByTestId('report-card')).toHaveLength(2)
  })

  it('filters reports by search and shows the search empty state', async () => {
    useReportStore.setState({ reports: [report({ id: 'r1' })] })
    render(<ReportsPage />)
    await act(async () => {})
    expect(screen.queryByTestId('empty-search')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('search'), { target: { value: 'zzz' } })
    expect(await screen.findByTestId('empty-search')).toBeInTheDocument()
  })

  it('filters reports by type', async () => {
    useReportStore.setState({
      reports: [report({ id: 'r1' }), report({ id: 'r2', title: 'Detail', type: 'Full' })],
    })
    render(<ReportsPage />)
    await act(async () => {})
    fireEvent.change(screen.getByLabelText('type'), { target: { value: 'Full' } })
    expect(screen.getByTestId('report-card')).toHaveTextContent('Detail(r2)')
    expect(screen.queryByText('Sales Report(r1)')).not.toBeInTheDocument()
  })

  it('sorts reports by title ascending', async () => {
    useReportStore.setState({
      reports: [report({ id: 'r1', title: 'Zebra' }), report({ id: 'r2', title: 'Alpha' })],
    })
    render(<ReportsPage />)
    await act(async () => {})
    fireEvent.change(screen.getByLabelText('sort'), { target: { value: 'title-asc' } })
    const cards = screen.getAllByTestId('report-card')
    expect(cards[0]).toHaveTextContent('Alpha(r2)')
    expect(cards[1]).toHaveTextContent('Zebra(r1)')
  })
})