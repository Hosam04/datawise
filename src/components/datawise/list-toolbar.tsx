'use client'

import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ListSearchProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

export function ListSearch({
  value,
  onChange,
  placeholder = 'Search...',
  className,
}: ListSearchProps) {
  return (
    <div className={cn('relative', className)}>
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-border bg-background py-2 pr-3 pl-9 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
      />
    </div>
  )
}

export interface FilterOption {
  value: string
  label: string
}

interface ListFilterProps {
  value: string
  onChange: (value: string) => void
  options: FilterOption[]
  label?: string
}

export function ListFilter({
  value,
  onChange,
  options,
  label = 'Filter',
}: ListFilterProps) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
            className={cn(
              'rounded-lg px-3 py-1.5 text-sm transition-colors',
              value === option.value
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

interface ListSortProps {
  value: string
  onChange: (value: string) => void
  options: FilterOption[]
  label?: string
}

export function ListSort({
  value,
  onChange,
  options,
  label = 'Sort by',
}: ListSortProps) {
  return (
    <div className="space-y-2">
      <label
        htmlFor="list-sort"
        className="text-sm font-medium text-muted-foreground"
      >
        {label}
      </label>
      <select
        id="list-sort"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:ring-2 focus:ring-ring sm:w-auto"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}

interface ListToolbarProps {
  search?: string
  onSearchChange?: (value: string) => void
  searchPlaceholder?: string
  filter?: string
  onFilterChange?: (value: string) => void
  filterOptions?: FilterOption[]
  filterLabel?: string
  sort?: string
  onSortChange?: (value: string) => void
  sortOptions?: FilterOption[]
  sortLabel?: string
}

export function ListToolbar({
  search,
  onSearchChange,
  searchPlaceholder,
  filter,
  onFilterChange,
  filterOptions,
  filterLabel,
  sort,
  onSortChange,
  sortOptions,
  sortLabel,
}: ListToolbarProps) {
  const showSearch = search !== undefined && onSearchChange !== undefined
  const showFilter =
    filter !== undefined &&
    onFilterChange !== undefined &&
    filterOptions !== undefined
  const showSort =
    sort !== undefined && onSortChange !== undefined && sortOptions !== undefined

  if (!showSearch && !showFilter && !showSort) return null

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-4">
      {showSearch && (
        <ListSearch
          value={search}
          onChange={onSearchChange}
          placeholder={searchPlaceholder}
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {showFilter && (
          <ListFilter
            value={filter}
            onChange={onFilterChange}
            options={filterOptions}
            label={filterLabel}
          />
        )}

        {showSort && (
          <ListSort
            value={sort}
            onChange={onSortChange}
            options={sortOptions}
            label={sortLabel}
          />
        )}
      </div>
    </div>
  )
}
