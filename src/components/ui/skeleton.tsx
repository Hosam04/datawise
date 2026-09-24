import { cn } from '@/lib/utils'

interface SkeletonProps extends React.ComponentProps<'div'> {}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-md bg-muted',
        'after:absolute after:inset-0 after:-translate-x-full after:animate-[shimmer_1.5s_ease-in-out_infinite] after:bg-linear-to-r after:from-transparent after:via-foreground/10 after:to-transparent',
        className,
      )}
      aria-hidden="true"
      {...props}
    />
  )
}
