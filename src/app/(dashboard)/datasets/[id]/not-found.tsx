import { NotFoundView } from '@/components/datawise/not-found-view'

export default function DatasetNotFound() {
  return (
    <NotFoundView
      title="Dataset not found"
      description="This dataset may have been removed or does not exist."
      backHref="/datasets"
      backLabel="Back to datasets"
    />
  )
}
