import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FileCard } from '../../../components/upload/file-card'

const csv = new File(['a,b,c'], 'sales.csv', { type: 'text/csv' })

describe('FileCard', () => {
  it('shows the file name, size, and kind label', () => {
    const { container } = render(<FileCard file={csv} onRemove={vi.fn()} />)
    expect(screen.getByText('sales.csv')).toBeInTheDocument()
    expect(container.textContent).toContain('5 B')
    expect(container.textContent).toContain('CSV')
  })

  it('calls onRemove from the remove button', () => {
    const onRemove = vi.fn()
    render(<FileCard file={csv} onRemove={onRemove} />)
    fireEvent.click(screen.getByRole('button', { name: 'Remove file' }))
    expect(onRemove).toHaveBeenCalledTimes(1)
  })

  it('disables the remove button when asked', () => {
    render(<FileCard file={csv} onRemove={vi.fn()} disableRemove />)
    expect(screen.getByRole('button', { name: 'Remove file' })).toBeDisabled()
  })

  it('hides the remove button in the success variant', () => {
    render(<FileCard file={csv} onRemove={vi.fn()} variant="success" />)
    expect(
      screen.queryByRole('button', { name: 'Remove file' }),
    ).not.toBeInTheDocument()
  })

  it('does not show a kind label for unknown file types', () => {
    const txt = new File(['x'], 'notes.txt', { type: 'text/plain' })
    render(<FileCard file={txt} onRemove={vi.fn()} />)
    expect(screen.getByText('notes.txt')).toBeInTheDocument()
    expect(screen.queryByText(/·/)).not.toBeInTheDocument()
  })
})