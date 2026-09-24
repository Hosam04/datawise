import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '@testing-library/react'
import type { ReactNode } from 'react'
import {
  GlobalSearchProvider,
  GlobalSearchTrigger,
  useGlobalSearch,
} from '../../../components/datawise/global-search-provider'
import { useDatasetStore } from '../../../stores/dataset-store'
import { useReportStore } from '../../../stores/report-store'
import { useFavoriteStore } from '../../../stores/favorite-store'

vi.mock('cmdk', () => ({
  Command: {
    Dialog: vi.fn(
      ({ children, label, open }: { children: ReactNode; label: string; open: boolean }) =>
        open ? (
          <div data-testid="cmdk-dialog" aria-label={typeof label === 'string' ? label : undefined}>
            {children}
          </div>
        ) : null,
    ),
    Input: (props: Record<string, unknown>) => <input {...props} />,
    List: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    Empty: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    Group: ({ children, heading }: { children: ReactNode; heading: unknown }) => (
      <div data-group={typeof heading === 'string' ? heading : ''}>
        {typeof heading === 'string' ? heading : null}
        {children}
      </div>
    ),
    Item: ({ children, onSelect }: { children: ReactNode; onSelect?: () => void }) => (
      <div data-testid="cmdk-item" onClick={onSelect}>
        {children}
      </div>
    ),
  },
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}))

const pushMock = vi.fn()

function Harness({ children }: { children: React.ReactNode }) {
  return <GlobalSearchProvider>{children}</GlobalSearchProvider>
}

describe('GlobalSearchProvider', () => {
  beforeEach(() => {
    pushMock.mockReset()
    useDatasetStore.setState({ datasets: [] })
    useReportStore.setState({ reports: [] })
    useFavoriteStore.setState({ favorites: [] })
  })

  it('throws when useGlobalSearch is used without a provider', () => {
    const ConsoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const Bad = () => {
      useGlobalSearch()
      return null
    }
    expect(() => render(<Bad />)).toThrow(
      /useGlobalSearch must be used within GlobalSearchProvider/,
    )
    ConsoleError.mockRestore()
  })

  it('opens the dialog from a bar trigger', async () => {
    render(
      <Harness>
        <GlobalSearchTrigger variant="bar" />
      </Harness>,
    )
    expect(screen.queryByTestId('cmdk-dialog')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open global search' }))
    expect(screen.getByTestId('cmdk-dialog')).toBeInTheDocument()
    expect(
      screen.getByPlaceholderText('Search pages, datasets, reports, favorites...'),
    ).toBeInTheDocument()
  })

  it('toggles the dialog with Ctrl+K', () => {
    render(
      <Harness>
        <GlobalSearchTrigger />
      </Harness>,
    )
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true })
    expect(screen.getByTestId('cmdk-dialog')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'K', ctrlKey: true })
    expect(screen.queryByTestId('cmdk-dialog')).not.toBeInTheDocument()
  })

  it('ignores a plain K press without the modifier', () => {
    render(
      <Harness>
        <GlobalSearchTrigger />
      </Harness>,
    )
    fireEvent.keyDown(document, { key: 'k' })
    expect(screen.queryByTestId('cmdk-dialog')).not.toBeInTheDocument()
  })

  it('lists pages, datasets, and communities from the stores', async () => {
    useDatasetStore.setState({
      datasets: [
        { id: 'd1', name: 'sales.csv', size: '10 KB', type: 'CSV', status: 'Analyzed' },
      ],
    })
    render(
      <Harness>
        <GlobalSearchTrigger />
      </Harness>,
    )
    fireEvent.click(screen.getByRole('button', { name: /search/i }))
    expect(screen.getByTestId('cmdk-dialog')).toBeInTheDocument()
    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.getByText('sales.csv')).toBeInTheDocument()
    // 'Datasets' appears both as a group heading and as a page subtitle.
    expect(screen.getAllByText('Datasets').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Pages')).toBeInTheDocument()
  })

  it('navigates when an item is selected', () => {
    render(
      <Harness>
        <GlobalSearchTrigger />
      </Harness>,
    )
    fireEvent.click(screen.getByRole('button', { name: /search/i }))
    const homeItem = screen.getByText('Home')
    fireEvent.click(homeItem)
    expect(pushMock).toHaveBeenCalledWith('/')
    expect(screen.queryByTestId('cmdk-dialog')).not.toBeInTheDocument()
  })
})