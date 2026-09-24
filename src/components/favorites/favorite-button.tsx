'use client'

import { Star } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { IconTooltip } from '@/components/ui/tooltip'
import { useFavoriteStore } from '@/stores/favorite-store'
import type { FavoriteItem } from '@/stores/favorite-store'

interface FavoriteButtonProps {
  item: FavoriteItem
  className?: string
  showLabel?: boolean
}

export function FavoriteButton({
  item,
  className,
  showLabel = false,
}: FavoriteButtonProps) {
  const toggleFavorite = useFavoriteStore((state) => state.toggleFavorite)
  const isFavorite = useFavoriteStore((state) => state.isFavorite(item.id))

  const handleToggle = () => {
    toggleFavorite(item)

    if (isFavorite) {
      toast.success('Removed from favorites', {
        description: item.name,
      })
    } else {
      toast.success('Added to favorites', {
        description: item.name,
      })
    }
  }

  const label = isFavorite
    ? `Remove ${item.name} from favorites`
    : `Add ${item.name} to favorites`

  if (showLabel) {
    return (
      <button
        type="button"
        onClick={handleToggle}
        aria-label={
          isFavorite
            ? `Remove ${item.name} from favorites`
            : `Add ${item.name} to favorites`
        }
        aria-pressed={isFavorite}
        className={cn(
          'inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted',
          isFavorite && 'border-primary/30 bg-primary/5 text-primary',
          className,
        )}
      >
        <Star className={cn('size-4', isFavorite && 'fill-current')} />
        {isFavorite ? 'Saved to Favorites' : 'Add to Favorites'}
      </button>
    )
  }

  return (
    <IconTooltip
      label={label}
      onClick={handleToggle}
      aria-pressed={isFavorite}
      side="top"
      className={cn(
        'rounded-lg p-2 transition-colors hover:bg-muted',
        isFavorite ? 'text-primary' : 'text-muted-foreground',
        className,
      )}
    >
      <Star className={cn('size-4', isFavorite && 'fill-current')} />
    </IconTooltip>
  )
}
