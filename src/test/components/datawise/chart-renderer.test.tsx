import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import React from 'react'
import { ChartRenderer } from '../../../components/datawise/chart-renderer'
import type { ChartDataItem } from '../../../types/artifacts'

vi.mock('recharts', () => {
  const stub = (name: string) => {
    const Cmp = (props: Record<string, unknown>) => {
      const { children, ...rest } = props
      const attrs: Record<string, unknown> = {}
      for (const key of ['dataKey', 'name', 'type', 'fill', 'xAxisLabel', 'yAxisLabel']) {
        if (key in rest) attrs[`data-${key}`] = String(rest[key] ?? '')
      }
      if ('data' in rest && Array.isArray(rest.data)) {
        attrs['data-count'] = String(rest.data.length)
      }
      return React.createElement(
        'div',
        { 'data-testid': `rc-${name}`, ...attrs },
        children as React.ReactNode,
      )
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

const baseChart = (partial: Partial<ChartDataItem>): ChartDataItem => ({
  id: 1,
  type: 'bar',
  title: 'Sales by region',
  labels: ['North', 'South'],
  datasets: [{ label: 'Revenue', data: [10, 20] }],
  ...partial,
})

describe('ChartRenderer', () => {
  it('renders an invalid-data placeholder without a type', () => {
    render(<ChartRenderer chart={{ id: 1, title: 'Broken' } as ChartDataItem} />)
    expect(screen.getByText('Invalid chart data')).toBeInTheDocument()
  })

  it('renders a bar chart with its title and type badge', () => {
    render(<ChartRenderer chart={baseChart({})} />)
    expect(screen.getByText('Sales by region')).toBeInTheDocument()
    expect(screen.getByTestId('rc-BarChart')).toBeInTheDocument()
    expect(screen.getByTestId('rc-XAxis')).toHaveAttribute('data-dataKey', 'label')
    expect(screen.getByTestId('rc-Bar')).toHaveAttribute(
      'data-dataKey',
      'series_0',
    )
  })

  it('renders a line chart variant when the type is line', () => {
    render(<ChartRenderer chart={baseChart({ type: 'line' })} />)
    expect(screen.getByTestId('rc-LineChart')).toBeInTheDocument()
    expect(screen.getByTestId('rc-Line')).toHaveAttribute(
      'data-dataKey',
      'series_0',
    )
    expect(screen.queryByTestId('rc-BarChart')).not.toBeInTheDocument()
  })

  it('renders a scatter chart for the scatter type', () => {
    render(
      <ChartRenderer
        chart={baseChart({
          type: 'scatter',
          labels: [1, 2, 3],
          datasets: [{ label: 'pts', data: [5, 6, 7] }],
        })}
      />,
    )
    const scatter = screen.getByTestId('rc-ScatterChart')
    expect(scatter).toBeInTheDocument()
    expect(screen.getByTestId('rc-Scatter')).toHaveAttribute('data-count', '3')
  })

  it('renders a pie chart for the pie type', () => {
    render(<ChartRenderer chart={baseChart({ type: 'pie' })} />)
    expect(screen.getByTestId('rc-PieChart')).toBeInTheDocument()
    expect(screen.getByTestId('rc-Pie')).toBeInTheDocument()
  })

  it('renders a box plot with an svg and shows details on hover', () => {
    const chart = baseChart({
      type: 'boxplot',
      options: {
        boxplot: [
          {
            label: 'A',
            min: 1,
            q1: 2,
            median: 3,
            q3: 4,
            max: 5,
            outliers: [9],
          },
        ],
      },
    })
    const { container } = render(<ChartRenderer chart={chart} />)
    const svg = container.querySelector('[aria-label="Sales by region box plot"]')
    expect(svg).not.toBeNull()

    const box = container.querySelector('g rect') as SVGRectElement
    act(() => {
      fireEvent.mouseOver(box)
    })
    expect(screen.getByText('Median: 3')).toBeInTheDocument()
    expect(screen.getByText('Outliers: 1')).toBeInTheDocument()
  })

  it('shows a placeholder when there is no box plot data', () => {
    render(
      <ChartRenderer
        chart={baseChart({ type: 'boxplot', options: {}, datasets: [] })}
      />,
    )
    expect(screen.getByText('No box plot data available.')).toBeInTheDocument()
  })

  it('renders a heatmap and shows a tooltip on hover', () => {
    const chart = baseChart({
      type: 'heatmap',
      options: {
        heatmap: {
          x: ['a', 'b'],
          y: ['p', 'q'],
          z: [[1, 2], [3, 4]],
        },
      },
    })
    const { container } = render(<ChartRenderer chart={chart} />)
    const svg = container.querySelector('[aria-label="Sales by region heatmap"]')
    expect(svg).not.toBeNull()

    const firstCell = container.querySelector('g rect') as SVGRectElement
    act(() => {
      fireEvent.mouseOver(firstCell)
    })
    expect(screen.getByText('a:', { exact: false })).toBeInTheDocument()
  })

  it('shows a placeholder when there is no heatmap data', () => {
    render(
      <ChartRenderer
        chart={baseChart({ type: 'heatmap', options: {}, datasets: [] })}
      />,
    )
    expect(screen.getByText('No heatmap data available.')).toBeInTheDocument()
  })

  it('opens a fullscreen dialog and closes with Escape', () => {
    render(<ChartRenderer chart={baseChart({})} />)
    const expand = screen.getByRole('button', {
      name: 'Expand Sales by region fullscreen',
    })
    act(() => {
      expand.click()
    })
    const dialog = screen.getByRole('dialog', {
      name: 'Sales by region (Fullscreen)',
    })
    expect(dialog).toBeInTheDocument()

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    })
    expect(
      screen.queryByRole('dialog', { name: 'Sales by region (Fullscreen)' }),
    ).not.toBeInTheDocument()
  })
})