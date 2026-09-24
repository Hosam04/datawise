import { authFetch, API_URL, errorMessage } from '@/lib/api'

export interface ServerReportDto {
  id: string
  title: string
  dataset?: string | null
  type?: string | null
  date?: string | null
  created_at?: string | null
  dataset_id?: string | null
  status?: string | null
}

export async function fetchMyReports(): Promise<ServerReportDto[]> {
  const response = await authFetch(`${API_URL}/me/reports`)
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to load reports'))
  }
  return (await response.json()) as ServerReportDto[]
}

export async function deleteReportApi(reportId: string): Promise<void> {
  const response = await authFetch(
    `${API_URL}/me/reports/${encodeURIComponent(reportId)}`,
    { method: 'DELETE' },
  )
  if (!response.ok && response.status !== 404) {
    throw new Error(await errorMessage(response, 'Failed to delete report'))
  }
}

export async function deleteAllReportsApi(): Promise<void> {
  const reports = await fetchMyReports()
  await Promise.all(reports.map((r) => deleteReportApi(r.id)))
}