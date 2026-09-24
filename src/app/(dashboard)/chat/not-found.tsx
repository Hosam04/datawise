import { NotFoundView } from '@/components/datawise/not-found-view'

export default function ChatNotFound() {
  return (
    <NotFoundView
      title="Chat not found"
      description="The chat session you requested could not be found."
      backHref="/chat"
      backLabel="Open chat"
    />
  )
}
