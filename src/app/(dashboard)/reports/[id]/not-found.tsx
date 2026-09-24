import { NotFoundView } from '@/components/datawise/not-found-view'

export default function ReportNotFound() {
  return (
    <NotFoundView
      title="Report not found"
      description="This report may have been removed or does not exist."
      backHref="/reports"
      backLabel="Back to reports"
    />
  )
}
