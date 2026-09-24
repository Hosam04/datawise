import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import {
  ListCardSkeleton,
  ListCardSkeletonGroup,
  StatCardSkeleton,
  StatCardSkeletonGroup,
  DatasetSwitcherSkeleton,
  ListToolbarSkeleton,
} from '../../../components/datawise/card-skeleton'

describe('ListCardSkeleton', () => {
  it('renders an aria-busy skeleton group with the right count', () => {
    const { container } = render(<ListCardSkeletonGroup count={5} />)
    const group = container.querySelector('[aria-busy="true"]')
    expect(group).toHaveAttribute('aria-label', 'Loading content')
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0)
  })

  it('renders the requested number of cards', () => {
    const { container } = render(<ListCardSkeletonGroup count={2} />)
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThanOrEqual(
      2 * 5,
    )
  })
})

describe('StatCardSkeleton', () => {
  it('renders a skeleton card that is hidden from assistive tech', () => {
    const { container } = render(<StatCardSkeleton />)
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull()
  })
})

describe('StatCardSkeletonGroup', () => {
  it('renders count skeleton cards with four hidden nodes each', () => {
    const { container } = render(<StatCardSkeletonGroup count={4} />)
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBe(16)
  })
})

describe('DatasetSwitcherSkeleton', () => {
  it('renders a skeleton', () => {
    const { container } = render(<DatasetSwitcherSkeleton />)
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull()
  })
})

describe('ListToolbarSkeleton', () => {
  it('renders multiple skeletons', () => {
    const { container } = render(<ListToolbarSkeleton />)
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(1)
  })
})