import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import rehypeAutolinkHeadings from 'rehype-autolink-headings'

interface MarkdownOutputProps {
  content?: string
  variant: 'brd' | 'transcript'
}

type TranscriptEntry =
  | { type: 'section'; id: string; title: string }
  | {
      type: 'message'
      id: string
      speaker: 'interviewer' | 'interviewee'
      label: string
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
  let currentMessage: Extract<TranscriptEntry, { type: 'message' }> | null = null

  const flushMessage = () => {
    if (currentMessage?.text.trim()) {
      entries.push({
        ...currentMessage,
        text: currentMessage.text.trim(),
      })
    }
    currentMessage = null
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
      flushMessage()
      entries.push({ type: 'section', id: `section-${index}`, title: sectionMatch[1] })
      return
    }

    const inlineSpeakerMatch = line.match(/^\*\*(.*?)\*\*\s*(?:\[(.*?)\]|`(.*?)`)?[:：]\s*(.+)$/)
    if (inlineSpeakerMatch) {
      flushMessage()
      const label = normalizeSpeakerLabel(inlineSpeakerMatch[1])
      currentMessage = {
        type: 'message',
        id: `message-${index}`,
        speaker: getSpeakerSide(label),
        label,
        time: inlineSpeakerMatch[2] || inlineSpeakerMatch[3],
        text: inlineSpeakerMatch[4],
      }
      return
    }

    const speakerMatch = line.match(/^\*\*(.*?)\*\*\s*(?:`(.*?)`)?$/)
    if (speakerMatch) {
      const label = normalizeSpeakerLabel(speakerMatch[1])
      if (label === '訪問者' || label === '受訪者') {
        flushMessage()
        currentMessage = {
          type: 'message',
          id: `message-${index}`,
          speaker: getSpeakerSide(label),
          label,
          time: speakerMatch[2],
          text: '',
        }
      }
      return
    }

    if (currentMessage) {
      currentMessage.text = [currentMessage.text, line.replace(/^>\s?/, '')]
        .filter(Boolean)
        .join('\n')
    }
  })

  flushMessage()
  return { summary, entries }
}

function normalizeSpeakerLabel(label: string) {
  if (label.includes('受訪者') || label.toLowerCase().includes('interviewee')) return '受訪者'
  if (
    label.includes('訪談者') ||
    label.includes('訪問者') ||
    label.toLowerCase().includes('interviewer')
  ) {
    return '訪問者'
  }
  return label.trim()
}

function getSpeakerSide(label: string): 'interviewer' | 'interviewee' {
  return label === '受訪者' ? 'interviewee' : 'interviewer'
}

function TranscriptChat({ content }: { content?: string }) {
  const { summary, entries } = parseTranscriptMarkdown(content || '')
  if (entries.length === 0) {
    return <p className="text-sm text-gray-500">（無內容）</p>
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <section className="rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm">
        <h1 className="text-base font-semibold text-gray-900">{summary.title}</h1>
        {summary.items.length > 0 && (
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            {summary.items.map((item) => (
              <div key={item.label} className="rounded-md bg-gray-50 px-3 py-2">
                <dt className="text-xs font-medium text-gray-500">{item.label}</dt>
                <dd className="mt-0.5 text-sm text-gray-900">{item.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {entries.map((entry) => {
        if (entry.type === 'section') {
          return (
            <div key={entry.id} className="flex justify-center">
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-500">
                {entry.title}
              </span>
            </div>
          )
        }

        const isInterviewee = entry.speaker === 'interviewee'
        return (
          <div
            key={entry.id}
            className={`flex w-full ${isInterviewee ? 'justify-start' : 'justify-end'}`}
          >
            <div className={`max-w-[74%] ${isInterviewee ? 'items-start' : 'items-end'} flex flex-col gap-1`}>
              <div className={`text-xs text-gray-400 ${isInterviewee ? 'text-left' : 'text-right'}`}>
                <span>{entry.label}</span>
                {entry.time ? <span className="ml-2">{entry.time}</span> : null}
              </div>
              <div
                className={`rounded-2xl px-4 py-2.5 text-sm leading-7 shadow-sm ${
                  isInterviewee
                    ? 'rounded-bl-md border border-gray-200 bg-white text-gray-900'
                    : 'rounded-br-md bg-blue-600 text-white'
                }`}
              >
                {entry.text.split('\n').map((line, lineIndex) => (
                  <p key={`${entry.id}-line-${lineIndex}`} className="whitespace-pre-wrap">
                    {line}
                  </p>
                ))}
              </div>
            </div>
          </div>
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
    <div className="mx-auto max-w-3xl prose prose-sm prose-gray prose-headings:text-gray-900 prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-blockquote:border-blue-300 prose-blockquote:text-blue-800 prose-blockquote:bg-blue-50 prose-blockquote:px-4 prose-blockquote:py-2 prose-blockquote:rounded">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug, rehypeAutolinkHeadings]}>
        {content || '（無內容）'}
      </ReactMarkdown>
    </div>
  )
}
