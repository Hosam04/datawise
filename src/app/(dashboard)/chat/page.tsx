import { Suspense } from 'react'
import { ArtifactPanel } from '@/components/datawise/artifact-panel'
import { ChatPanel } from '@/components/datawise/chat-panel'

export default function ChatPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Suspense fallback={null}>
          <ChatPanel />
        </Suspense>
        <Suspense fallback={null}>
          <ArtifactPanel />
        </Suspense>
      </div>
    </div>
  )
}
