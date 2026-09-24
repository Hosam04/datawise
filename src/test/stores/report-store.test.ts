import { beforeEach, describe, expect, it } from 'vitest'
import { useReportStore } from '../../stores/report-store'

const REPORT_A = {
  id: 'r1',
  title: 'Alpha report',
  dataset: 'sales.csv',
  type: 'summary',
  date: 'Jan 1, 2025',
  createdAt: '2025-01-01T00:00:00Z',
}

const REPORT_B = {
  id: 'r2',
  title: 'Beta report',
  dataset: 'sales.csv',
  type: 'detailed',
  date: 'Feb 1, 2025',
}

beforeEach(() => {
  useReportStore.setState({ reports: [] })
  localStorage.clear()
})

describe('report-store', () => {
  it('starts with no reports', () => {
    expect(useReportStore.getState().reports).toEqual([])
  })

  it('addReport appends and dedupes by id', () => {
    const { addReport } = useReportStore.getState()
    addReport(REPORT_A)
    addReport(REPORT_B)
    addReport(REPORT_A)
    expect(useReportStore.getState().reports.map((r) => r.id)).toEqual([
      'r1',
      'r2',
    ])
  })

  it('removeReport filters by id', () => {
    const { addReport, removeReport } = useReportStore.getState()
    addReport(REPORT_A)
    addReport(REPORT_B)
    removeReport('r1')
    expect(useReportStore.getState().reports.map((r) => r.id)).toEqual(['r2'])
  })

  it('persists reports to localStorage', () => {
    const { addReport } = useReportStore.getState()
    addReport(REPORT_A)
    const persisted = JSON.parse(
      localStorage.getItem('datawise-reports') ?? '{}',
    )
    expect(persisted.state.reports).toEqual([REPORT_A])
  })
})