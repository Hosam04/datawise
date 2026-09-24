'use client'

function renderInlineMarkdown(text: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  let key = 0
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }
    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={key++} className="font-semibold text-foreground">
          {token.slice(2, -2)}
        </strong>
      )
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code key={key++} className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
          {token.slice(1, -1)}
        </code>
      )
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={key++} className="italic text-foreground">
          {token.slice(1, -1)}
        </em>
      )
    }
    lastIndex = regex.lastIndex
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }
  return parts.length > 0 ? parts : text
}

export function FormattedMarkdown({ content }: { content: unknown }) {
  if (typeof content !== 'string') {
    if (!content) return null
    return (
      <p className="text-sm text-muted-foreground">
        {typeof content === 'object' ? JSON.stringify(content, null, 2) : String(content)}
      </p>
    )
  }

  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let currentList: { type: 'ul' | 'ol'; items: string[] } | null = null

  const flushList = () => {
    if (!currentList) return
    if (currentList.type === 'ul') {
      elements.push(
        <ul key={`list-${elements.length}`} className="my-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground">
          {currentList.items.map((item, idx) => (
            <li key={idx}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      )
    } else {
      elements.push(
        <ol key={`list-${elements.length}`} className="my-2 list-decimal space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground">
          {currentList.items.map((item, idx) => (
            <li key={idx}>{renderInlineMarkdown(item)}</li>
          ))}
        </ol>
      )
    }
    currentList = null
  }

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i]
    const line = rawLine.trim()

    if (!line) {
      flushList()
      continue
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/)
    if (headingMatch) {
      flushList()
      const level = headingMatch[1].length
      const text = headingMatch[2]
      if (level === 1) {
        elements.push(
          <h3 key={i} className="mt-3 text-base font-bold text-foreground">
            {renderInlineMarkdown(text)}
          </h3>
        )
      } else if (level === 2) {
        elements.push(
          <h4 key={i} className="mt-2.5 text-sm font-semibold text-foreground">
            {renderInlineMarkdown(text)}
          </h4>
        )
      } else {
        elements.push(
          <h5 key={i} className="mt-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {renderInlineMarkdown(text)}
          </h5>
        )
      }
      continue
    }

    const bulletMatch = line.match(/^[-*•]\s+(.+)$/)
    if (bulletMatch) {
      if (!currentList || currentList.type !== 'ul') {
        flushList()
        currentList = { type: 'ul', items: [] }
      }
      currentList.items.push(bulletMatch[1])
      continue
    }

    const numMatch = line.match(/^\d+\.\s+(.+)$/)
    if (numMatch) {
      if (!currentList || currentList.type !== 'ol') {
        flushList()
        currentList = { type: 'ol', items: [] }
      }
      currentList.items.push(numMatch[1])
      continue
    }

    flushList()
    elements.push(
      <p key={i} className="my-1.5 text-sm leading-relaxed text-muted-foreground wrap-break-word">
        {renderInlineMarkdown(line)}
      </p>
    )
  }

  flushList()
  return <div className="space-y-1">{elements}</div>
}