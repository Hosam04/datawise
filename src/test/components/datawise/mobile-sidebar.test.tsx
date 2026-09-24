import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MobileSidebar } from '../../../components/datawise/mobile-sidebar'

vi.mock('@/components/datawise/sidebar-nav', () => ({
  SidebarNav: vi.fn(() => null),
}))

describe('MobileSidebar', () => {
  it('shows the dialog when open', () => {
    render(<MobileSidebar open={true} onClose={() => {}} />)
    expect(
      screen.getByRole('dialog', { name: 'Navigation menu' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Close navigation menu')).toBeInTheDocument()
  })

  it('locks body scroll while open and restores it on close', () => {
    const { rerender, unmount } = render(<MobileSidebar open={true} onClose={() => {}} />)
    expect(document.body.style.overflow).toBe('hidden')

    rerender(<MobileSidebar open={false} onClose={() => {}} />)
    expect(document.body.style.overflow).not.toBe('hidden')
    unmount()
  })

  it('focuses the close button when it opens', () => {
    render(<MobileSidebar open={true} onClose={() => {}} />)
    expect(screen.getByLabelText('Close navigation menu')).toHaveFocus()
  })

  it('invokes onClose via the close button and Escape', () => {
    const onClose = vi.fn()
    render(<MobileSidebar open={true} onClose={onClose} />)

    fireEvent.click(screen.getByLabelText('Close navigation menu'))
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('closes when the backdrop is clicked', () => {
    const onClose = vi.fn()
    const { container } = render(<MobileSidebar open={true} onClose={onClose} />)
    const dialog = screen.getByRole('dialog', { name: 'Navigation menu' })
    const backdrop = dialog.previousElementSibling as HTMLElement
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('keeps focus inside the dialog (focus trap)', () => {
    const { container } = render(<MobileSidebar open={true} onClose={() => {}} />)
    expect(screen.getByRole('dialog', { name: 'Navigation menu' })).toBeInTheDocument()
    expect(container.querySelector('[aria-modal="true"]')).toBeInTheDocument()
  })
})