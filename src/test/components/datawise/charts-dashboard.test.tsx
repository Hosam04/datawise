import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ChartsDashboard } from '../../../components/datawise/charts-dashboard'
import type { ChartDataItem } from '../../../types/artifacts'

vi.mock('recharts', () => {
  const React = require('react')
  const stub = (name: string) => {
    const Cmp = (props: { children?: unknown; data?: unknown }) => {
      const { children, data } = props
      const attrs: Record<string, unknown> = {}
      if ('data' in props && Array.isArray(data)) attrs['data-count'] = String(data.length)
      return React.createElement('div', { 'data-testid': `rc-${name}`, ...attrs }, children)
    }
    Cmp.displayName = name
    return Cmp
  }
  return {
    ResponsiveContainer: stub('ResponsiveContainer'),
    LineChart: stub('LineChart'),
    BarChart: stub('BarChart'),
    ScatterChart: stub('ScatterChart'),
    PieChart: stub('PieChart'),
    CartesianGrid: stub('CartesianGrid'),
    XAxis: stub('XAxis'),
    YAxis: stub('YAxis'),
    Tooltip: stub('Tooltip'),
    Legend: stub('Legend'),
    Cell: stub('Cell'),
    Line: stub('Line'),
    Bar: stub('Bar'),
    Scatter: stub('Scatter'),
    Pie: stub('Pie'),
  }
})

const chart = (id: number, type: ChartDataItem['type'], title: string): ChartDataItem => ({
  id,
  type,
  title,
  labels: ['a', 'b'],
  datasets: [{ label: 's', data: [1, 2] }],
})

describe('ChartsDashboard', () => {
  it('renders a skeleton while chartData is undefined', () => {
    const { container } = render(<ChartsDashboard chartData={undefined} />)
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('shows the empty state for an empty chart list', () => {
    render(<ChartsDashboard chartData={[]} />)
    expect(screen.getByText('No charts generated')).toBeInTheDocument()
    expect(
      screen.getByText('Upload a dataset to generate visualizations'),
    ).toBeInTheDocument()
  })

  it('renders charts, category filters, and the type legend', () => {
    render(
      <ChartsDashboard
        chartData={[chart(1, 'bar', 'Sales'), chart(2, 'line', 'Trend')]}
      />,
    )
    expect(screen.getByText('Sales')).toBeInTheDocument()
    expect(screen.getByText('Trend')).toBeInTheDocument()
    expect(screen.getByText('All Charts')).toBeInTheDocument()
    expect(screen.getByText('Comparisons')).toBeInTheDocument()
    expect(screen.getByText('Trends')).toBeInTheDocument()
    // The type label appears both in the legend and on each chart badge.
    expect(screen.getAllByText('Bar').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Line').length).toBeGreaterThanOrEqual(1)
  })

  it('filters charts by category', () => {
    render(
      <ChartsDashboard
        chartData={[chart(1, 'bar', 'Sales'), chart(2, 'line', 'Trend')]}
      />,
    )
    fireEvent.click(screen.getByText('Trends'))
    expect(screen.getByText('Trend')).toBeInTheDocument()
    expect(screen.queryByText('Sales')).not.toBeInTheDocument()
  })

  it('shows the empty filter state when nothing matches', () => {
    render(
      <ChartsDashboard
        chartData={[chart(1, 'bar', 'Sales'), chart(2, 'pie', 'Mix')]}
      />,
    )
    fireEvent.click(screen.getByText('Distributions'))
    const search = screen.getByPlaceholderText('Search charts...')
    fireEvent.change(search, { target: { value: 'zzz' } })
    expect(
      screen.getByText('No charts in "Distributions"'),
    ).toBeInTheDocument()
  })

  it('filters charts by search query', () => {
    render(
      <ChartsDashboard
        chartData={[chart(1, 'bar', 'Sales'), chart(2, 'line', 'Churn')]}
      />,
    )
    const search = screen.getByPlaceholderText('Search charts...')
    fireEvent.change(search, { target: { value: 'churn' } })
    expect(screen.getByText('Churn')).toBeInTheDocument()
    expect(screen.queryByText('Sales')).not.toBeInTheDocument()
  })

  it('supports toggling the compact view', () => {
    render(<ChartsDashboard chartData={[chart(1, 'bar', 'Sales')]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Compact view' }))
    fireEvent.click(screen.getByRole('button', { name: 'Grid view' }))
    expect(screen.getByText('Sales')).toBeInTheDocument()
  })
})