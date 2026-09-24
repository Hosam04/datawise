import { authFetch, assetUrl, errorMessage, filenameFromDisposition, type DownloadedFile } from '@/lib/api'

export async function fetchFile(
  path: string,
  fallbackFilename: string,
): Promise<DownloadedFile> {
  const response = await authFetch(assetUrl(path), {
    method: 'GET',
    cache: 'no-store',
  })
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to fetch file'))
  }

  const blob = await response.blob()
  const filename =
    filenameFromDisposition(response.headers.get('content-disposition')) ??
    fallbackFilename

  return { blob, filename }
}

export function saveDownloadedFile(file: DownloadedFile): void {
  const objectUrl = URL.createObjectURL(file.blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = file.filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()

  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export async function downloadFile(
  path: string,
  fallbackFilename: string,
): Promise<void> {
  const file = await fetchFile(path, fallbackFilename)
  saveDownloadedFile(file)
}

export async function downloadProcessedDataset(datasetId: string, fallbackFilename?: string): Promise<void> {
  const fallback = fallbackFilename || `${datasetId}_processed.csv`
  return downloadFile(`/datasets/${encodeURIComponent(datasetId)}/processed-dataset/download`, fallback)
}

export async function downloadReportFile(datasetId: string, fallbackFilename?: string): Promise<void> {
  const fallback = fallbackFilename || `${datasetId}_report.pdf`
  return downloadFile(`/datasets/${encodeURIComponent(datasetId)}/report/download`, fallback)
}

export { filenameFromDisposition }
export type { DownloadedFile }