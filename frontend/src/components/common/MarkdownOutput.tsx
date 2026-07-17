import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import rehypeAutolinkHeadings from 'rehype-autolink-headings'

interface MarkdownOutputProps {
  content?: string
  variant: 'brd' | 'transcript'
}

type TranscriptEntry =
  | { type: 'heading'; id: string; title: string }
  | {
      type: 'utterance'
      id: string
      time?: string
      text: string
    }

interface TranscriptSummary {
  title: string
  items: Array<{ label: string; value: string }>
}

interface ParsedTranscript {
  summary: TranscriptSummary
  entries: TranscriptEntry[]
}

function parseTranscriptMarkdown(content: string): ParsedTranscript {
  const entries: TranscriptEntry[] = []
  const summary: TranscriptSummary = { title: '訪談逐字稿', items: [] }
  let currentUtterance: Extract<TranscriptEntry, { type: 'utterance' }> | null = null

  const flushUtterance = () => {
    if (currentUtterance?.text.trim()) {
      entries.push({
        ...currentUtterance,
        text: currentUtterance.text.trim(),
      })
    }
    currentUtterance = null
  }

  content.split(/\r?\n/).forEach((rawLine, index) => {
    const line = rawLine.trim()
    if (!line) return

    const titleMatch = line.match(/^#\s+(.+)$/)
    if (titleMatch) {
      summary.title = titleMatch[1]
      return
    }

    const summaryRowMatch = line.match(/^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$/)
    if (summaryRowMatch) {
      const label = summaryRowMatch[1].trim()
      const value = summaryRowMatch[2].trim()
      if (label !== '項目' && !/^:?-+:?$/.test(label) && !/^:?-+:?$/.test(value)) {
        summary.items.push({ label, value })
      }
      return
    }

    const sectionMatch = line.match(/^##\s+(.+)$/)
    if (sectionMatch) {
      flushUtterance()
      entries.push({ type: 'heading', id: `heading-${index}`, title: sectionMatch[1] })
      return
    }

    const timedLineMatch = line.match(/^(?:[-*]\s*)?(?:\[(.*?)\]|`(.*?)`)\s*(.+)$/)
    if (timedLineMatch) {
      flushUtterance()
      currentUtterance = {
        type: 'utterance',
        id: `utterance-${index}`,
        time: timedLineMatch[1] || timedLineMatch[2],
        text: timedLineMatch[3],
      }
      return
    }

    if (/^[-*]\s+/.test(line)) {
      flushUtterance()
      currentUtterance = {
        type: 'utterance',
        id: `utterance-${index}`,
        text: line.replace(/^[-*]\s+/, ''),
      }
      return
    }

    if (currentUtterance) {
      currentUtterance.text = [currentUtterance.text, line.replace(/^>\s?/, '')]
        .filter(Boolean)
        .join('\n')
      return
    }

    currentUtterance = {
      type: 'utterance',
      id: `utterance-${index}`,
      text: line.replace(/^>\s?/, ''),
    }
  })

  flushUtterance()
  return { summary, entries }
}

function TranscriptChat({ content }: { content?: string }) {
  const { summary, entries } = parseTranscriptMarkdown(content || '')
  if (entries.length === 0) {
    return <p className="text-sm text-natural-400">（無內容）</p>
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <section className="rounded-lg border border-cream-300 bg-white px-4 py-3 shadow-sm">
        <h1 className="text-base font-semibold text-natural-700">{summary.title}</h1>
        {summary.items.length > 0 && (
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            {summary.items.map((item) => (
              <div key={item.label} className="rounded-md bg-cream-100 px-3 py-2">
                <dt className="text-xs font-medium text-natural-400">{item.label}</dt>
                <dd className="mt-0.5 text-sm text-natural-700">{item.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {entries.map((entry) => {
        if (entry.type === 'heading') {
          return (
            <div key={entry.id} className="flex justify-center">
              <span className="rounded-full bg-cream-200 px-3 py-1 text-xs font-medium text-natural-400">
                {entry.title}
              </span>
            </div>
          )
        }

        return (
          <article
            key={entry.id}
            className="rounded-xl border border-cream-300 bg-white px-4 py-3 shadow-sm"
          >
            {entry.time ? (
              <div className="mb-1 text-xs font-medium text-natural-300">{entry.time}</div>
            ) : null}
            <div className="text-sm leading-7 text-natural-700">
              {entry.text.split('\n').map((line, lineIndex) => (
                <p key={`${entry.id}-line-${lineIndex}`} className="whitespace-pre-wrap">
                  {line}
                </p>
              ))}
            </div>
          </article>
        )
      })}
    </div>
  )
}

export default function MarkdownOutput({ content, variant }: MarkdownOutputProps) {
  if (variant === 'transcript') {
    return <TranscriptChat content={content} />
  }

  return (
    <div className="mx-auto max-w-3xl prose prose-sm prose-gray prose-headings:text-natural-700 prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-blockquote:border-blue-300 prose-blockquote:text-blue-800 prose-blockquote:bg-blue-50 prose-blockquote:px-4 prose-blockquote:py-2 prose-blockquote:rounded">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug, rehypeAutolinkHeadings]}>
        {content || '（無內容）'}
      </ReactMarkdown>
    </div>
  )
}
