import { UploadPanel } from '@/components/upload/upload-panel'
import { PageHeader } from '@/components/datawise/page-header'

export default function UploadPage() {
  return (
    <div className="h-full p-6">
      <PageHeader
        centered
        title="Upload Dataset"
        description="Upload CSV, Excel, or JSON files to start analyzing your data."
        className="mb-6"
      />

      <div className="mx-auto max-w-2xl">
        <UploadPanel />
      </div>
    </div>
  )
}
