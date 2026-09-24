import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { createSafeStorage } from '@/lib/safe-storage'
import type { ChatMessage, ChatRole } from '@/types/chat'

export interface ChatStoreState {
  // Session-isolated messages: { [sessionId: string]: ChatMessage[] }
  messagesBySession: Record<string, ChatMessage[]>
  activeSessionId: string | null
  isSending: boolean
  error: string | null

  // Actions
  setActiveSession: (sessionId: string | null) => void
  addMessage: (
    sessionId: string,
    message: {
      role: ChatRole
      content: string
      id?: string
      createdAt?: number
    },
  ) => ChatMessage
  updateMessage: (
    sessionId: string,
    messageId: string,
    content: string,
  ) => void
  clearSessionMessages: (sessionId: string) => void
  clearAllMessages: () => void
  setSending: (isSending: boolean) => void
  setError: (error: string | null) => void
  clearError: () => void
  getMessages: (sessionId?: string | null) => ChatMessage[]
}

export const useChatStore = create<ChatStoreState>()(
  persist(
    (set, get) => ({
      messagesBySession: {},
      activeSessionId: null,
      isSending: false,
      error: null,

      setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

      addMessage: (sessionId, { role, content, id, createdAt }) => {
        const now = Date.now()
        const newMessage: ChatMessage = {
          id: id ?? `${now}-${Math.random().toString(36).slice(2, 7)}`,
          role,
          content,
          createdAt: createdAt ?? now,
        }

        set((state) => {
          const current = state.messagesBySession[sessionId] ?? []
          // Cap per-session history to avoid localStorage quota issues
          const next = [...current, newMessage].slice(-200)
          return {
            messagesBySession: {
              ...state.messagesBySession,
              [sessionId]: next,
            },
            error: null,
          }
        })

        return newMessage
      },

      updateMessage: (sessionId, messageId, content) =>
        set((state) => {
          const current = state.messagesBySession[sessionId] ?? []
          return {
            messagesBySession: {
              ...state.messagesBySession,
              [sessionId]: current.map((msg) =>
                msg.id === messageId ? { ...msg, content } : msg,
              ),
            },
          }
        }),

      clearSessionMessages: (sessionId) =>
        set((state) => {
          const updated = { ...state.messagesBySession }
          delete updated[sessionId]
          return { messagesBySession: updated }
        }),

      clearAllMessages: () => set({ messagesBySession: {}, error: null }),

      setSending: (isSending) => set({ isSending }),

      setError: (error) => set({ error, isSending: false }),

      clearError: () => set({ error: null }),

      getMessages: (sessionId) => {
        const targetId = sessionId ?? get().activeSessionId
        if (!targetId) return []
        return get().messagesBySession[targetId] ?? []
      },
    }),
    {
      name: 'datawise-chat',
      storage: createJSONStorage(() => createSafeStorage()),
      partialize: (state) => ({
        messagesBySession: state.messagesBySession,
        activeSessionId: state.activeSessionId,
      }),
    },
  ),
)
