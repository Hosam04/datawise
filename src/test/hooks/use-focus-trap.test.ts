import { beforeEach, describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { createRef } from 'react'
import { useFocusTrap } from '../../hooks/use-focus-trap'

function mountTrap(active: boolean) {
  document.body.innerHTML = `
    <button id="outside">outside</button>
    <div id="trap">
      <input id="first" />
      <button id="middle">middle</button>
      <a id="last" href="#">last</a>
    </div>
  `
  const container = document.getElementById('trap') as HTMLDivElement
  // jsdom has no layout engine so offsetParent is always null; the trap
  // treats null-offset containers as hidden. Simulate "visible" elements.
  container
    .querySelectorAll<HTMLElement>('#first, #middle, #last')
    .forEach((el) =>
      Object.defineProperty(el, 'offsetParent', {
        configurable: true,
        value: document.body,
      }),
    )
  const ref = createRef<HTMLDivElement>()
  ref.current = container
  const { rerender, unmount } = renderHook(
    (props) => useFocusTrap(ref, props),
    { initialProps: active },
  )
  return { container, rerender, unmount }
}

function pressTab(shiftKey = false) {
  const target = (document.activeElement ?? document.body) as HTMLElement
  target.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true, shiftKey }),
  )
}

describe('useFocusTrap', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('wraps focus back to the first element from the last on Tab', () => {
    const { container } = mountTrap(true)
    const last = container.querySelector<HTMLElement>('#last')!
    last.focus()
    pressTab()
    expect(document.activeElement?.id).toBe('first')
  })

  it('wraps focus to the last element from the first on Shift+Tab', () => {
    const { container } = mountTrap(true)
    const first = container.querySelector<HTMLElement>('#first')!
    first.focus()
    pressTab(true)
    expect(document.activeElement?.id).toBe('last')
  })

  it('does not interfere with native Tab when in the middle of the trap', () => {
    const { container } = mountTrap(true)
    container.querySelector<HTMLElement>('#middle')!.focus()
    pressTab()
    // Native browser navigation would move focus; jsdom stays put. The trap
    // must not preventDefault or wrap when the active element is not a boundary.
    expect(document.activeElement?.id).toBe('middle')
  })

  it('does not trap when inactive', () => {
    mountTrap(false)
    const last = document.querySelector<HTMLElement>('#last')!
    last.focus()
    pressTab()
    expect(document.activeElement?.id).toBe('last')
  })

  it('restores focus to the previously focused element on cleanup', () => {
    document.body.innerHTML = `<button id="outside">outside</button>
      <div id="trap"><button id="first">first</button></div>`
    const outside = document.getElementById('outside')!
    outside.focus()
    const ref = createRef<HTMLDivElement>()
    ref.current = document.getElementById('trap') as HTMLDivElement
    const { unmount } = renderHook(() => useFocusTrap(ref, true))
    unmount()
    expect(document.activeElement?.id).toBe('outside')
  })

  it('ignores Tab when there are no focusable elements', () => {
    document.body.innerHTML = `<div id="empty">
      <span tabindex="-1">skipped</span>
    </div>`
    const ref = createRef<HTMLDivElement>()
    ref.current = document.getElementById('empty') as HTMLDivElement
    const { unmount } = renderHook(() => useFocusTrap(ref, true))
    expect(() => pressTab()).not.toThrow()
    unmount()
  })

  it('does not interfere with native Tab when in the middle of the trap', () => {
    const { container } = mountTrap(true)
    container.querySelector<HTMLElement>('#middle')!.focus()
    pressTab()
    // Native browser navigation would move focus; jsdom stays put. The trap
    // must not preventDefault or wrap when the active element is not a boundary.
    expect(document.activeElement?.id).toBe('middle')
  })
})