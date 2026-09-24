import { beforeEach, describe, expect, it } from 'vitest'
import { useNotificationStore } from '../../stores/notification-store'
import type { NotificationItem } from '../../stores/notification-store'

const ITEMS: NotificationItem[] = [
  {
    id: 'n1',
    action: 'Dataset uploaded',
    file: 'sales.csv',
    time: 'Just now',
    href: '/datasets/1700000000000',
  },
  {
    id: 'n2',
    action: 'Analysis completed',
    file: 'sales.csv',
    time: 'Just now',
    href: '/chat?dataset=1700000000000',
  },
]

beforeEach(() => {
  useNotificationStore.setState({ items: [], seenIds: [], dismissedIds: [] })
  localStorage.clear()
})

describe('notification-store', () => {
  it('starts empty', () => {
    expect(useNotificationStore.getState().items).toEqual([])
    expect(useNotificationStore.getState().seenIds).toEqual([])
    expect(useNotificationStore.getState().dismissedIds).toEqual([])
  })

  it('addNotification prepends new items', () => {
    const { addNotification } = useNotificationStore.getState()
    addNotification(ITEMS[0])
    addNotification(ITEMS[1])
    expect(useNotificationStore.getState().items.map((i) => i.id)).toEqual([
      'n2',
      'n1',
    ])
  })

  it('addNotification deduplicates by id', () => {
    const { addNotification } = useNotificationStore.getState()
    addNotification(ITEMS[0])
    addNotification(ITEMS[0])
    expect(useNotificationStore.getState().items).toHaveLength(1)
  })

  it('addNotification caps items to 50', () => {
    const { addNotification } = useNotificationStore.getState()
    for (let i = 0; i < 55; i += 1) {
      addNotification({ ...ITEMS[0], id: `item-${i}` })
    }
    expect(useNotificationStore.getState().items).toHaveLength(50)
  })

  it('markAllSeen merges ids deduplicated', () => {
    const { markAllSeen } = useNotificationStore.getState()
    markAllSeen(['a', 'b'])
    markAllSeen(['b', 'c'])
    expect(useNotificationStore.getState().seenIds.sort()).toEqual([
      'a',
      'b',
      'c',
    ])
  })

  it('dismissAll marks ids as seen and dismissed', () => {
    const { dismissAll } = useNotificationStore.getState()
    dismissAll(['a', 'b'])
    dismissAll(['b', 'c'])
    const s = useNotificationStore.getState()
    expect(s.seenIds.sort()).toEqual(['a', 'b', 'c'])
    expect(s.dismissedIds.sort()).toEqual(['a', 'b', 'c'])
  })

  it('clearNotifications empties items and both lists', () => {
    const { addNotification, markAllSeen, dismissAll, clearNotifications } =
      useNotificationStore.getState()
    addNotification(ITEMS[0])
    dismissAll(['a'])
    markAllSeen(['b'])
    clearNotifications()
    const s = useNotificationStore.getState()
    expect(s.items).toEqual([])
    expect(s.seenIds).toEqual([])
    expect(s.dismissedIds).toEqual([])
  })

  it('persists items and both lists', () => {
    const { addNotification, dismissAll } = useNotificationStore.getState()
    addNotification(ITEMS[0])
    dismissAll(['a'])
    const persisted = JSON.parse(
      localStorage.getItem('datawise-notifications') ?? '{}',
    )
    expect(persisted.state.items.map((i: NotificationItem) => i.id)).toEqual([
      'n1',
    ])
    expect(persisted.state.dismissedIds).toEqual(['a'])
    expect(persisted.state.seenIds).toEqual(['a'])
  })
})