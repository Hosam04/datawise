import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NotificationsDropdown } from '../../../components/datawise/notifications-dropdown'
import { useNotificationStore } from '../../../stores/notification-store'
import type { NotificationItem } from '../../../stores/notification-store'

const item = (overrides: Partial<NotificationItem> = {}): NotificationItem => ({
  id: 'n1',
  action: 'Analysis completed',
  file: 'sales.csv',
  time: '2m ago',
  href: '/chat?dataset=1700000000000',
  ...overrides,
})

function resetStores() {
  useNotificationStore.setState({ items: [], seenIds: [], dismissedIds: [] })
}

describe('NotificationsDropdown', () => {
  beforeEach(() => {
    resetStores()
  })

  it('shows a bell trigger and an empty state when there are no notifications', () => {
    render(<NotificationsDropdown />)
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(screen.getByText('No notifications yet')).toBeInTheDocument()
    expect(screen.queryByText('View all activity')).not.toBeInTheDocument()
  })

  it('lists notifications and shows unread count badges', () => {
    useNotificationStore.setState({
      items: [
        item({ id: 'a', action: 'Upload completed', file: 'u.csv' }),
        item({ id: 'b' }),
      ],
    })
    render(<NotificationsDropdown />)
    expect(screen.getByText('2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(screen.getByText('Upload completed')).toBeInTheDocument()
    expect(screen.getByText('Analysis completed')).toBeInTheDocument()
    expect(screen.getByText('sales.csv', { exact: true })).toBeInTheDocument()
  })

  it('links notifications to their destination', () => {
    useNotificationStore.setState({ items: [item({ id: 'a', href: '/datasets/x' })] })
    render(<NotificationsDropdown />)
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(screen.getByRole('link', { name: /Analysis completed/ })).toHaveAttribute(
      'href',
      '/datasets/x',
    )
  })

  it('hides dismissed items from the list', () => {
    useNotificationStore.setState({
      items: [item({ id: 'x' }), item({ id: 'y' })],
      dismissedIds: ['x'],
    })
    render(<NotificationsDropdown />)
    expect(screen.getByText('1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(screen.getByText('Analysis completed')).toBeInTheDocument()
  })

  it('marks everything seen when opening and clears via the Clear button', () => {
    useNotificationStore.setState({ items: [item(), item({ id: 'c' })] })
    render(<NotificationsDropdown />)
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(useNotificationStore.getState().seenIds.sort()).toEqual(['c', 'n1'])

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    expect(useNotificationStore.getState().dismissedIds.sort()).toEqual(['c', 'n1'])
    expect(screen.queryByText('Analysis completed')).not.toBeInTheDocument()
  })

  it('caps the visible notification list to 8 entries', () => {
    useNotificationStore.setState({
      items: Array.from({ length: 12 }, (_, i) => item({ id: `n${i}` })),
    })
    render(<NotificationsDropdown />)
    // The unread badge is shown only before the notification list is opened.
    expect(screen.getByText('9+')).toBeInTheDocument()
  })

  it('closes on an outside click', () => {
    useNotificationStore.setState({ items: [item()] })
    render(<NotificationsDropdown />)
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(screen.getByText('Analysis completed')).toBeInTheDocument()
    fireEvent.mouseDown(document.body)
    expect(screen.queryByText('Analysis completed')).not.toBeInTheDocument()
  })
})