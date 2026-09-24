import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { Skeleton } from '../../../components/ui/skeleton'

describe('Skeleton', () => {
  it('renders an aria-hidden placeholder div', () => {
    const { container } = render(<Skeleton className="h-8 w-32" />)
    const el = container.firstElementChild as HTMLElement
    expect(el).not.toBeNull()
    expect(el.getAttribute('aria-hidden')).toBe('true')
    expect(el.className).toContain('h-8')
  })
})