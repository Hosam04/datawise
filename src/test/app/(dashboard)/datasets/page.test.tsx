import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import DatasetsPage from '../../../../app/(dashboard)/datasets/page'
import { useDatasetStore } from '../../../../stores/dataset-store'

vi.mock('@/components/datasets/dataset-card', () => {
  const DatasetCard = ({ id, name }: { id: string; name: string }) => (
    <div data-testid="dataset-card">{name}({id})</div>
  )
  return { __esModule: true, default: DatasetCard, DatasetCard }
})
vi.mock('@/components/datawise/animated-list', () => ({
  AnimatedList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}))
vi.mock('@/components/datawise/list-toolbar', () => ({
  ListToolbar: ({
    search,
    onSearchChange,
    filterOptions,
    filter,
    onFilterChange,
  }: {
    search: string
    onSearchChange: (v: string) => void
    filterOptions: { value: string; label: string }[]
    filter: string
    onFilterChange: (v: string) => void
  }) => (
    <div>
      <input
        aria-label="search"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
      />
      <select
        aria-label="status"
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
      >
        {filterOptions.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  ),
}))
vi.mock('@/components/datawise/empty-state', () => ({
  EmptyState: () => <div data-testid="empty" />,
}))
vi.mock('@/components/datawise/page-header', () => ({
  PageHeader: () => <header />,
}))

const dataset = {
  id: 'd1',
  name: 'sales.csv',
  size: '10 KB',
  type: 'CSV' as const,
  status: 'Analyzed' as const,
  uploadedAt: '2025-06-01T10:00:00Z',
}

describe('DatasetsPage', () => {
  beforeEach(() => {
    useDatasetStore.setState({ datasets: [] })
  })

  async function renderPage() {
    render(<DatasetsPage />)
    await act(async () => {})
  }

  it('shows the empty state when there are no datasets', async () => {
    await renderPage()
    expect(screen.getByTestId('empty')).toBeInTheDocument()
  })

  it('lists all datasets after mount', async () => {
    useDatasetStore.setState({ datasets: [dataset] })
    await renderPage()
    expect(screen.getByTestId('dataset-card')).toHaveTextContent('sales.csv(d1)')
  })

  it('filters datasets by search query', async () => {
    useDatasetStore.setState({
      datasets: [dataset, { ...dataset, id: 'd2', name: 'billing.csv' }],
    })
    await renderPage()
    fireEvent.change(screen.getByLabelText('search'), {
      target: { value: 'sales' },
    })
    expect(screen.getByTestId('dataset-card')).toHaveTextContent('sales.csv(d1)')
    expect(screen.queryByText('billing.csv(d2)')).not.toBeInTheDocument()
  })

  it('shifts to the search empty state when nothing matches', async () => {
    useDatasetStore.setState({ datasets: [dataset] })
    await renderPage()
    expect(screen.queryAllByTestId('empty')).toHaveLength(0)
    fireEvent.change(screen.getByLabelText('search'), {
      target: { value: 'zzz' },
    })
    expect(screen.getByTestId('empty')).toBeInTheDocument()
  })
})