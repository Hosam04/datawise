import { beforeEach, describe, expect, it } from 'vitest'
import { useDatasetStore } from '../../stores/dataset-store'
import type { CompletedArtifacts } from '../../types/artifacts'

const DATASET = {
  id: 'd1',
  name: 'sales.csv',
  size: '10 KB',
  type: 'text/csv',
  status: 'Analyzed',
  uploadedAt: '2025-01-01T00:00:00Z',
}

const ARTIFACTS: CompletedArtifacts = {
  summary: 'summary',
  preview: { columns: [], rows: [] },
  charts: [],
  insights: [],
} as unknown as CompletedArtifacts

beforeEach(() => {
  useDatasetStore.setState({ datasets: [] })
  localStorage.clear()
})

describe('dataset-store actions', () => {
  it('adds a dataset (append order)', () => {
    const { addDataset } = useDatasetStore.getState()
    addDataset(DATASET)
    addDataset({ ...DATASET, id: 'd2', name: 'other.csv' })
    expect(useDatasetStore.getState().datasets.map((d) => d.name)).toEqual([
      'sales.csv',
      'other.csv',
    ])
  })

  it('dedupes by id on add', () => {
    const { addDataset } = useDatasetStore.getState()
    addDataset(DATASET)
    addDataset(DATASET)
    expect(useDatasetStore.getState().datasets).toHaveLength(1)
  })

  it('removes a dataset by id', () => {
    const { addDataset, removeDataset } = useDatasetStore.getState()
    addDataset(DATASET)
    addDataset({ ...DATASET, id: 'd2' })
    removeDataset('d1')
    expect(useDatasetStore.getState().datasets.map((d) => d.id)).toEqual(['d2'])
  })

  it('updates status for a matching id only', () => {
    const { addDataset, updateDatasetStatus } = useDatasetStore.getState()
    addDataset(DATASET)
    addDataset({ ...DATASET, id: 'd2' })
    updateDatasetStatus('d1', 'Processing')
    const byId = Object.fromEntries(
      useDatasetStore.getState().datasets.map((d) => [d.id, d.status]),
    )
    expect(byId.d1).toBe('Processing')
    expect(byId.d2).toBe('Analyzed')
  })

  it('sets artifacts for a matching id', () => {
    const { addDataset, setDatasetArtifacts } = useDatasetStore.getState()
    addDataset(DATASET)
    setDatasetArtifacts('d1', ARTIFACTS)
    expect(useDatasetStore.getState().datasets[0].artifacts).toBe(ARTIFACTS)
  })
})

describe('dataset-store persistence (quota safety)', () => {
  it('never persists artifacts to localStorage', () => {
    const { addDataset, setDatasetArtifacts } = useDatasetStore.getState()
    addDataset(DATASET)
    setDatasetArtifacts('d1', ARTIFACTS)

    // In memory the artifacts are present...
    expect(useDatasetStore.getState().datasets[0].artifacts).toBeTruthy()

    // ...but the persisted snapshot must strip them.
    const persisted = JSON.parse(
      localStorage.getItem('datawise-datasets') ?? '{}',
    )
    expect(persisted.state.datasets[0]).not.toHaveProperty('artifacts')
    expect(persisted.state.datasets[0].id).toBe('d1')
  })

  it('strips artifacts during rehydration from a legacy payload', async () => {
    const legacy = {
      state: {
        datasets: [
          { ...DATASET, artifacts: ARTIFACTS },
          { ...DATASET, id: 'd2', name: 'x.csv' },
        ],
      },
      version: 0,
    }
    localStorage.setItem('datawise-datasets', JSON.stringify(legacy))

    await useDatasetStore.persist.rehydrate()

    const datasets = useDatasetStore.getState().datasets
    expect(datasets).toHaveLength(2)
    expect(datasets[0]).not.toHaveProperty('artifacts')
    expect(datasets[0].name).toBe('sales.csv')
    expect(datasets[1].id).toBe('d2')
  })
})