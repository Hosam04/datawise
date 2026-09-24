import { NotFoundView } from '@/components/datawise/not-found-view'

export default function UploadNotFound() {
  return (
    <NotFoundView
      title="Upload not found"
      description="The upload page you requested does not exist."
      backHref="/upload"
      backLabel="Back to upload"
    />
  )
}
