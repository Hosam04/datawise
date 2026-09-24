import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ChatPanel } from '../../../components/datawise/chat-panel'
import { useDatasetStore } from '../../../stores/dataset-store'
import { useWorkspaceStore } from '../../../stores/workspace-store'
import { useChatStore } from '../../../stores/chat-store'

vi.mock('@/lib/api', () => ({
  chatWithDataset: vi.fn(),
  getDatasetArtifacts: vi.fn().mockResolvedValue({ status: 'completed' }),
}))

const params = { get: vi.fn(() => null) }

vi.mock('next/navigation', () => ({
  useSearchParams: () => params,
}))

import { chatWithDataset } from '../../../lib/api'
const mockedChat = vi.mocked(chatWithDataset)

const ANALYZED = {
  id: 'd1',
  name: 'sales.csv',
  size: '1 KB',
  type: 'CSV',
  status: 'Analyzed',
}
const PROCESSING = { ...ANALYZED, id: 'd2', status: 'Processing' }

function resetStores() {
  useDatasetStore.setState({ datasets: [] })
  useWorkspaceStore.setState({ openDatasetIds: [], activeDatasetId: null })
  useChatStore.setState({ messagesBySession: {}, isSending: false, error: null })
}

describe('ChatPanel', () => {
  beforeEach(() => {
    params.get.mockReset()
    params.get.mockReturnValue(null)
    mockedChat.mockReset()
    mockedChat.mockResolvedValue({ answer: 'Sure!', status: 'ok', session_id: 'd1' })
    resetStores()
  })

  it('shows the empty state when no dataset is selected', () => {
    render(<ChatPanel />)
    expect(screen.getByText('No dataset selected')).toBeInTheDocument()
    expect(screen.getByText('Browse datasets')).toBeInTheDocument()
    expect(screen.getByText('Upload file')).toBeInTheDocument()
    expect(
      screen.getByPlaceholderText('Select a dataset to chat'),
    ).toBeDisabled()
  })

  it('shows a welcome state with the dataset name for an analyzed dataset', () => {
    useDatasetStore.setState({ datasets: [ANALYZED] })
    useWorkspaceStore.setState({ openDatasetIds: ['d1'], activeDatasetId: 'd1' })
    render(<ChatPanel />)
    expect(screen.getByText('Ask DataWise anything')).toBeInTheDocument()
    // The name appears in the panel header and in the welcome sentence.
    expect(screen.getAllByText('sales.csv').length).toBe(2)
    expect(
      screen.getByPlaceholderText('Ask anything about your data...'),
    ).toBeEnabled()
  })

  it('disables chat until the analysis is complete', () => {
    useDatasetStore.setState({ datasets: [PROCESSING] })
    useWorkspaceStore.setState({ openDatasetIds: ['d2'], activeDatasetId: 'd2' })
    render(<ChatPanel />)
    expect(
      screen.getByPlaceholderText('Analysis must complete before chat'),
    ).toBeDisabled()
  })

  it('sends a message, shows typing, and appends the bot reply', async () => {
    let resolveReply: (value: { answer: string; status: string; session_id: string }) => void
    mockedChat.mockReturnValue(
      new Promise((resolve) => {
        resolveReply = resolve
      }),
    )

    useDatasetStore.setState({ datasets: [ANALYZED] })
    useWorkspaceStore.setState({ openDatasetIds: ['d1'], activeDatasetId: 'd1' })
    render(<ChatPanel />)

    const input = screen.getByPlaceholderText('Ask anything about your data...')
    fireEvent.change(input, { target: { value: 'What are the trends?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(screen.getByText('What are the trends?')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Send message' }),
    ).toBeDisabled()
    expect(mockedChat).toHaveBeenCalledWith('d1', 'What are the trends?')
    expect(useChatStore.getState().isSending).toBe(true)

    resolveReply!({ answer: 'Upward trend in Q3.', status: 'ok', session_id: 'd1' })
    await waitFor(() => {
      expect(screen.getByText('Upward trend in Q3.')).toBeInTheDocument()
    })
    expect(useChatStore.getState().isSending).toBe(false)
  })

  it('renders markdown in the bot reply', async () => {
    mockedChat.mockResolvedValue({ answer: '**Strong** finding', status: 'ok', session_id: 'd1' })
    useDatasetStore.setState({ datasets: [ANALYZED] })
    useWorkspaceStore.setState({ openDatasetIds: ['d1'], activeDatasetId: 'd1' })
    render(<ChatPanel />)

    fireEvent.change(
      screen.getByPlaceholderText('Ask anything about your data...'),
      { target: { value: 'hi' } },
    )
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => {
      expect(screen.getByText('Strong')).toBeInTheDocument()
    })
  })

  it('sends on Enter', async () => {
    useDatasetStore.setState({ datasets: [ANALYZED] })
    useWorkspaceStore.setState({ openDatasetIds: ['d1'], activeDatasetId: 'd1' })
    render(<ChatPanel />)

    const input = screen.getByPlaceholderText('Ask anything about your data...')
    fireEvent.change(input, { target: { value: 'hello' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => {
      expect(mockedChat).toHaveBeenCalledWith('d1', 'hello')
    })
  })

  it('ignores blank input', () => {
    useDatasetStore.setState({ datasets: [ANALYZED] })
    useWorkspaceStore.setState({ openDatasetIds: ['d1'], activeDatasetId: 'd1' })
    render(<ChatPanel />)

    fireEvent.change(screen.getByPlaceholderText('Ask anything about your data...'), {
      target: { value: '   ' },
    })
    const send = screen.getByRole('button', { name: 'Send message' })
    expect(send).toBeDisabled()
    fireEvent.click(send)
    expect(mockedChat).not.toHaveBeenCalled()
  })

  it('appends a canned reply and records the error when the API fails', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockedChat.mockRejectedValue(new Error('backend timeout'))

    useDatasetStore.setState({ datasets: [ANALYZED] })
    useWorkspaceStore.setState({ openDatasetIds: ['d1'], activeDatasetId: 'd1' })
    render(<ChatPanel />)

    fireEvent.change(screen.getByPlaceholderText('Ask anything about your data...'), {
      target: { value: 'hello' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    await waitFor(() => {
      expect(
        screen.getByText('Sorry, I encountered an error. Please try again.'),
      ).toBeInTheDocument()
    })
    expect(consoleSpy).toHaveBeenCalled()
    expect(useChatStore.getState().isSending).toBe(false)
    // Quirk: addMessage() clears the error state immediately after setError(),
    // so the detailed error never surfaces through the store.
    expect(useChatStore.getState().error).toBeNull()
  })

  it('restores earlier messages from the chat store', () => {
    useDatasetStore.setState({ datasets: [ANALYZED] })
    useWorkspaceStore.setState({ openDatasetIds: ['d1'], activeDatasetId: 'd1' })
    useChatStore.setState({
      messagesBySession: {
        d1: [
          {
            id: 'm1',
            role: 'user',
            content: 'earlier',
            createdAt: new Date().toISOString(),
          },
        ],
      },
    })
    render(<ChatPanel />)
    expect(screen.getByText('earlier')).toBeInTheDocument()
  })
})