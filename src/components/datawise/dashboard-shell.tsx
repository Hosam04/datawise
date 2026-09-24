'use client'

import { useRef, useState, type ReactNode } from 'react'
import { Suspense } from 'react'
import { MobileSidebar } from '@/components/datawise/mobile-sidebar'
import { PageTransition } from '@/components/datawise/page-transition'
import { Sidebar } from '@/components/datawise/sidebar'
import { TopBar } from '@/components/datawise/top-bar'
import { GlobalSearchProvider } from '@/components/datawise/global-search-provider'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useRequireAuth } from '@/hooks/use-require-auth'
import { useServerDataHydration } from '@/hooks/use-store-hydration'

export function DashboardShell({ children }: { children: ReactNode }) {
  useRequireAuth()
  useServerDataHydration()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  return (
    <GlobalSearchProvider>
      <TooltipProvider>
        <div className="flex h-screen flex-col bg-background">
          <Suspense fallback={null}>
            <TopBar
              menuButtonRef={menuButtonRef}
              mobileNavOpen={mobileNavOpen}
              onOpenMobileNav={() => setMobileNavOpen(true)}
            />
          </Suspense>

          <MobileSidebar
            open={mobileNavOpen}
            onClose={() => setMobileNavOpen(false)}
            returnFocusRef={menuButtonRef}
          />

          <main className="flex min-h-0 flex-1">
            <Sidebar />

            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto">
              <PageTransition className="flex min-h-0 flex-1 flex-col">
                {children}
              </PageTransition>
            </div>
          </main>
        </div>
      </TooltipProvider>
    </GlobalSearchProvider>
  )
}
