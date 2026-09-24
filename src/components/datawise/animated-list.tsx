import { Children, isValidElement, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface AnimatedListProps {
  children: ReactNode
  className?: string
  itemClassName?: string
  staggerMs?: number
}

export function AnimatedList({
  children,
  className,
  itemClassName,
  staggerMs = 45,
}: AnimatedListProps) {
  const items = Children.toArray(children).filter(isValidElement)

  return (
    <div className={cn('space-y-3', className)}>
      {items.map((child, index) => (
        <div
          key={child.key ?? index}
          className={cn(
            'animate-in fade-in slide-in-from-bottom-1 duration-300 motion-reduce:animate-none',
            itemClassName,
          )}
          style={{
            animationDelay: `${index * staggerMs}ms`,
            animationFillMode: 'both',
          }}
        >
          {child}
        </div>
      ))}
    </div>
  )
}
