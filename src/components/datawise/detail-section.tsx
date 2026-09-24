import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DetailSectionProps {
  title: string
  description?: string
  children: ReactNode
  className?: string
}

export function DetailSection({
  title,
  description,
  children,
  className,
}: DetailSectionProps) {
  return (
    <section className={cn('rounded-xl border border-border bg-card p-6', className)}>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </section>
  )
}

interface MetadataItemProps {
  label: string
  value: string
}

export function MetadataGrid({ items }: { items: MetadataItemProps[] }) {
  return (
    <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-border bg-background p-4"
        >
          <dt className="text-sm text-muted-foreground">{item.label}</dt>
          <dd className="mt-1 break-words font-medium text-foreground">
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

interface ActionBarProps {
  children: ReactNode
  className?: string
}

export function ActionBar({ children, className }: ActionBarProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-4',
        className,
      )}
    >
      {children}
    </div>
  )
}
