'use client'

import { Suspense, useEffect, useState, type RefObject } from 'react'
import { BarChart3, Menu, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { DatasetSwitcher } from '@/components/datawise/dataset-switcher'
import { DatasetSwitcherSkeleton } from '@/components/datawise/card-skeleton'
import {
  GlobalSearchTrigger,
} from '@/components/datawise/global-search-provider'
import { NotificationsDropdown } from '@/components/datawise/notifications-dropdown'
import { UserMenu } from '@/components/datawise/user-menu'
import { IconTooltip } from '@/components/ui/tooltip'
import { focusRing } from '@/lib/ui-styles'
import { cn } from '@/lib/utils'

function DatasetSwitcherFallback() {
  return <DatasetSwitcherSkeleton />
}

interface TopBarProps {
  menuButtonRef?: RefObject<HTMLButtonElement | null>
  mobileNavOpen?: boolean
  onOpenMobileNav?: () => void
}

export function TopBar({
  menuButtonRef,
  mobileNavOpen = false,
  onOpenMobileNav,
}: TopBarProps) {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const id = window.requestAnimationFrame(() => setMounted(true))
    return () => window.cancelAnimationFrame(id)
  }, [])

  const isDark = mounted && resolvedTheme === 'dark'

  const toggleTheme = () => {
    setTheme(isDark ? 'light' : 'dark')
  }

  return (
    <header className="flex h-14 items-center justify-between gap-3 border-b border-border bg-card px-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          ref={menuButtonRef}
          type="button"
          onClick={onOpenMobileNav}
          aria-label="Open navigation menu"
          aria-controls="mobile-sidebar"
          aria-expanded={mobileNavOpen}
          className={cn(
            'flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden',
            focusRing,
          )}
        >
          <Menu className="size-5" />
        </button>

        <div className="flex min-w-0 items-center gap-2">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary">
            <BarChart3 className="size-4 text-primary-foreground" aria-hidden="true" />
          </div>
          <span className="hidden truncate text-lg font-bold text-foreground min-[420px]:inline">
            DataWise
          </span>
        </div>

        <Suspense fallback={<DatasetSwitcherFallback />}>
          <div className="min-w-0 flex-1 sm:flex-initial sm:max-w-[220px]">
            <DatasetSwitcher />
          </div>
        </Suspense>

        <GlobalSearchTrigger variant="bar" className="mx-1 hidden lg:flex" />
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <GlobalSearchTrigger variant="icon" />

        <IconTooltip
          label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          disabled={!mounted}
          onClick={toggleTheme}
          className="flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
        >
          {isDark ? (
            <Sun className="size-4.5" aria-hidden="true" />
          ) : (
            <Moon className="size-4.5" aria-hidden="true" />
          )}
        </IconTooltip>

        <NotificationsDropdown />
        <UserMenu />
      </div>
    </header>
  )
}
