import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import apiClient from '@/api/client'
import Button from '@/components/common/Button'
import MarkdownOutput from '@/components/common/MarkdownOutput'

export default function InterviewReportPage() {
  const { documentId, sessionId } = useParams<{ documentId: string; sessionId: string }>()
  const navigate = useNavigate()
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
    apiClient.post(`/api/interview-sessions/${sessionId}/outputs/generate`).then(r => r.data)
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
      <div className="flex h-screen items-center justify-center bg-cream-100">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-cream-300 border-t-sage-400" />
          <p className="text-base font-medium text-natural-600">正在產生 BRD 與逐字稿...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-cream-100">
        <div className="text-center">
          <p className="text-red-600 mb-3">{error}</p>
          <Button onClick={() => window.location.reload()}>重試</Button>
        </div>
      </div>
    )
  }

  const markdownContent = activeTab === 'brd' ? outputs?.brd?.markdown : outputs?.transcript?.markdown

  return (
    <div className="flex h-screen flex-col bg-cream-100">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-cream-300 bg-white px-5 py-3">
        <div className="flex items-center gap-4">
          <h2 className="text-base font-semibold text-natural-700">訪談報告</h2>
          <div className="flex rounded-lg border border-cream-300 bg-cream-100 p-0.5">
            <button
              type="button"
              onClick={() => setActiveTab('brd')}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${activeTab === 'brd' ? 'bg-white text-natural-700 shadow-sm' : 'text-natural-400 hover:text-natural-600'}`}
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
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${activeTab === 'transcript' ? 'bg-white text-natural-700 shadow-sm' : 'text-natural-400 hover:text-natural-600'}`}
            >
              逐字稿
              {outputs?.transcript?.utteranceCount ? (
                <span className="ml-1.5 text-xs text-natural-300">{outputs.transcript.utteranceCount} 句</span>
              ) : null}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {outputs?.brd && (
            <button
              type="button"
              onClick={() => downloadMarkdown(outputs.brd!.markdown, 'BRD_草稿.md')}
              className="rounded-lg border border-cream-400 bg-white px-3 py-1.5 text-xs font-medium text-natural-600 hover:bg-cream-100"
            >
              下載 BRD
            </button>
          )}
          {outputs?.transcript && (
            <button
              type="button"
              onClick={() => downloadMarkdown(outputs.transcript!.markdown, '訪談逐字稿.md')}
              className="rounded-lg border border-cream-400 bg-white px-3 py-1.5 text-xs font-medium text-natural-600 hover:bg-cream-100"
            >
              下載逐字稿
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate(`/sessions/${sessionId}/insight-memo`)}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
          >
            訪談洞察
          </button>
          <Button variant="secondary" onClick={() => window.location.assign(`/editor/${documentId}`)}>
            回到編輯
          </Button>
        </div>
      </div>

      {/* Markdown content */}
      <div className="min-h-0 flex-1 overflow-y-auto bg-white px-8 py-6">
        <MarkdownOutput content={markdownContent} variant={activeTab} />
      </div>
    </div>
  )
}
