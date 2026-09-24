'use client'

import { useEffect, useRef, type RefObject } from 'react'
import { X } from 'lucide-react'
import { SidebarNav } from '@/components/datawise/sidebar-nav'
import { useEscapeKey } from '@/hooks/use-escape-key'
import { useFocusTrap } from '@/hooks/use-focus-trap'
import { focusRing } from '@/lib/ui-styles'
import { cn } from '@/lib/utils'

interface MobileSidebarProps {
  open: boolean
  onClose: () => void
  returnFocusRef?: RefObject<HTMLElement | null>
}

export function MobileSidebar({
  open,
  onClose,
  returnFocusRef,
}: MobileSidebarProps) {
  const asideRef = useRef<HTMLElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEscapeKey(onClose, open)
  useFocusTrap(asideRef, open)

  useEffect(() => {
    if (!open) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()
    const returnFocusElement = returnFocusRef?.current

    return () => {
      document.body.style.overflow = previousOverflow
      returnFocusElement?.focus()
    }
  }, [open, returnFocusRef])

  return (
    <>
      <div
        aria-hidden={!open}
        className={cn(
          'fixed inset-0 z-40 bg-black/50 md:hidden',
          open
            ? 'animate-in fade-in duration-200 motion-reduce:animate-none'
            : 'pointer-events-none opacity-0 transition-opacity duration-200',
        )}
        onClick={onClose}
      />

      <aside
        ref={asideRef}
        id="mobile-sidebar"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
        aria-hidden={!open}
        inert={!open ? true : undefined}
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-72 border-r border-sidebar-border bg-sidebar shadow-xl md:hidden',
          open
            ? 'animate-in slide-in-from-left duration-300 ease-out motion-reduce:animate-none'
            : 'pointer-events-none -translate-x-full transition-transform duration-300 ease-out',
        )}
      >
        <div className="flex items-center justify-between border-b border-sidebar-border px-4 py-3">
          <span className="text-sm font-semibold text-foreground">Navigation</span>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close navigation menu"
            className={cn(
              'flex size-9 items-center justify-center rounded-lg text-muted-foreground',
              focusRing,
              'hover:bg-muted hover:text-foreground',
            )}
          >
            <X className="size-5" />
          </button>
        </div>

        <SidebarNav variant="drawer" onNavigate={onClose} animateItems={open} />
      </aside>
    </>
  )
}
