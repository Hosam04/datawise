import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import DashboardPage from '../../../app/(dashboard)/page'
import { useDatasetStore } from '../../../stores/dataset-store'
import { useReportStore } from '../../../stores/report-store'
import { useFavoriteStore } from '../../../stores/favorite-store'

vi.mock('@/hooks/use-store-hydration', () => ({
  useDashboardHydration: () => true,
}))

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('@/components/dashboard/stat-card', () => ({
  StatCard: ({ label, value }: { label: string; value: number }) => (
    <div data-testid="stat-card">{label}: {value}</div>
  ),
}))

vi.mock('@/components/datawise/page-header', () => ({
  PageHeader: () => <header />,
}))

describe('DashboardPage', () => {
  beforeEach(() => {
    useDatasetStore.setState({ datasets: [] })
    useReportStore.setState({ reports: [] })
    useFavoriteStore.setState({ favorites: [] })
  })

  async function renderPage() {
    render(<DashboardPage />)
    await act(async () => {})
  }

  it('renders the stat cards with counts', async () => {
    useDatasetStore.setState({
      datasets: [
        { id: 'd1', name: 'a.csv', size: '1', type: 'CSV', status: 'Analyzed' },
      ],
    })
    await renderPage()
    const cards = screen.getAllByTestId('stat-card')
    expect(cards).toHaveLength(3)
    expect(cards[0]).toHaveTextContent('Datasets: 1')
    expect(cards[1]).toHaveTextContent('Reports: 0')
    expect(cards[2]).toHaveTextContent('Favorites: 0')
  })

  it('renders the quick actions card', async () => {
    await renderPage()
    expect(screen.getByText('Quick actions')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Upload/ })).toHaveAttribute(
      'href',
      '/upload',
    )
    expect(
      screen.getByRole('link', { name: /Browse datasets/ }),
    ).toHaveAttribute('href', '/datasets')
  })
})