import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RevenueChart } from '../../../components/datawise/revenue-chart'

vi.mock('recharts', () => {
  const passthrough = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  )
  return {
    ResponsiveContainer: passthrough,
    LineChart: ({ data }: { data: unknown[] }) => (
      <div data-testid="line-chart">{data.length + ''}</div>
    ),
    CartesianGrid: () => <div />,
    XAxis: () => <div />,
    YAxis: () => <div />,
    Tooltip: () => <div />,
    Legend: () => <div />,
    Line: () => <div />,
  }
})

describe('RevenueChart', () => {
  it('shows the placeholder when no data is provided', () => {
    render(<RevenueChart data={[]} />)
    expect(screen.getByText('No chart data available.')).toBeInTheDocument()
    expect(screen.queryByTestId('line-chart')).not.toBeInTheDocument()
  })

  it('renders the line chart with the provided rows', () => {
    const data = [{ month: 'Jan', monthly: 100 }]
    render(<RevenueChart data={data} />)
    expect(screen.getByTestId('line-chart')).toBeInTheDocument()
  })
})