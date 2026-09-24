import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { DatasetSwitcher } from '../../../components/datawise/dataset-switcher'
import { useDatasetStore } from '../../../stores/dataset-store'
import { useWorkspaceStore } from '../../../stores/workspace-store'

const pushMock = vi.fn()
const pathnameMock = vi.fn(() => '/chat')
const paramsMock = { get: vi.fn<(key: string) => string | null>(() => null) }

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => pathnameMock(),
  useSearchParams: () => paramsMock,
}))

vi.mock('@/hooks/use-store-hydration', () => ({
  useDatasetSwitcherHydration: () => true,
}))

const dataset = {
  id: 'd1',
  name: 'sales.csv',
  size: '10 KB',
  type: 'CSV',
  status: 'Analyzed',
}

function flushMount() {
  return act(async () => {})
}

describe('DatasetSwitcher', () => {
  beforeEach(() => {
    pushMock.mockReset()
    pathnameMock.mockReset()
    pathnameMock.mockReturnValue('/chat')
    paramsMock.get.mockReset()
    paramsMock.get.mockReturnValue(null)
    useDatasetStore.setState({ datasets: [] })
    useWorkspaceStore.setState({
      openDatasetIds: [],
      activeDatasetId: null,
    })
  })

  it('shows the skeleton before the component has mounted', async () => {
    render(<DatasetSwitcher />)
    expect(await screen.findByText('Select a dataset')).toBeInTheDocument()
  })

  it('links to /datasets when there are no open datasets', async () => {
    render(<DatasetSwitcher />)
    const link = await screen.findByText('Select a dataset')
    expect(link.closest('a')).toHaveAttribute('href', '/datasets')
  })

  it('shows the active dataset name and navigates to chat on click', async () => {
    useDatasetStore.setState({ datasets: [dataset] })
    useWorkspaceStore.setState({
      openDatasetIds: ['d1'],
      activeDatasetId: 'd1',
    })
    render(<DatasetSwitcher />)
    const trigger = await screen.findByRole('button', { name: /sales.csv$/ })
    fireEvent.click(trigger)
    expect(pushMock).toHaveBeenCalledWith('/chat?dataset=d1')
  })

  it('opens a listbox when multiple datasets are open and switches selection', async () => {
    useDatasetStore.setState({
      datasets: [
        dataset,
        { ...dataset, id: 'd2', name: 'billing.csv' },
      ],
    })
    useWorkspaceStore.setState({
      openDatasetIds: ['d1', 'd2'],
      activeDatasetId: 'd1',
    })
    render(<DatasetSwitcher />)

    const button = await screen.findByRole('button')
    fireEvent.click(button)
    const listbox = screen.getByRole('listbox')
    expect(listbox).toBeInTheDocument()
    expect(screen.getByText('billing.csv')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('option', { name: /billing.csv/ }))
    expect(useWorkspaceStore.getState().activeDatasetId).toBe('d2')
    expect(pushMock).toHaveBeenCalledWith('/chat?dataset=d2')
  })

  it('cleans up stale open dataset ids', async () => {
    useDatasetStore.setState({ datasets: [dataset] })
    useWorkspaceStore.setState({
      openDatasetIds: ['d1', 'ghost'],
      activeDatasetId: 'd1',
    })
    render(<DatasetSwitcher />)
    await screen.findByRole('button')
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual(['d1'])
  })

  it('opens a dataset coming from the URL query on /chat', async () => {
    useDatasetStore.setState({ datasets: [dataset, { ...dataset, id: 'd9', name: 'z.csv' }] })
    paramsMock.get.mockReturnValue('d9')
    render(<DatasetSwitcher />)
    await act(async () => {})
    expect(useWorkspaceStore.getState().openDatasetIds).toContain('d9')
  })
})