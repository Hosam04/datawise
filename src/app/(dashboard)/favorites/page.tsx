'use client'

import { FavoriteCard } from '@/components/favorites/favorite-card'
import { AnimatedList } from '@/components/datawise/animated-list'
import { ListCardSkeletonGroup } from '@/components/datawise/card-skeleton'
import { EmptyState } from '@/components/datawise/empty-state'
import { PageHeader } from '@/components/datawise/page-header'
import { useFavoriteStoreHydration } from '@/hooks/use-store-hydration'
import { useFavoriteStore } from '@/stores/favorite-store'

export default function FavoritesPage() {
  const hydrated = useFavoriteStoreHydration()
  const favorites = useFavoriteStore((state) => state.favorites)

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Favorites"
        description="Your saved datasets and reports."
      />

      {!hydrated ? (
        <ListCardSkeletonGroup count={3} spacing="md" padding="md" />
      ) : favorites.length === 0 ? (
        <EmptyState variant="favorites" />
      ) : (
        <AnimatedList className="space-y-4">
          {favorites.map((item) => (
            <FavoriteCard
              key={item.id}
              id={item.id}
              name={item.name}
              type={item.type}
              description={item.description}
            />
          ))}
        </AnimatedList>
      )}
    </div>
  )
}
