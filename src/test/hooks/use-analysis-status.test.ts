import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAnalysisStatus } from '../../hooks/use-analysis-status'
import { useDatasetStore, type Dataset } from '../../stores/dataset-store'

vi.mock('@/lib/api', () => ({
  getAnalysisStatus: vi.fn(),
}))

import { getAnalysisStatus } from '../../lib/api'
const mockedGetStatus = vi.mocked(getAnalysisStatus)

const SESSION = 's1'
const dataset = (status: string): Dataset => ({
  id: SESSION,
  name: 'data.csv',
  size: '1 KB',
  type: 'CSV',
  status,
})

describe('useAnalysisStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockedGetStatus.mockReset()
    mockedGetStatus.mockResolvedValue({ status: 'processing' })
    useDatasetStore.setState({ datasets: [dataset('Processing')] })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    useDatasetStore.setState({ datasets: [] })
  })

  function statusOf() {
    return useDatasetStore
      .getState()
      .datasets.find((d) => d.id === SESSION)!.status
  }

  it('does not poll when there is no session id', async () => {
    renderHook(() => useAnalysisStatus())
    await act(async () => {
      vi.advanceTimersByTime(10_000)
    })
    expect(mockedGetStatus).not.toHaveBeenCalled()
  })

  it('polls the backend every 3 seconds', async () => {
    renderHook(() => useAnalysisStatus(SESSION))
    await act(async () => {
      vi.advanceTimersByTime(9_000)
    })
    expect(mockedGetStatus).toHaveBeenCalledTimes(3)
    expect(mockedGetStatus).toHaveBeenCalledWith(SESSION)
  })

  it('maps processing to Processing', async () => {
    renderHook(() => useAnalysisStatus(SESSION))
    await act(async () => {
      vi.advanceTimersByTime(3_000)
    })
    expect(statusOf()).toBe('Processing')
  })

  it('maps completed to Analyzed and stops polling', async () => {
    mockedGetStatus.mockResolvedValue({ status: 'completed' })
    renderHook(() => useAnalysisStatus(SESSION))
    await act(async () => {
      vi.advanceTimersByTime(3_000)
    })
    expect(statusOf()).toBe('Analyzed')
    expect(mockedGetStatus).toHaveBeenCalledTimes(1)

    mockedGetStatus.mockClear()
    await act(async () => {
      vi.advanceTimersByTime(9_000)
    })
    expect(mockedGetStatus).not.toHaveBeenCalled()
  })

  it('keeps polling and leaves status unchanged when the request fails', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockedGetStatus.mockRejectedValue(new Error('network down'))
    renderHook(() => useAnalysisStatus(SESSION))

    await act(async () => {
      vi.advanceTimersByTime(9_000)
    })
    expect(mockedGetStatus).toHaveBeenCalledTimes(3)
    expect(consoleSpy).toHaveBeenCalled()
    expect(statusOf()).toBe('Processing')
  })

  it('recovers from a transient error once a later poll succeeds', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockedGetStatus
      .mockRejectedValueOnce(new Error('transient'))
      .mockResolvedValue({ status: 'completed' })

    renderHook(() => useAnalysisStatus(SESSION))
    await act(async () => {
      vi.advanceTimersByTime(6_000)
    })

    expect(mockedGetStatus).toHaveBeenCalledTimes(2)
    expect(statusOf()).toBe('Analyzed')
    mockedGetStatus.mockClear()
    await act(async () => {
      vi.advanceTimersByTime(6_000)
    })
    expect(mockedGetStatus).not.toHaveBeenCalled()
  })

  it('clears the interval on unmount', async () => {
    const { unmount } = renderHook(() => useAnalysisStatus(SESSION))
    unmount()
    mockedGetStatus.mockClear()
    await act(async () => {
      vi.advanceTimersByTime(12_000)
    })
    expect(mockedGetStatus).not.toHaveBeenCalled()
  })
})