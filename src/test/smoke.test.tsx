import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { cn } from '../lib/utils'

describe('smoke', () => {
  it('runs the vitest pipeline with the @ alias', () => {
    expect(cn('a', false && 'b', 'c')).toBe('a c')
  })

  it('renders and queries with testing-library in jsdom', () => {
    render(<button>Hello</button>)
    expect(screen.getByRole('button', { name: 'Hello' })).toBeInTheDocument()
  })
})