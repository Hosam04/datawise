export type ChatRole = 'user' | 'ai'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  createdAt: number
}

export interface ChatRequest {
  message: string
}

export interface ChatResponse {
  answer: string
  status: string
  session_id: string
}

export interface ChatSessionState {
  sessionId: string
  messages: ChatMessage[]
  isSending: boolean
  error?: string | null
}
