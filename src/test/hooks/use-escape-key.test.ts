import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { act } from 'react'
import { useEscapeKey } from '../../hooks/use-escape-key'

function pressEscape() {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
}

describe('useEscapeKey', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('calls the handler when Escape is pressed', () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(onEscape))
    pressEscape()
    expect(onEscape).toHaveBeenCalledTimes(1)
  })

  it('ignores other keys', () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(onEscape))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    expect(onEscape).not.toHaveBeenCalled()
  })

  it('does not listen when disabled', () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(onEscape, false))
    pressEscape()
    expect(onEscape).not.toHaveBeenCalled()
  })

  it('removes the listener on unmount', () => {
    const onEscape = vi.fn()
    const { unmount } = renderHook(() => useEscapeKey(onEscape))
    unmount()
    pressEscape()
    expect(onEscape).not.toHaveBeenCalled()
  })

  it('re-subscribes when a new handler is passed', () => {
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook(({ handler }) => useEscapeKey(handler), {
      initialProps: { handler: first },
    })
    rerender({ handler: second })
    pressEscape()
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })
})