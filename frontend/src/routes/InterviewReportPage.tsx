import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSlug from 'rehype-slug'
import rehypeAutolinkHeadings from 'rehype-autolink-headings'
import { presentationAPI } from '@/api/presentation'
import Button from '@/components/common/Button'

export default function InterviewReportPage() {
  const { deckId, sessionId } = useParams<{ deckId: string; sessionId: string }>()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'brd' | 'transcript'>('brd')
  const [outputs, setOutputs] = useState<{
    brd?: { markdown: string; openIssuesCount: number }
    transcript?: { markdown: string; utteranceCount: number }
  } | null>(null)

  useEffect(() => {
    if (!sessionId) return
    setIsLoading(true)
    presentationAPI.generateOutputs(sessionId)
      .then(setOutputs)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to generate report'))
      .finally(() => setIsLoading(false))
  }, [sessionId])

  function downloadMarkdown(content: string, filename: string) {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-gray-200 border-t-blue-600" />
          <p className="text-base font-medium text-gray-700">正在產生 BRD 與逐字稿...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-red-600 mb-3">{error}</p>
          <Button onClick={() => window.location.reload()}>重試</Button>
        </div>
      </div>
    )
  }

  const markdownContent = activeTab === 'brd' ? outputs?.brd?.markdown : outputs?.transcript?.markdown

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-gray-200 bg-white px-5 py-3">
        <div className="flex items-center gap-4">
          <h2 className="text-base font-semibold text-gray-900">訪談報告</h2>
          <div className="flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
            <button
              type="button"
              onClick={() => setActiveTab('brd')}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${activeTab === 'brd' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            >
              BRD 草稿
              {outputs?.brd?.openIssuesCount ? (
                <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                  {outputs.brd.openIssuesCount} 待補
                </span>
              ) : null}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('transcript')}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${activeTab === 'transcript' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            >
              逐字稿
              {outputs?.transcript?.utteranceCount ? (
                <span className="ml-1.5 text-xs text-gray-400">{outputs.transcript.utteranceCount} 句</span>
              ) : null}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {outputs?.brd && (
            <button
              type="button"
              onClick={() => downloadMarkdown(outputs.brd!.markdown, 'BRD_草稿.md')}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              下載 BRD
            </button>
          )}
          {outputs?.transcript && (
            <button
              type="button"
              onClick={() => downloadMarkdown(outputs.transcript!.markdown, '訪談逐字稿.md')}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              下載逐字稿
            </button>
          )}
          <Button variant="secondary" onClick={() => window.location.assign(`/editor/${deckId}`)}>
            回到編輯
          </Button>
        </div>
      </div>

      {/* Markdown content */}
      <div className="min-h-0 flex-1 overflow-y-auto bg-white px-8 py-6">
        <div className="mx-auto max-w-3xl prose prose-sm prose-gray prose-headings:text-gray-900 prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-blockquote:border-blue-300 prose-blockquote:text-blue-800 prose-blockquote:bg-blue-50 prose-blockquote:px-4 prose-blockquote:py-2 prose-blockquote:rounded">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug, rehypeAutolinkHeadings]}>
            {markdownContent || '（無內容）'}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
