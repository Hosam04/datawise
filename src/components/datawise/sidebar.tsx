'use client'

import { SidebarNav } from '@/components/datawise/sidebar-nav'

export function Sidebar() {
  return (
    <aside className="hidden w-20 shrink-0 border-r border-sidebar-border bg-sidebar md:flex">
      <SidebarNav variant="compact" className="w-full" />
    </aside>
  )
}
