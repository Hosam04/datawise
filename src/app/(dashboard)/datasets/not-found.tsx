import { NotFoundView } from '@/components/datawise/not-found-view'

export default function DatasetsNotFound() {
  return (
    <NotFoundView
      title="Datasets page not found"
      description="The datasets section you requested does not exist."
      backHref="/datasets"
      backLabel="Back to datasets"
    />
  )
}
