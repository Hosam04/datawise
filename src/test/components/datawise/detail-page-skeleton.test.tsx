import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { DetailPageSkeleton } from '../../../components/datawise/detail-page-skeleton'

describe('DetailPageSkeleton', () => {
  it('renders a busy loading container with the details label', () => {
    const { container } = render(<DetailPageSkeleton />)
    const shell = container.querySelector('[aria-busy="true"]')
    expect(shell).not.toBeNull()
    expect(shell).toHaveAttribute('aria-label', 'Loading details')
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0)
  })
})