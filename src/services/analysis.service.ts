import {
  authFetch,
  API_URL,
  tryRefreshAccessToken,
  errorMessage,
  isAnalysisResult,
  getResponseDetail,
  type AnalysisResult,
  type AnalysisStatus,
} from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'
import type { DatasetArtifacts } from '@/types/artifacts'

export async function analyzeData(
  file: File,
  query = 'Analyze this dataset',
  onUploadProgress?: (progress: number) => void,
): Promise<AnalysisResult> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${API_URL}/analyze-data/?query=${encodeURIComponent(query)}`)
    request.responseType = 'json'

    const token = useAuthStore.getState().accessToken
    if (token) {
      request.setRequestHeader('Authorization', `Bearer ${token}`)
    }

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onUploadProgress?.(Math.round((event.loaded / event.total) * 100))
    }
    request.onerror = () => reject(new Error(`Network error. Is the backend running at ${API_URL}?`))
    request.onload = async () => {
      if (request.status === 401) {
        const newToken = await tryRefreshAccessToken()
        if (newToken) {
          const retry = new XMLHttpRequest()
          retry.open('POST', `${API_URL}/analyze-data/?query=${encodeURIComponent(query)}`)
          retry.responseType = 'json'
          retry.setRequestHeader('Authorization', `Bearer ${newToken}`)
          retry.upload.onprogress = request.upload.onprogress
          retry.onerror = request.onerror
          retry.onload = () => {
            const response = retry.response as unknown
            if (retry.status >= 200 && retry.status < 300 && isAnalysisResult(response)) {
              resolve(response)
              return
            }
            const detail = getResponseDetail(response)
            reject(new Error(detail ?? 'Failed to upload dataset'))
          }
          const formData = new FormData()
          formData.append('file', file)
          retry.send(formData)
          return
        }
      }

      const response = request.response as unknown
      if (request.status >= 200 && request.status < 300 && isAnalysisResult(response)) {
        resolve(response)
        return
      }
      const detail = getResponseDetail(response)
      reject(new Error(detail ?? 'Failed to upload dataset'))
    }
    const formData = new FormData()
    formData.append('file', file)
    request.send(formData)
  })
}

export async function getAnalysisStatus(sessionId: string): Promise<AnalysisStatus> {
  const response = await authFetch(`${API_URL}/status/${sessionId}`)
  if (!response.ok) throw new Error(await errorMessage(response, 'Failed to get analysis status'))
  return response.json() as Promise<AnalysisStatus>
}

export async function getDatasetArtifacts(datasetId: string): Promise<DatasetArtifacts> {
  const response = await authFetch(`${API_URL}/datasets/${datasetId}/artifacts`)
  if (!response.ok) throw new Error(await errorMessage(response, 'Failed to fetch artifacts'))
  return response.json() as Promise<DatasetArtifacts>
}

export async function getInsights(sessionId: string) {
  const response = await authFetch(
    `${API_URL}/datasets/${sessionId}/insights`,
  )

  if (!response.ok) {
    throw new Error('Failed to fetch insights')
  }

  const text = await response.json()

  return text
}