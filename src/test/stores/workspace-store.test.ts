import { beforeEach, describe, expect, it } from 'vitest'
import { useWorkspaceStore } from '../../stores/workspace-store'

beforeEach(() => {
  useWorkspaceStore.setState({ openDatasetIds: [], activeDatasetId: null })
  localStorage.clear()
})

describe('workspace-store', () => {
  it('starts with an empty workspace', () => {
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual([])
    expect(useWorkspaceStore.getState().activeDatasetId).toBeNull()
  })

  it('openDataset adds the id and makes it active', () => {
    const { openDataset } = useWorkspaceStore.getState()
    openDataset('d1')
    openDataset('d2')
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual(['d1', 'd2'])
    expect(useWorkspaceStore.getState().activeDatasetId).toBe('d2')
  })

  it('openDataset is idempotent for the same id', () => {
    const { openDataset } = useWorkspaceStore.getState()
    openDataset('d1')
    openDataset('d1')
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual(['d1'])
  })

  it('setActiveDataset only works for open datasets', () => {
    const { openDataset, setActiveDataset } = useWorkspaceStore.getState()
    openDataset('d1')
    openDataset('d2')

    setActiveDataset('d1')
    expect(useWorkspaceStore.getState().activeDatasetId).toBe('d1')

    setActiveDataset('not-open')
    expect(useWorkspaceStore.getState().activeDatasetId).toBe('d1')
  })

  it('removeOpenDataset removes any id from the list', () => {
    const { openDataset, removeOpenDataset } = useWorkspaceStore.getState()
    openDataset('d1')
    openDataset('d2')
    openDataset('d3')
    removeOpenDataset('d2')
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual(['d1', 'd3'])
  })

  it('promotes the last remaining dataset as active when the active one is removed', () => {
    const { openDataset, removeOpenDataset } = useWorkspaceStore.getState()
    openDataset('d1')
    openDataset('d2')
    removeOpenDataset('d2')
    expect(useWorkspaceStore.getState().activeDatasetId).toBe('d1')
  })

  it('clears the active dataset when the last one is removed', () => {
    const { openDataset, removeOpenDataset } = useWorkspaceStore.getState()
    openDataset('d1')
    removeOpenDataset('d1')
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual([])
    expect(useWorkspaceStore.getState().activeDatasetId).toBeNull()
  })

  it('keeps the active dataset when a non-active one is removed', () => {
    const { openDataset, removeOpenDataset, setActiveDataset } =
      useWorkspaceStore.getState()
    openDataset('d1')
    openDataset('d2')
    setActiveDataset('d1')
    removeOpenDataset('d2')
    expect(useWorkspaceStore.getState().activeDatasetId).toBe('d1')
  })

  it('clearWorkspace resets the workspace', () => {
    const { openDataset, clearWorkspace } = useWorkspaceStore.getState()
    openDataset('d1')
    clearWorkspace()
    expect(useWorkspaceStore.getState().openDatasetIds).toEqual([])
    expect(useWorkspaceStore.getState().activeDatasetId).toBeNull()
  })

  it('persists the workspace', () => {
    const { openDataset } = useWorkspaceStore.getState()
    openDataset('d1')
    const persisted = JSON.parse(
      localStorage.getItem('datawise-workspace') ?? '{}',
    )
    expect(persisted.state.openDatasetIds).toEqual(['d1'])
    expect(persisted.state.activeDatasetId).toBe('d1')
  })
})