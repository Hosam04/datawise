'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import type { LucideIcon } from 'lucide-react'
import {
  emptyStatePresets,
  type EmptyStateVariant,
} from '@/lib/empty-state-presets'
import { focusRing } from '@/lib/ui-styles'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  variant?: EmptyStateVariant
  title?: string
  description?: string
  icon?: LucideIcon
  primaryAction?: { label: string; href: string; onClick?: () => void }
  secondaryAction?: { label: string; href: string; onClick?: () => void }
  className?: string
  /** @deprecated Use variant + presets instead */
  message?: string
  /** @deprecated Use primaryAction instead */
  actionLabel?: string
  /** @deprecated Use primaryAction instead */
  actionHref?: string
}

function EmptyStateAction({
  action,
  variant,
}: {
  action: { label: string; href: string; onClick?: () => void }
  variant: 'primary' | 'secondary'
}) {
  const className = cn(
    'inline-flex h-9 items-center justify-center rounded-lg px-4 text-sm font-medium transition-colors duration-200',
    focusRing,
    variant === 'primary'
      ? 'bg-primary text-primary-foreground hover:bg-primary/90'
      : 'border border-border bg-background text-foreground hover:bg-muted',
  )

  if (action.href === '#' && action.onClick) {
    return (
      <button type="button" onClick={action.onClick} className={className}>
        {action.label}
      </button>
    )
  }

  return (
    <Link href={action.href} onClick={action.onClick} className={className}>
      {action.label}
    </Link>
  )
}

export function EmptyState({
  variant = 'activity',
  title,
  description,
  icon,
  primaryAction,
  secondaryAction,
  className,
  message,
  actionLabel,
  actionHref,
}: EmptyStateProps) {
  const [mounted, setMounted] = useState(false)
  const preset = emptyStatePresets[variant]
  const Icon = icon ?? preset.icon
  const resolvedTitle = title ?? (message ? undefined : preset.title)
  const resolvedDescription =
    description ?? message ?? preset.description
  const resolvedPrimary =
    primaryAction ??
    (actionLabel || actionHref
      ? {
          label: actionLabel ?? preset.primaryAction.label,
          href: actionHref ?? preset.primaryAction.href,
        }
      : preset.primaryAction)
  const resolvedSecondary = secondaryAction ?? preset.secondaryAction

  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <div
      className={cn(
        'flex flex-col items-center rounded-xl border border-border bg-card px-6 py-10 text-center',
        mounted && 'animate-in fade-in zoom-in-95 duration-300',
        className,
      )}
    >
      <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10">
        <Icon className="size-7 text-primary" aria-hidden="true" />
      </div>

      {resolvedTitle && (
        <h3 className="mt-4 text-base font-semibold text-foreground">
          {resolvedTitle}
        </h3>
      )}

      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        {resolvedDescription}
      </p>

      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        <EmptyStateAction action={resolvedPrimary} variant="primary" />
        {resolvedSecondary && (
          <EmptyStateAction action={resolvedSecondary} variant="secondary" />
        )}
      </div>
    </div>
  )
}