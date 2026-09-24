'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { sidebarNavItems, sidebarSettingsItem } from '@/lib/sidebar-nav'
import { focusRing, iconButtonHover } from '@/lib/ui-styles'
import { isNavActive } from '@/lib/app-links'
import { cn } from '@/lib/utils'

interface SidebarNavProps {
  variant?: 'compact' | 'drawer'
  onNavigate?: () => void
  className?: string
  animateItems?: boolean
}

export function SidebarNav({
  variant = 'compact',
  onNavigate,
  className,
  animateItems = false,
}: SidebarNavProps) {
  const pathname = usePathname()
  const isDrawer = variant === 'drawer'
  const SettingsIcon = sidebarSettingsItem.icon

  const linkClassName = (isActive: boolean) =>
    cn(
      'rounded-lg text-xs transition-colors duration-200',
      focusRing,
      isDrawer
        ? cn(
            'flex w-full items-center gap-3 px-3 py-2.5 text-sm',
            isActive
              ? 'bg-sidebar-accent text-sidebar-accent-foreground'
              : cn('text-muted-foreground', iconButtonHover),
          )
        : cn(
            'flex w-16 flex-col items-center gap-1 px-2 py-2',
            isActive
              ? 'bg-sidebar-accent text-sidebar-accent-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          ),
    )

  return (
    <nav
      aria-label="Main navigation"
      className={cn(
        isDrawer
          ? 'flex h-full flex-col justify-between p-4'
          : 'flex h-full flex-col items-center justify-between py-4',
        className,
      )}
    >
      <ul className={cn(isDrawer ? 'space-y-1' : 'flex flex-col items-center gap-2')}>
        {sidebarNavItems.map((item, index) => {
          const Icon = item.icon
          const isActive = isNavActive(pathname, item.href)

          return (
            <li
              key={item.id}
              className={cn(
                animateItems &&
                  'animate-in fade-in slide-in-from-left-2 duration-300 motion-reduce:animate-none',
              )}
              style={
                animateItems
                  ? {
                      animationDelay: `${index * 40}ms`,
                      animationFillMode: 'both',
                    }
                  : undefined
              }
            >
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={isActive ? 'page' : undefined}
                className={linkClassName(isActive)}
              >
                <Icon className={isDrawer ? 'size-5 shrink-0' : 'size-5'} />
                <span>{item.label}</span>
              </Link>
            </li>
          )
        })}
      </ul>

      <Link
        href={sidebarSettingsItem.href}
        onClick={onNavigate}
        aria-current={
          pathname === sidebarSettingsItem.href ? 'page' : undefined
        }
        className={cn(
          linkClassName(pathname === sidebarSettingsItem.href),
          animateItems &&
            'animate-in fade-in slide-in-from-left-2 duration-300 motion-reduce:animate-none',
        )}
        style={
          animateItems
            ? {
                animationDelay: `${sidebarNavItems.length * 40}ms`,
                animationFillMode: 'both',
              }
            : undefined
        }
      >
        <SettingsIcon className={isDrawer ? 'size-5 shrink-0' : 'size-5'} />
        <span>{sidebarSettingsItem.label}</span>
      </Link>
    </nav>
  )
}
