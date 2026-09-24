'use client'

import ReactMarkdown from 'react-markdown'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
  ChevronDown,
  Database,
  MessageSquare,
  SendHorizontal,
  Sparkles,
  Upload,
  User,
} from 'lucide-react'
import { formatMessageTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { IconTooltip } from '@/components/ui/tooltip'
import { useDatasetStore } from '@/stores/dataset-store'
import { useWorkspaceStore } from '@/stores/workspace-store'
import { useChatStore } from '@/stores/chat-store'
import { chatWithDataset, getDatasetArtifacts } from '@/lib/api'
import type { ChatMessage as Message } from '@/types/chat'


const SCROLL_THRESHOLD = 80

function renderMessageContent(content: unknown) {
  if (typeof content === 'string') {
    return content
  }

  if (
    typeof content === 'object' &&
    content !== null &&
    'text' in content
  ) {
    return String(content.text)
  }

  return JSON.stringify(content)
}

function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  const content = renderMessageContent(message.content)

  return (
    <div
      className={cn(
        'flex gap-2.5',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <div
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-full',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-primary/10 text-primary',
        )}
        aria-hidden="true"
      >
        {isUser ? (
          <User className="size-4" />
        ) : (
          <Sparkles className="size-4" />
        )}
      </div>

      <div
        className={cn(
          'flex max-w-[80%] flex-col gap-1',
          isUser ? 'items-end' : 'items-start',
        )}
      >
        <div
          className={cn(
            'rounded-xl px-4 py-2.5 text-sm leading-relaxed',
            isUser
              ? 'rounded-tr-sm bg-primary text-primary-foreground'
              : 'rounded-tl-sm bg-muted text-foreground',
          )}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap">
              {content}
            </div>
          ) : (
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown
                components={{
                  h1: ({ children }) => (
                    <h1 className="mb-3 mt-1 text-base font-bold">
                      {children}
                    </h1>
                  ),

                  h2: ({ children }) => (
                    <h2 className="mb-2 mt-4 text-sm font-bold">
                      {children}
                    </h2>
                  ),

                  h3: ({ children }) => (
                    <h3 className="mb-2 mt-3 text-sm font-semibold">
                      {children}
                    </h3>
                  ),

                  p: ({ children }) => (
                    <p className="mb-3 last:mb-0">
                      {children}
                    </p>
                  ),

                  ul: ({ children }) => (
                    <ul className="mb-3 list-disc space-y-1 pl-5">
                      {children}
                    </ul>
                  ),

                  ol: ({ children }) => (
                    <ol className="mb-3 list-decimal space-y-1 pl-5">
                      {children}
                    </ol>
                  ),

                  li: ({ children }) => (
                    <li>{children}</li>
                  ),

                  strong: ({ children }) => (
                    <strong className="font-semibold">
                      {children}
                    </strong>
                  ),

                  code: ({ children }) => (
                    <code className="rounded bg-background/60 px-1 py-0.5 text-xs">
                      {children}
                    </code>
                  ),

                  blockquote: ({ children }) => (
                    <blockquote className="my-3 border-l-2 pl-3">
                      {children}
                    </blockquote>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        <time
          dateTime={new Date(message.createdAt).toISOString()}
          className="px-1 text-[11px] text-muted-foreground"
        >
          {formatMessageTime(message.createdAt)}
        </time>
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-2.5">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Sparkles className="size-4" aria-hidden="true" />
      </div>

      <div className="rounded-xl rounded-tl-sm bg-muted px-4 py-3">
        <div className="flex items-center gap-1">
          <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:0ms]" />
          <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:150ms]" />
          <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  )
}

function NoDatasetState() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-4 text-center">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-muted">
        <Database className="size-7 text-muted-foreground" />
      </div>

      <h3 className="mt-4 text-base font-semibold text-foreground">
        No dataset selected
      </h3>

      <p className="mt-2 max-w-60 text-sm text-muted-foreground">
        Select a dataset from the top bar or upload a new file to start chatting.
      </p>

      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <Link
          href="/datasets"
          className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-background px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted"
        >
          Browse datasets
        </Link>

        <Link
          href="/upload"
          className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Upload className="size-4" />
          Upload file
        </Link>
      </div>
    </div>
  )
}

function WelcomeState({ datasetName }: { datasetName: string }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-4 text-center">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10">
        <MessageSquare className="size-7 text-primary" />
      </div>

      <h3 className="mt-4 text-base font-semibold text-foreground">
        Ask DataWise anything
      </h3>

      <p className="mt-2 max-w-65 text-sm text-muted-foreground">
        Start a conversation about{' '}
        <span className="font-medium text-foreground">{datasetName}</span>.
        Ask about trends, comparisons, outliers, or anything in the data.
      </p>
    </div>
  )
}

export function ChatPanel() {
  const searchParams = useSearchParams()
  const urlDatasetId = searchParams.get('dataset')
  const activeDatasetId = useWorkspaceStore((state) => state.activeDatasetId)
  const datasets = useDatasetStore((state) => state.datasets)
  const setDatasetArtifacts = useDatasetStore(
    (state) => state.setDatasetArtifacts,
  )

  const resolvedDatasetId = urlDatasetId ?? activeDatasetId
  const activeDataset = datasets.find(
    (dataset) => dataset.id === resolvedDatasetId,
  )
  const hasDataset = Boolean(activeDataset)
  const isChatReady = activeDataset?.status === 'Analyzed'

  const messagesBySession = useChatStore((state) => state.messagesBySession)
  const addMessage = useChatStore((state) => state.addMessage)
  const isSending = useChatStore((state) => state.isSending)
  const setSending = useChatStore((state) => state.setSending)
  const setChatError = useChatStore((state) => state.setError)

  const messages: Message[] = (resolvedDatasetId ? messagesBySession[resolvedDatasetId] : undefined) ?? []
  const [input, setInput] = useState('')
  const [showScrollButton, setShowScrollButton] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const inputRef = useRef<HTMLInputElement>(null)

  const isNearBottom = useCallback((container: HTMLDivElement) => {
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight

    return distanceFromBottom <= SCROLL_THRESHOLD
  }, [])

  const updateScrollState = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container) return

    const atBottom = isNearBottom(container)
    isAtBottomRef.current = atBottom
    setShowScrollButton(!atBottom)
  }, [isNearBottom])

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    const container = scrollContainerRef.current
    if (!container) return

    container.scrollTo({
      top: container.scrollHeight,
      behavior,
    })

    isAtBottomRef.current = true
    setShowScrollButton(false)
  }

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    container.addEventListener('scroll', updateScrollState, { passive: true })
    updateScrollState()

    return () => container.removeEventListener('scroll', updateScrollState)
  }, [messages.length, isSending, hasDataset, updateScrollState])

  useLayoutEffect(() => {
    if (!isAtBottomRef.current) return

    const container = scrollContainerRef.current
    if (!container) return

    container.scrollTop = container.scrollHeight
    setShowScrollButton(false)
  }, [messages, isSending])

  const focusInput = () => {
    queueMicrotask(() => inputRef.current?.focus())
  }

  useEffect(() => {
    if (hasDataset) {
      focusInput()
    }
  }, [hasDataset])

  useEffect(() => {
    if (!isSending && hasDataset) {
      focusInput()
    }
  }, [isSending, hasDataset])

  const handleSend = async () => {
    if (!input.trim() || !isChatReady || isSending || !activeDataset || !resolvedDatasetId) return

    const container = scrollContainerRef.current
    const shouldStickToBottom = container ? isNearBottom(container) : true
    const messageContent = input.trim()

    setInput('')
    setSending(true)
    addMessage(resolvedDatasetId, {
      role: 'user',
      content: messageContent,
    })

    isAtBottomRef.current = shouldStickToBottom
    focusInput()

    try {
      const result = await chatWithDataset(resolvedDatasetId, messageContent)
      setSending(false)
      addMessage(resolvedDatasetId, {
        role: 'ai',
        content: result.answer,
      })

      // If chat generated a new chart (generate_chart tool), re-fetch artifacts
      // so the Charts tab shows the appended chart without a full page reload.
      try {
        const artifacts = await getDatasetArtifacts(resolvedDatasetId)
        if (artifacts.status === 'completed') {
          setDatasetArtifacts(resolvedDatasetId, artifacts)
        }
      } catch (refreshError) {
        // Chat reply already succeeded; artifact refresh is best-effort.
        console.warn('Failed to refresh artifacts after chat:', refreshError)
      }
    } catch (err: unknown) {
      setSending(false)
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setChatError(errorMsg)
      addMessage(resolvedDatasetId, {
        role: 'ai',
        content: 'Sorry, I encountered an error. Please try again.',
      })
      console.error(err)
    }
  }

  return (
    <section className="flex h-full min-h-0 w-80 shrink-0 flex-col overflow-hidden border-r border-border bg-card lg:w-96">
      <div className="shrink-0 border-b border-border px-5 py-4">
        <h2 className="text-lg font-semibold text-foreground">Chat</h2>
        <p className="mt-1 truncate text-sm text-muted-foreground">
          {activeDataset
            ? activeDataset.name
            : 'Select a dataset to begin'}
        </p>
      </div>

      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
        <div
          ref={scrollContainerRef}
          className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-5 py-5"
        >
          {!hasDataset ? (
            <NoDatasetState />
          ) : messages.length === 0 && !isSending ? (
            <WelcomeState datasetName={activeDataset!.name} />
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}

              {isSending && <TypingIndicator />}
            </div>
          )}
        </div>

        {showScrollButton && (
          <IconTooltip
            label="Scroll to bottom"
            onClick={() => scrollToBottom('smooth')}
            side="top"
            className="absolute bottom-4 left-1/2 z-10 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border border-border bg-card text-foreground shadow-md transition-colors hover:bg-muted"
          >
            <ChevronDown className="size-4" />
          </IconTooltip>
        )}
      </div>

      <div
        className={cn(
          'shrink-0 border-t border-border p-4',
          !hasDataset && 'opacity-60',
        )}
      >
        <div className="flex gap-2">
          <input
            ref={inputRef}
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed"
            placeholder={
              !hasDataset
                ? 'Select a dataset to chat'
                : !isChatReady
                  ? 'Analysis must complete before chat'
                  : 'Ask anything about your data...'
            }
            value={input}
            disabled={!isChatReady}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                handleSend()
              }
            }}
          />

          <IconTooltip
            label="Send message"
            onMouseDown={(event) => event.preventDefault()}
            onClick={handleSend}
            disabled={!isChatReady || !input.trim() || isSending}
            className="rounded-lg bg-primary p-2 text-primary-foreground transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
          >
            <SendHorizontal className="size-4.5" />
          </IconTooltip>
        </div>
      </div>
    </section>
  )
}