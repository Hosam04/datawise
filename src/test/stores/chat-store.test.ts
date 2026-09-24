import { beforeEach, describe, expect, it } from 'vitest'
import { useChatStore } from '../../stores/chat-store'

beforeEach(() => {
  useChatStore.setState({
    messagesBySession: {},
    activeSessionId: null,
    isSending: false,
    error: null,
  })
  localStorage.clear()
})

describe('chat-store session management', () => {
  it('starts with no sessions', () => {
    const s = useChatStore.getState()
    expect(s.messagesBySession).toEqual({})
    expect(s.activeSessionId).toBeNull()
    expect(s.isSending).toBe(false)
    expect(s.error).toBeNull()
  })

  it('setActiveSession switches the active session', () => {
    useChatStore.getState().setActiveSession('sess-1')
    expect(useChatStore.getState().activeSessionId).toBe('sess-1')
  })

  it('getMessages falls back to the active session', () => {
    const { addMessage, setActiveSession, getMessages } = useChatStore.getState()
    setActiveSession('sess-1')
    addMessage('sess-1', { role: 'user', content: 'hello' })
    expect(getMessages()).toHaveLength(1)
    expect(getMessages(null)).toHaveLength(1)
    expect(getMessages('sess-other')).toHaveLength(0)
  })

  it('getMessages returns [] when nothing is active', () => {
    expect(useChatStore.getState().getMessages()).toEqual([])
  })
})

describe('chat-store messages', () => {
  it('addMessage appends and returns the created message with defaults', () => {
    const { addMessage } = useChatStore.getState()
    const before = Date.now()
    const message = addMessage('sess-1', { role: 'user', content: 'hi' })
    expect(message.role).toBe('user')
    expect(message.content).toBe('hi')
    expect(message.id).toMatch(/^\d+-[a-z0-9]{5}$/)
    expect(message.createdAt).toBeGreaterThanOrEqual(before)

    const stored = useChatStore.getState().messagesBySession['sess-1']
    expect(stored).toHaveLength(1)
    expect(stored[0]).toEqual(message)
  })

  it('keeps a provided id and createdAt', () => {
    const message = useChatStore.getState().addMessage('sess-1', {
      role: 'assistant',
      content: 'answer',
      id: 'custom-1',
      createdAt: 123,
    })
    expect(message.id).toBe('custom-1')
    expect(message.createdAt).toBe(123)
  })

  it('addMessage clears any pending error', () => {
    useChatStore.getState().setError('previous failure')
    useChatStore.getState().addMessage('sess-1', { role: 'user', content: 'x' })
    expect(useChatStore.getState().error).toBeNull()
  })

  it('caps per-session history at 200 messages', () => {
    const { addMessage } = useChatStore.getState()
    for (let i = 0; i < 205; i += 1) {
      addMessage('sess-1', { role: 'user', content: `msg-${i}` })
    }
    const messages = useChatStore.getState().messagesBySession['sess-1']
    expect(messages).toHaveLength(200)
    expect(messages[0].content).toBe('msg-5')
  })

  it('updateMessage replaces content of a matching id only', () => {
    const { addMessage, updateMessage } = useChatStore.getState()
    addMessage('sess-1', { role: 'user', content: 'first', id: 'a' })
    addMessage('sess-1', { role: 'user', content: 'second', id: 'b' })

    updateMessage('sess-1', 'a', 'first-edited')
    const messages = useChatStore.getState().messagesBySession['sess-1']
    expect(messages.map((m) => m.content)).toEqual([
      'first-edited',
      'second',
    ])
  })

  it('clearSessionMessages removes only the given session', () => {
    const { addMessage, clearSessionMessages } = useChatStore.getState()
    addMessage('sess-1', { role: 'user', content: 'a' })
    addMessage('sess-2', { role: 'user', content: 'b' })
    clearSessionMessages('sess-1')
    expect(useChatStore.getState().messagesBySession).toEqual({
      'sess-2': [expect.any(Object)],
    })
  })

  it('clearAllMessages wipes all sessions and the error', () => {
    const { addMessage, setError, clearAllMessages } = useChatStore.getState()
    addMessage('sess-1', { role: 'user', content: 'a' })
    setError('boom')
    clearAllMessages()
    expect(useChatStore.getState().messagesBySession).toEqual({})
    expect(useChatStore.getState().error).toBeNull()
  })
})

describe('chat-store sending state', () => {
  it('setSending tracks in-flight requests', () => {
    useChatStore.getState().setSending(true)
    expect(useChatStore.getState().isSending).toBe(true)
    useChatStore.getState().setSending(false)
    expect(useChatStore.getState().isSending).toBe(false)
  })

  it('setError sets the error and stops sending', () => {
    useChatStore.getState().setSending(true)
    useChatStore.getState().setError('network down')
    expect(useChatStore.getState().isSending).toBe(false)
    expect(useChatStore.getState().error).toBe('network down')
  })

  it('clearError clears the error', () => {
    useChatStore.getState().setError('boom')
    useChatStore.getState().clearError()
    expect(useChatStore.getState().error).toBeNull()
  })
})

describe('chat-store persistence', () => {
  it('persists messages and active session but not flags', () => {
    useChatStore.getState().setActiveSession('sess-1')
    useChatStore.getState().addMessage('sess-1', { role: 'user', content: 'hi' })
    useChatStore.getState().setSending(true)

    const persisted = JSON.parse(localStorage.getItem('datawise-chat') ?? '{}')
    expect(persisted.state.messagesBySession['sess-1']).toHaveLength(1)
    expect(persisted.state.activeSessionId).toBe('sess-1')
    expect(persisted.state).not.toHaveProperty('isSending')
    expect(persisted.state).not.toHaveProperty('error')
  })
})