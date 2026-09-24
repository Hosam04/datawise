import { NotFoundView } from '@/components/datawise/not-found-view'

export default function FavoritesNotFound() {
  return (
    <NotFoundView
      title="Favorites not found"
      description="The favorites page you requested does not exist."
      backHref="/favorites"
      backLabel="Back to favorites"
    />
  )
}
