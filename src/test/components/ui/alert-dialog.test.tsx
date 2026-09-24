import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ConfirmDialog } from '../../../components/ui/alert-dialog'

describe('ConfirmDialog', () => {
  it('renders the trigger', () => {
    render(
      <ConfirmDialog
        title="Delete?"
        description="It will be gone."
        onConfirm={() => {}}
        trigger={<button type="button">Trash</button>}
      />,
    )
    expect(screen.getByRole('button', { name: 'Trash' })).toBeInTheDocument()
  })

  it('opens the dialog and runs onConfirm when confirmed', async () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        title="Delete dataset?"
        description="sales.csv will be removed."
        onConfirm={onConfirm}
        trigger={<button type="button">Trash</button>}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Trash' }))

    expect(
      await screen.findByRole('heading', { name: 'Delete dataset?' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('sales.csv will be removed.'),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1))
    await waitFor(() => {
      expect(
        screen.queryByRole('heading', { name: 'Delete dataset?' }),
      ).not.toBeInTheDocument()
    })
  })

  it('does not call onConfirm when cancelled', async () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        title="Delete dataset?"
        description="sales.csv will be removed."
        onConfirm={onConfirm}
        trigger={<button type="button">Trash</button>}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Trash' }))
    fireEvent.click(
      await screen.findByRole('button', { name: 'Cancel' }),
    )
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('supports a custom confirm label', async () => {
    render(
      <ConfirmDialog
        title="Remove history item?"
        description="It will be gone."
        confirmLabel="Remove"
        onConfirm={() => {}}
        trigger={<button type="button">Trash</button>}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Trash' }))
    expect(
      await screen.findByRole('button', { name: 'Remove' }),
    ).toBeInTheDocument()
  })
})