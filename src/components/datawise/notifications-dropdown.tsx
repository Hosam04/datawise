'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { Bell } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { NotificationItem } from '@/stores/notification-store'
import { useNotificationStore } from '@/stores/notification-store'
import { IconTooltip } from '@/components/ui/tooltip'
import { useEscapeKey } from '@/hooks/use-escape-key'
import { focusRing } from '@/lib/ui-styles'

function NotificationItem({
  item,
  unread,
  onNavigate,
}: {
  item: NotificationItem
  unread: boolean
  onNavigate: () => void
}) {
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn(
        'flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted',
        unread && 'bg-primary/5',
      )}
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <Bell className="size-4 text-primary" />
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{item.action}</p>
        <p className="truncate text-xs text-muted-foreground">{item.file}</p>
      </div>

      <span className="shrink-0 text-xs text-muted-foreground">{item.time}</span>
    </Link>
  )
}

export function NotificationsDropdown() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)

  const items = useNotificationStore((state) => state.items)
  const seenIds = useNotificationStore((state) => state.seenIds)
  const dismissedIds = useNotificationStore((state) => state.dismissedIds)
  const markAllSeen = useNotificationStore((state) => state.markAllSeen)
  const dismissAll = useNotificationStore((state) => state.dismissAll)

  const recentNotifications = useMemo(
    () => items.filter((item) => !dismissedIds.includes(item.id)).slice(0, 8),
    [items, dismissedIds],
  )

  const unreadCount = useMemo(
    () =>
      items.filter(
        (item) =>
          !seenIds.includes(item.id) && !dismissedIds.includes(item.id),
      ).length,
    [items, seenIds, dismissedIds],
  )

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleToggle = () => {
    const nextOpen = !open

    if (nextOpen) {
      markAllSeen(
        items
          .filter((item) => !dismissedIds.includes(item.id))
          .map((item) => item.id),
      )
    }

    setOpen(nextOpen)
  }

  const close = useCallback(() => setOpen(false), [])

  const handleClear = () => {
    dismissAll(items.map((item) => item.id))
  }

  useEscapeKey(close, open)

  return (
    <div ref={containerRef} className="relative">
      <IconTooltip
        label="Notifications"
        onClick={handleToggle}
        aria-expanded={open}
        aria-haspopup="true"
        className="relative flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <Bell className="size-4.5" aria-hidden="true" />

        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </IconTooltip>

      {open && (
        <div className="absolute top-full right-0 z-50 mt-2 w-90 overflow-hidden rounded-xl border border-border bg-card shadow-lg">
          <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Notifications</h2>
              <p className="text-xs text-muted-foreground">
                Recent activity from your workspace
              </p>
            </div>

            {recentNotifications.length > 0 && (
              <button
                type="button"
                onClick={handleClear}
                className={cn(
                  'shrink-0 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                  focusRing,
                )}
              >
                Clear
              </button>
            )}
          </div>

          <div className="max-h-90 overflow-y-auto p-1">
            {recentNotifications.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <Bell className="mx-auto mb-2 size-8 text-muted-foreground/50" />
                <p className="text-sm font-medium text-foreground">
                  No notifications yet
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Upload a dataset or run an analysis to see updates here.
                </p>
              </div>
            ) : (
              recentNotifications.map((item) => (
                <NotificationItem
                  key={item.id}
                  item={item}
                  unread={!seenIds.includes(item.id)}
                  onNavigate={close}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}