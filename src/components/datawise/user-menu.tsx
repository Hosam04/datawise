'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { LogOut, Settings, User } from 'lucide-react'
import { IconTooltip } from '@/components/ui/tooltip'
import { useEscapeKey } from '@/hooks/use-escape-key'
import { avatarUrl } from '@/lib/api'
import { focusRing, iconButtonHover } from '@/lib/ui-styles'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'
import { clearAllAppData } from '@/lib/app-data'

export function UserMenu() {
  const router = useRouter()
  const { user, logout } = useAuthStore()
  const containerRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const close = useCallback(() => setOpen(false), [])

  useEscapeKey(close, open)

  const handleLogout = useCallback(async () => {
    try {
      // Clear auth + local UI caches. Server-side datasets/favorites/cleaning
      // data remain in PostgreSQL and are reloaded via hydrateUserDataFromServer
      // on the next login — so logout no longer permanently loses work.
      logout()
      clearAllAppData()
      close()
      router.push('/login')
    } catch (error) {
      console.error('Logout error:', error)
      router.push('/login')
    }
  }, [close, router, logout])

  // EARLY RETURN MUST BE PLACED AFTER ALL HOOKS
  if (!user) return null

  return (
    <div ref={containerRef} className="relative">
      <IconTooltip
        label="Account menu"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="ml-1 flex size-8 items-center justify-center overflow-hidden rounded-full bg-accent transition-opacity hover:opacity-90"
      >
        {avatarUrl(user?.picture) ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={avatarUrl(user?.picture)}
            alt=""
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="text-sm font-semibold text-accent-foreground">
            {user?.name?.[0] ?? 'D'}
          </span>
        )}
      </IconTooltip>

      {open && (
        <div
          role="menu"
          className="absolute top-full right-0 z-50 mt-2 w-56 overflow-hidden rounded-xl border border-border bg-card shadow-lg"
        >
          <div className="border-b border-border px-4 py-3">
            <p className="text-sm font-semibold text-foreground">{user?.name ?? 'User'}</p>
            <p className="text-xs text-muted-foreground">{user?.email ?? 'user@example.com'}</p>
          </div>

          <div className="p-1">
            <Link
              href="/profile"
              role="menuitem"
              onClick={close}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-foreground',
                iconButtonHover,
                focusRing,
              )}
            >
              <User className="size-4 text-muted-foreground" />
              Profile
            </Link>

            <Link
              href="/settings"
              role="menuitem"
              onClick={close}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-foreground',
                iconButtonHover,
                focusRing,
              )}
            >
              <Settings className="size-4 text-muted-foreground" />
              Settings
            </Link>

            <button
              type="button"
              role="menuitem"
              onClick={handleLogout}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-destructive transition-colors duration-200 hover:bg-destructive/10',
                focusRing,
              )}
            >
              <LogOut className="size-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}