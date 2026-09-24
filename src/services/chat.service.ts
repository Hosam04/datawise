import { authFetch, API_URL, errorMessage } from '@/lib/api'
import type { ChatResponse } from '@/lib/api'

export async function chatWithDataset(datasetId: string, message: string): Promise<ChatResponse> {
  if (!datasetId.trim()) throw new Error('A dataset session ID is required before chatting.')
  let response: Response
  try {
    response = await authFetch(`${API_URL}/datasets/${encodeURIComponent(datasetId)}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
  } catch (networkError: unknown) {
    const messageText = networkError instanceof Error ? networkError.message : 'Unknown network failure'
    throw new Error(`Network error: ${messageText}. Is the backend running at ${API_URL}?`)
  }
  if (!response.ok) throw new Error(await errorMessage(response, 'Failed to send message'))
  const data = await response.json()
  console.log('CHAT RESPONSE:', data)
  return data
}