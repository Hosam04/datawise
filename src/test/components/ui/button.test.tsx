import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Button, buttonVariants } from '../../../components/ui/button'

describe('Button', () => {
  it('renders a button with accessible label content', () => {
    render(<Button>Click</Button>)
    expect(screen.getByRole('button', { name: 'Click' })).toBeInTheDocument()
    expect(screen.getByRole('button')).toHaveAttribute('data-slot', 'button')
  })

  it('applies the outline variant classes', () => {
    render(<Button variant="outline">Outline</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveClass('border-border')
  })

  it('forwards click handlers', () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not fire handlers while disabled', () => {
    const onClick = vi.fn()
    render(
      <Button onClick={onClick} disabled>
        Disabled
      </Button>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Disabled' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('exports buttonVariants with the requested classes', () => {
    expect(buttonVariants({ variant: 'destructive', size: 'lg' })).toContain(
      'text-destructive',
    )
    expect(buttonVariants({ variant: 'ghost', size: 'icon' })).toContain('size-8')
  })
})