import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { AnimatedList } from '../../../components/datawise/animated-list'
import { PageTransition } from '../../../components/datawise/page-transition'

describe('AnimatedList', () => {
  it('staggers children with increasing animation delays', () => {
    const { container } = render(
      <AnimatedList>
        <div key="a">a</div>
        <div key="b">b</div>
        <div key="c">c</div>
      </AnimatedList>,
    )
    const items = Array.from(container.querySelectorAll<HTMLElement>('[style*="animation-delay"]'))
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveStyle('animation-delay: 0ms')
    expect(items[1]).toHaveStyle('animation-delay: 45ms')
    expect(items[2]).toHaveStyle('animation-delay: 90ms')
  })

  it('honors a custom stagger interval', () => {
    const { container } = render(
      <AnimatedList staggerMs={100}>
        <span key="a">a</span>
        <span key="b">b</span>
      </AnimatedList>,
    )
    const items = container.querySelectorAll('div > *')
    expect(items[1]).toHaveStyle('animation-delay: 100ms')
  })
})

describe('PageTransition', () => {
  it('applies a fill-mode animation to the wrapper', () => {
    const { container } = render(<PageTransition>content</PageTransition>)
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper).not.toBeNull()
    expect(wrapper.style.animationFillMode).toBe('both')
    expect(wrapper.textContent).toBe('content')
  })
})