import { authFetch, API_URL, errorMessage } from '@/lib/api'

export interface ServerDatasetDto {
  id: string
  dataset_uuid: string
  name: string
  original_filename: string
  size?: number | null
  type?: string | null
  rows?: number | null
  status: string
  uploaded_at?: string | null
  analysis_id?: string | null
}

export async function fetchMyDatasets(): Promise<ServerDatasetDto[]> {
  const response = await authFetch(`${API_URL}/me/datasets`)
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to load datasets'))
  }
  return (await response.json()) as ServerDatasetDto[]
}

export async function deleteDatasetApi(datasetId: string): Promise<void> {
  const response = await authFetch(
    `${API_URL}/me/datasets/${encodeURIComponent(datasetId)}`,
    { method: 'DELETE' },
  )
  if (!response.ok && response.status !== 404) {
    throw new Error(await errorMessage(response, 'Failed to delete dataset'))
  }
}

export async function deleteAllDatasetsApi(): Promise<void> {
  const datasets = await fetchMyDatasets()
  await Promise.all(datasets.map((d) => deleteDatasetApi(d.id)))
}