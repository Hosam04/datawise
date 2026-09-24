import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatPage from '../../../../app/(dashboard)/chat/page'

vi.mock('@/components/datawise/artifact-panel', () => ({
  ArtifactPanel: () => <div data-testid="artifact-panel" />,
}))
vi.mock('@/components/datawise/chat-panel', () => ({
  ChatPanel: () => <div data-testid="chat-panel" />,
}))

describe('ChatPage', () => {
  it('renders the chat and artifact panels', () => {
    render(<ChatPage />)
    expect(screen.getByTestId('chat-panel')).toBeTruthy()
    expect(screen.getByTestId('artifact-panel')).toBeTruthy()
  })
})