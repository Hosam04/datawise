import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EmptyState } from '../../../components/datawise/empty-state'

describe('EmptyState', () => {
  it('renders the preset content for the activity variant', async () => {
    render(<EmptyState variant="activity" />)
    expect(await screen.findByRole('heading')).toBeInTheDocument()
    expect(screen.getByText('Upload dataset')).toBeInTheDocument()
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument()
  })

  it('overrides preset content with custom props', async () => {
    render(
      <EmptyState
        variant="activity"
        title="Custom title"
        description="Custom description"
        primaryAction={{ label: 'Go', href: '/anywhere' }}
      />,
    )
    expect(await screen.findByText('Custom title')).toBeInTheDocument()
    expect(screen.getByText('Custom description')).toBeInTheDocument()
    expect(screen.queryByText(/no recent activity/i)).not.toBeInTheDocument()
    const link = screen.getByText('Go').closest('a')
    expect(link).toHaveAttribute('href', '/anywhere')
  })

  it('still supports the deprecated message/action props', async () => {
    render(
      <EmptyState
        variant="activity"
        message="Old message"
        actionLabel="Old action"
        actionHref="/old"
      />,
    )
    expect(await screen.findByText('Old message')).toBeInTheDocument()
    const link = screen.getByText('Old action').closest('a')
    expect(link).toHaveAttribute('href', '/old')
  })

  it('renders a button action when href is # and onClick is provided', async () => {
    const onClick = vi.fn()
    render(
      <EmptyState
        variant="activity"
        primaryAction={{ label: 'Retry', href: '#', onClick }}
      />,
    )
    const button = await screen.findByRole('button', { name: 'Retry' })
    fireEvent.click(button)
    expect(onClick).toHaveBeenCalled()
  })
})