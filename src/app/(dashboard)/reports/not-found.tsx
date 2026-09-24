import { NotFoundView } from '@/components/datawise/not-found-view'

export default function ReportsNotFound() {
  return (
    <NotFoundView
      title="Reports page not found"
      description="The reports section you requested does not exist."
      backHref="/reports"
      backLabel="Back to reports"
    />
  )
}
