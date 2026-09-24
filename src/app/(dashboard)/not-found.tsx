import { NotFoundView } from '@/components/datawise/not-found-view'

export default function DashboardNotFound() {
  return (
    <NotFoundView
      title="Page not found"
      description="This dashboard page does not exist."
      backHref="/"
      backLabel="Back to dashboard"
    />
  )
}
