import { NotFoundView } from '@/components/datawise/not-found-view'

export default function ProfileNotFound() {
  return (
    <NotFoundView
      title="Profile not found"
      description="The profile page you requested does not exist."
      backHref="/profile"
      backLabel="Back to profile"
    />
  )
}