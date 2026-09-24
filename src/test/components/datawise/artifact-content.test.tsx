import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  ArtifactEmptyState,
  InsightsContent,
  FormattedMarkdown,
  InsightsReportContent,
  DatasetStatisticsView,
  StatisticsContent,
  PreviewContent,
  ReportContent,
} from '../../../components/datawise/artifact-content'

vi.mock('@/components/dashboard/stat-card', () => ({
  StatCard: ({ label, value }: { label: string; value: string }) => (
    <div data-testid="stat-card">
      {label}: {value}
    </div>
  ),
}))

describe('ArtifactEmptyState', () => {
  it('labels the empty state with the given tab', () => {
    render(<ArtifactEmptyState tab="Insights" />)
    expect(screen.getByText('No insights yet')).toBeInTheDocument()
  })
})

describe('InsightsContent', () => {
  it('renders each insight with its title and description', () => {
    render(
      <InsightsContent
        insights={[
          { id: '1', title: 'Growth', description: 'Up 20%', tone: 'positive' },
          { id: '2', title: 'Risk', description: 'Watch spend', tone: 'warning' },
          { id: '3', title: 'Note', description: 'Peaks in March', tone: 'neutral' },
        ]}
      />,
    )
    for (const title of ['Growth', 'Risk', 'Note']) {
      expect(screen.getByText(title)).toBeInTheDocument()
    }
    expect(screen.getByText('Up 20%')).toBeInTheDocument()
  })
})

describe('FormattedMarkdown', () => {
  it('renders headings, inline bold, code, emphasis, and lists', () => {
    render(
      <FormattedMarkdown
        content="# Revenue grew
**Sales** are strong and average `12.5` *stage*.
- Item one
- Item two
1. Steps
2. More"
      />,
    )
    expect(screen.getByRole('heading', { name: 'Revenue grew' })).toBeInTheDocument()
    expect(screen.getByText('Sales')).toBeInTheDocument()
    expect(screen.getByText('12.5')).toBeInTheDocument()
    expect(screen.getByText('stage')).toBeInTheDocument()
    expect(screen.getByText('Item one')).toBeInTheDocument()
    expect(screen.getByText('Steps')).toBeInTheDocument()
  })

  it('returns a fallback for non-string content', () => {
    render(<FormattedMarkdown content={null} />)
    expect(screen.queryByText(/Wait/i)).not.toBeInTheDocument()
  })
})

describe('InsightsReportContent', () => {
  it('shows the waiting placeholder when there is no content', () => {
    render(<InsightsReportContent insights={null} />)
    expect(screen.getByText('Waiting for insights...')).toBeInTheDocument()
  })

  it('renders the report sections with findings, recommendations, and quality', () => {
    render(
      <InsightsReportContent
        insights={{
          executive_summary: 'Sales **grew** across regions.',
          key_findings: [
            {
              title: 'Strong growth',
              confidence: 'high',
              description: 'Monthly revenue increased',
              evidence: { difference_percent: 12.345, p_value: 0.00123 },
            },
          ],
          recommendations: ['Focus on retention'],
          limitations: ['Sample limited to 2024'],
          significant_segments: [{ name: 'Enterprise', description: 'Top tier' }],
          data_quality: { score: 85, issues: ['Missing values in region'] },
        }}
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'Executive Summary' }),
    ).toBeInTheDocument()
    expect(screen.getByText('grew')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Key Findings' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Strong growth')).toBeInTheDocument()
    expect(screen.getByText('high')).toBeInTheDocument()
    expect(screen.getByText('12.3%')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Recommendations' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Focus on retention')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Data Quality' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Missing values in region')).toBeInTheDocument()
  })
})

describe('DatasetStatisticsView', () => {
  it('shows the empty state when no statistics are provided', () => {
    render(<DatasetStatisticsView statistics={null} />)
    expect(
      screen.getByText('No numerical statistics available'),
    ).toBeInTheDocument()
  })

  it('renders the descriptive stats table as the default tab', () => {
    render(
      <DatasetStatisticsView
        statistics={{
          descriptive: {
            revenue: { mean: 100, median: 90, std: 10, min: 5, max: 500 },
          },
          correlations: null,
          outliers: null,
        }}
      />,
    )
    expect(screen.getByText('Descriptive (1)')).toBeInTheDocument()
    expect(screen.getByText('revenue')).toBeInTheDocument()
  })

  it('switches to the correlations tab', () => {
    const { container } = render(
      <DatasetStatisticsView
        statistics={{
          descriptive: {},
          correlations: {
            a: { a: 1, b: -0.5 },
            b: { a: -0.5, b: 1 },
          },
          outliers: null,
        }}
      />,
    )
    const buttons = container.querySelectorAll('button')
    fireEvent.click(Array.from(buttons).find((b) => b.textContent?.includes('Correlations'))!)
    expect(screen.getByText('Correlation Matrix')).toBeInTheDocument()
  })

  it('switches to the outliers tab', () => {
    const { container } = render(
      <DatasetStatisticsView
        statistics={{
          descriptive: {},
          correlations: null,
          outliers: { revenue: { count: 3, percentage: 4.5, note: 'High values' } },
        }}
      />,
    )
    const buttons = container.querySelectorAll('button')
    fireEvent.click(Array.from(buttons).find((b) => b.textContent?.includes('Outliers'))!)
    expect(screen.getByText('Detected Outliers')).toBeInTheDocument()
    expect(screen.getByText('High values')).toBeInTheDocument()
  })
})

describe('StatisticsContent', () => {
  it('renders a stat card per statistic', () => {
    render(
      <StatisticsContent
        statistics={[
          { label: 'Mean', value: '10', trend: 'up', change: '5%' },
        ]}
      />,
    )
    expect(screen.getByTestId('stat-card')).toHaveTextContent('Mean: 10')
  })
})

describe('PreviewContent', () => {
  it('renders column headers and cell values with row/column counts', () => {
    render(
      <PreviewContent
        columns={['name', 'amount']}
        rows={[{ name: 'Ada', amount: 100 }, { name: 'Grace', amount: 200 }]}
        meta={{
          rows: 2,
          columns: 2,
          fileSize: '4 KB',
          lastUpdated: 'Jun 1, 2025',
        }}
      />,
    )
    expect(screen.getByText('2 rows')).toBeInTheDocument()
    expect(screen.getByText('4 KB')).toBeInTheDocument()
    expect(screen.getByText('Ada')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('Grace')).toBeInTheDocument()
  })
})

describe('ReportContent', () => {
  it('renders the report title, summary, highlights, and recommendations', () => {
    render(
      <ReportContent
        report={{
          title: 'Annual Report',
          generatedAt: 'Jun 1',
          summary: 'A good year.',
          highlights: ['Revenue up'],
          recommendations: ['Invest more'],
        }}
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'Annual Report' }),
    ).toBeInTheDocument()
    expect(screen.getByText('A good year.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Key Highlights' })).toBeInTheDocument()
    expect(screen.getByText('Revenue up')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Recommendations' })).toBeInTheDocument()
    expect(screen.getByText('Invest more')).toBeInTheDocument()
  })
})