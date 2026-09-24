'use client'

import Link from 'next/link'
import { FileSpreadsheet, FileText, Star, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { favoriteHref } from '@/lib/app-links'
import { useFavoriteStore } from '@/stores/favorite-store'

interface FavoriteCardProps {
  id: string
  name: string
  type: 'dataset' | 'report'
  description: string
}

export function FavoriteCard({
  id,
  name,
  type,
  description,
}: FavoriteCardProps) {
  const Icon = type === 'dataset' ? FileSpreadsheet : FileText
  const removeFavorite = useFavoriteStore((state) => state.removeFavorite)
  const href = favoriteHref(id, type)

  return (
    <div className="flex items-center justify-between rounded-xl border border-border bg-card p-5">
      <Link
        href={href}
        className="flex min-w-0 flex-1 items-center gap-4 transition-colors hover:opacity-80"
      >
        <div className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="size-5 text-primary" />
        </div>

        <div className="min-w-0">
          <h3 className="font-semibold">{name}</h3>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </Link>

      <div className="flex items-center gap-3">
        <Star className="size-5 fill-current text-primary" />

        <ConfirmDialog
          title="Remove from favorites?"
          description={`"${name}" will be removed from your favorites.`}
          confirmLabel="Remove"
          tooltip="Remove from favorites"
          onConfirm={() => {
            removeFavorite(id)
            toast.success('Removed from favorites', { description: name })
          }}
          trigger={
            <button
              type="button"
              aria-label={`Remove ${name} from favorites`}
              className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
            >
              <Trash2 className="size-4" />
            </button>
          }
        />
      </div>
    </div>
  )
}
