import Link from 'next/link'
import { FileQuestion } from 'lucide-react'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface NotFoundViewProps {
  title?: string
  description?: string
  backHref?: string
  backLabel?: string
  className?: string
}

export function NotFoundView({
  title = 'Page not found',
  description = 'The page you are looking for does not exist or may have been removed.',
  backHref = '/',
  backLabel = 'Back to dashboard',
  className,
}: NotFoundViewProps) {
  return (
    <div
      className={cn(
        'flex min-h-[420px] items-center justify-center p-6 animate-in fade-in slide-in-from-bottom-2 duration-300 motion-reduce:animate-none',
        className,
      )}
    >
      <div className="max-w-md rounded-xl border border-border bg-card p-8 text-center">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-muted">
          <FileQuestion className="size-7 text-muted-foreground" />
        </div>

        <h1 className="mt-4 text-2xl font-bold text-foreground">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {description}
        </p>

        <Link
          href={backHref}
          className={cn(buttonVariants({ variant: 'outline' }), 'mt-6')}
        >
          {backLabel}
        </Link>
      </div>
    </div>
  )
}
