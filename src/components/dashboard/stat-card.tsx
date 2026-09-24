'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import type { LucideIcon } from 'lucide-react'
import { TrendingDown, TrendingUp } from 'lucide-react'
import { cardHover, focusRing } from '@/lib/ui-styles'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton' // تأكد من استيراد Skeleton

interface StatCardProps {
  label: string
  value: string | number
  icon?: LucideIcon
  href?: string
  trend?: 'up' | 'down' | 'neutral'
  change?: string
  className?: string
  isLoading?: boolean
}

// قمنا بتعديل المكون ليقبل حالة التحميل
export function StatCard({
  label,
  value,
  icon: Icon,
  href,
  trend,
  change,
  className,
  isLoading,
}: StatCardProps) {
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const containerClassName = cn(
    'rounded-xl border border-border bg-card p-5 transition-all',
    href && !isLoading ? cn('block hover:shadow-md', cardHover, focusRing) : '',
    className,
  )

  // إذا كنا في حالة تحميل، نرسم محتوى الـ Skeleton بدلاً من المحتوى الفعلي
  if (isLoading || !isMounted) {
    return (
      <div className={containerClassName} aria-hidden="true">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-12" />
          </div>
          <Skeleton className="size-10 rounded-lg" />
        </div>
      </div>
    )
  }

  // المحتوى الفعلي
  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="mt-2 text-3xl font-bold text-foreground">{value}</div>
        </div>
        {Icon && (
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
            <Icon className="size-5 text-primary" />
          </div>
        )}
      </div>
      {change && (
        <div className="mt-3 flex items-center gap-1 text-xs font-medium">
          {trend === 'up' && <TrendingUp className="size-3.5 text-emerald-600 dark:text-emerald-400" />}
          {trend === 'down' && <TrendingDown className="size-3.5 text-amber-600 dark:text-amber-400" />}
          <span className={cn(
              trend === 'up' && 'text-emerald-600 dark:text-emerald-400',
              trend === 'down' && 'text-amber-600 dark:text-amber-400',
              (!trend || trend === 'neutral') && 'text-muted-foreground',
          )}>
            {change}
          </span>
        </div>
      )}
    </>
  )

  if (href) {
    return (
      <Link href={href} className={containerClassName} prefetch={false}>
        {content}
      </Link>
    )
  }

  return <div className={containerClassName}>{content}</div>
}