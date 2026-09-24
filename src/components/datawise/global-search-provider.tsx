'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useRouter } from 'next/navigation'
import { Command } from 'cmdk'
import {
  Database,
  FileText,
  LayoutDashboard,
  MessageSquare,
  Search,
  Settings,
  Star,
  Upload,
} from 'lucide-react'
import {
  buildChatDatasetSearchItems,
  buildDatasetSearchItems,
  buildFavoriteSearchItems,
  buildReportSearchItems,
  getGlobalSearchValue,
  globalSearchPages,
  groupSearchItems,
  type GlobalSearchGroup,
  type GlobalSearchItem,
} from '@/lib/global-search'
import { focusRing } from '@/lib/ui-styles'
import { cn } from '@/lib/utils'
import { useDatasetStore } from '@/stores/dataset-store'
import { useFavoriteStore } from '@/stores/favorite-store'
import { useReportStore } from '@/stores/report-store'
import { IconTooltip } from '@/components/ui/tooltip'

interface GlobalSearchContextValue {
  open: boolean
  openSearch: () => void
  closeSearch: () => void
  toggleSearch: () => void
}

const GlobalSearchContext = createContext<GlobalSearchContextValue | null>(null)

export function useGlobalSearch() {
  const context = useContext(GlobalSearchContext)

  if (!context) {
    throw new Error('useGlobalSearch must be used within GlobalSearchProvider')
  }

  return context
}

const groupIcons: Record<GlobalSearchGroup, typeof Database> = {
  Pages: LayoutDashboard,
  Datasets: Database,
  Reports: FileText,
  Favorites: Star,
}

const pageIcons: Record<string, typeof Database> = {
  'page-home': LayoutDashboard,
  'page-chat': MessageSquare,
  'page-upload': Upload,
  'page-datasets': Database,
  'page-reports': FileText,
  'page-favorites': Star,
  'page-settings': Settings,
}

function SearchResultIcon({ item }: { item: GlobalSearchItem }) {
  const Icon =
    pageIcons[item.id] ??
    (item.id.startsWith('chat-') ? MessageSquare : groupIcons[item.group])

  return (
    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
      <Icon className="size-4 text-primary" />
    </div>
  )
}

function GlobalSearchDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const router = useRouter()
  const datasets = useDatasetStore((state) => state.datasets)
  const reports = useReportStore((state) => state.reports)
  const favorites = useFavoriteStore((state) => state.favorites)

  const searchItems = useMemo(
    () => [
      ...globalSearchPages,
      ...buildDatasetSearchItems(datasets),
      ...buildChatDatasetSearchItems(datasets),
      ...buildReportSearchItems(reports),
      ...buildFavoriteSearchItems(favorites),
    ],
    [datasets, reports, favorites],
  )

  const groupedItems = useMemo(
    () => groupSearchItems(searchItems),
    [searchItems],
  )

  const handleSelect = (href: string) => {
    onOpenChange(false)
    router.push(href)
  }

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Global search"
      overlayClassName="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
      contentClassName={cn(
        'fixed top-[15%] left-1/2 z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-card shadow-2xl',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
      )}
    >
      <div className="flex items-center border-b border-border px-3">
        <Search className="size-4 shrink-0 text-muted-foreground" />
        <Command.Input
          placeholder="Search pages, datasets, reports, favorites..."
          className="flex h-12 w-full bg-transparent px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
      </div>

      <Command.List className="max-h-90 overflow-y-auto p-2">
        <Command.Empty className="px-3 py-8 text-center text-sm text-muted-foreground">
          No results found.
        </Command.Empty>

        {groupedItems.map(({ group, items }) => (
          <Command.Group
            key={group}
            heading={group}
className="overflow-hidden px-1 py-1 **:[[cmdk-group-heading]]:px-2 **:[[cmdk-group-heading]]:py-1.5 **:[[cmdk-group-heading]]:text-xs **:[[cmdk-group-heading]]:font-medium **:[[cmdk-group-heading]]:text-muted-foreground"          >
            {items.map((item) => (
              <Command.Item
                key={item.id}
                value={getGlobalSearchValue(item)}
                onSelect={() => handleSelect(item.href)}
                className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2.5 text-sm outline-none data-[selected=true]:bg-muted"
              >
                <SearchResultIcon item={item} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-foreground">
                    {item.title}
                  </p>
                  {item.subtitle && (
                    <p className="truncate text-xs text-muted-foreground">
                      {item.subtitle}
                    </p>
                  )}
                </div>
              </Command.Item>
            ))}
          </Command.Group>
        ))}
      </Command.List>

      <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
        ↑↓ Navigate · Enter Open · Esc Close · Ctrl+K Toggle
      </div>
    </Command.Dialog>
  )
}

export function GlobalSearchProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)

  const openSearch = useCallback(() => setOpen(true), [])
  const closeSearch = useCallback(() => setOpen(false), [])
  const toggleSearch = useCallback(() => setOpen((current) => !current), [])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== 'k') return
      if (!(event.metaKey || event.ctrlKey)) return

      event.preventDefault()
      toggleSearch()
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [toggleSearch])

  const value = useMemo(
    () => ({ open, openSearch, closeSearch, toggleSearch }),
    [open, openSearch, closeSearch, toggleSearch],
  )

  return (
    <GlobalSearchContext.Provider value={value}>
      {children}
      <GlobalSearchDialog open={open} onOpenChange={setOpen} />
    </GlobalSearchContext.Provider>
  )
}

export function GlobalSearchTrigger({
  variant = 'icon',
  className,
}: {
  variant?: 'icon' | 'bar'
  className?: string
}) {
  const { openSearch } = useGlobalSearch()

  if (variant === 'bar') {
    return (
      <button
        type="button"
        onClick={openSearch}
        aria-label="Open global search"
        className={cn(
          'hidden h-9 min-w-99 max-w-sm flex-1 items-center gap-2 rounded-lg border border-border bg-background px-3 text-sm text-muted-foreground transition-colors duration-200 hover:bg-muted/60 lg:min-w-99',
          focusRing,
          className,
        )}
      >
        <Search className="size-4 shrink-0" />
        <span className="truncate">Search DataWise...</span>
        <kbd className="ml-auto hidden rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium lg:inline">
          Ctrl+K
        </kbd>
      </button>
    )
  }

  return (
    <IconTooltip
      label="Search (Ctrl+K)"
      onClick={openSearch}
      className={cn(
        'flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:hidden',
        className,
      )}
    >
      <Search className="size-4.5" aria-hidden="true" />
    </IconTooltip>
  )
}
