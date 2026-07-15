import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '@/api/client'
import { generateInsightMemo, getInsightMemo, type InsightMemo } from '@/api/projects'

type TranscriptEntry = {
  id?: string
  speaker: string
  transcript: string
  startedAt?: string
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    high: 'border-wood-300 bg-wood-100 text-wood-500',
    medium: 'border-wood-200 bg-wood-50 text-wood-400',
    low: 'border-cream-400 bg-cream-100 text-natural-500',
  }
  const labels: Record<string, string> = { high: '高優先', medium: '中優先', low: '低優先' }

  return (
    <span className={`inline-flex rounded border px-2 py-0.5 text-xs font-medium ${styles[severity] || styles.low}`}>
      {labels[severity] || severity}
    </span>
  )
}

function SourceBadge({ source }: { source: string }) {
  const styles: Record<string, string> = {
    explicit: 'border-sage-200 bg-sage-50 text-sage-500',
    inferred: 'border-cream-400 bg-cream-100 text-natural-500',
    unverified: 'border-wood-200 bg-wood-50 text-wood-500',
  }
  const labels: Record<string, string> = {
    explicit: '明確資訊',
    inferred: '分析推論',
    unverified: '待驗證',
  }

  return (
    <span className={`inline-flex rounded border px-2 py-0.5 text-xs font-medium ${styles[source] || styles.inferred}`}>
      {labels[source] || source}
    </span>
  )
}

function Metric({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="border-l border-cream-300 pl-4 first:border-l-0 first:pl-0">
      <div className="text-2xl font-semibold tracking-tight text-natural-800">{value}</div>
      <div className="mt-0.5 text-xs text-natural-400">{label}</div>
    </div>
  )
}

function SectionHeader({
  index,
  title,
  description,
  count,
}: {
  index: string
  title: string
  description: string
  count: number
}) {
  return (
    <div className="mb-5 flex items-start gap-4 border-b border-cream-300 pb-4">
      <span className="pt-0.5 font-mono text-xs font-semibold tracking-widest text-sage-400">{index}</span>
      <div className="min-w-0 flex-1">
        <h2 className="text-xl font-semibold text-natural-800">{title}</h2>
        <p className="mt-1 text-sm text-natural-500">{description}</p>
      </div>
      <span className="text-sm tabular-nums text-natural-400">{count}</span>
    </div>
  )
}

function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-cream-400 bg-cream-50 px-5 py-8 text-center text-sm text-natural-400">
      {children}
    </div>
  )
}

function formatTime(value?: string) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat('zh-TW', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function formatInterviewDate(value?: string) {
  if (!value) return '日期未記錄'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '日期未記錄'
  return new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export default function InsightMemoPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [memo, setMemo] = useState<InsightMemo | null>(null)
  const [allMemos, setAllMemos] = useState<InsightMemo[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'memo' | 'transcript'>('memo')
  const [selectedTranscriptSessionId, setSelectedTranscriptSessionId] = useState(sessionId || '')
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [transcriptLoading, setTranscriptLoading] = useState(false)

  const loadMemo = useCallback(async () => {
    if (!sessionId) return
    try {
      setLoading(true)
      let data: InsightMemo | null = null
      let retries = 0

      while (!data && retries < 10) {
        try {
          data = await getInsightMemo(sessionId)
        } catch {
          retries += 1
          if (retries >= 10) break
          setGenerating(true)
          await new Promise(resolve => setTimeout(resolve, 2000))
        }
      }

      if (!data) {
        try {
          data = await generateInsightMemo(sessionId)
        } catch {
          setMemo(null)
          setAllMemos([])
          setGenerating(false)
          return
        }
      }

      setGenerating(false)
      setMemo(data)

      if (data.projectId && data.stakeholderProfileId) {
        try {
          const response = await apiClient.get(`/api/projects/${data.projectId}/insight-memos`)
          const memos: InsightMemo[] = response.data?.memos || response.data || []
          const stakeholderMemos = memos.filter(
            item => item.stakeholderProfileId === data!.stakeholderProfileId,
          )
          setAllMemos(
            stakeholderMemos.some(item => item.sessionId === data!.sessionId)
              ? stakeholderMemos
              : [data, ...stakeholderMemos],
          )
        } catch {
          setAllMemos([data])
        }
      } else {
        setAllMemos([data])
      }
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => { loadMemo() }, [loadMemo])
  useEffect(() => {
    if (sessionId) setSelectedTranscriptSessionId(sessionId)
  }, [sessionId])
  useEffect(() => {
    if (activeTab !== 'transcript' || !selectedTranscriptSessionId) return

    let cancelled = false
    setTranscriptLoading(true)
    setTranscript([])

    apiClient.get(
      `/api/interview-sessions/${selectedTranscriptSessionId}/utterances`,
      { params: { limit: 1000 } },
    )
      .then(response => {
        if (!cancelled) setTranscript(response.data || [])
      })
      .catch(() => {
        if (!cancelled) setTranscript([])
      })
      .finally(() => {
        if (!cancelled) setTranscriptLoading(false)
      })

    return () => { cancelled = true }
  }, [activeTab, selectedTranscriptSessionId])

  const mergedPainPoints = allMemos.flatMap(item => item.painPoints || [])
  const mergedRequirements = allMemos.flatMap(item => item.requirementCandidates || [])
  const mergedConstraints = allMemos.flatMap(item => item.constraintsAndAssumptions || [])
  const mergedUnresolved = allMemos.flatMap(item => item.unresolvedQuestions || [])
  const mergedSuggestions = allMemos.flatMap(item => item.nextInterviewSuggestions || [])
  const mergedTopics = [...new Set(allMemos.flatMap(item => item.topicsCovered || []))]
  const totalMinutes = allMemos.reduce(
    (sum, item) => sum + (item.interviewDurationMinutes || 0),
    0,
  )
  const sourceTotals = allMemos.reduce(
    (totals, item) => ({
      explicit: totals.explicit + (item.sourceDistinction?.explicit_statements || 0),
      inferred: totals.inferred + (item.sourceDistinction?.inferences || 0),
      unverified: totals.unverified + (item.sourceDistinction?.unverified || 0),
    }),
    { explicit: 0, inferred: 0, unverified: 0 },
  )
  const sourceTotal = sourceTotals.explicit + sourceTotals.inferred + sourceTotals.unverified
  const constraints = mergedConstraints.filter(item => item.type !== 'assumption')
  const assumptions = mergedConstraints.filter(item => item.type === 'assumption')
  const transcriptSessions = [...(allMemos.length ? allMemos : memo ? [memo] : [])].sort((a, b) => {
    const aTime = new Date(a.interviewDate || a.createdAt || 0).getTime()
    const bTime = new Date(b.interviewDate || b.createdAt || 0).getTime()
    return aTime - bTime
  })
  const selectedTranscriptMemo = transcriptSessions.find(
    item => item.sessionId === selectedTranscriptSessionId,
  ) || transcriptSessions[0]
  const selectedTranscriptSessionIndex = transcriptSessions.findIndex(
    item => item.sessionId === selectedTranscriptMemo?.sessionId,
  )

  const handleGenerate = async () => {
    if (!sessionId) return
    try {
      setGenerating(true)
      setError(null)
      const data = await generateInsightMemo(sessionId)
      setMemo(data)
      setAllMemos(previous => previous.length > 1
        ? previous.map(item => item.sessionId === data.sessionId ? data : item)
        : [data])
    } catch (generationError: unknown) {
      const axiosError = generationError as { response?: { data?: { detail?: string } } }
      setError(axiosError.response?.data?.detail || '無法產生洞察紀錄')
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-50 px-6 py-16">
        <div className="mx-auto max-w-6xl animate-pulse space-y-6">
          <div className="h-8 w-48 rounded-lg bg-cream-300" />
          <div className="h-48 rounded-xl border border-cream-300 bg-white" />
          <div className="h-72 rounded-xl border border-cream-300 bg-white" />
        </div>
      </div>
    )
  }

  if (!memo) {
    return (
      <div className="min-h-screen bg-cream-50 px-6 py-16">
        <div className="mx-auto max-w-xl rounded-xl border border-cream-300 bg-white p-10 text-center shadow-natural">
          <p className="text-xs font-semibold tracking-[0.18em] text-sage-500">INTERVIEW INSIGHT</p>
          <h1 className="mt-3 text-2xl font-semibold text-natural-800">尚未產生訪談洞察</h1>
          <p className="mt-2 text-sm text-natural-500">完成分析後，痛點、需求線索與待追蹤問題會整理在這裡。</p>
          {error && <p className="mt-4 text-sm text-wood-500">{error}</p>}
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="mt-6 rounded-lg bg-sage-500 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-sage-400 disabled:opacity-50"
          >
            {generating ? '分析中…' : '產生洞察紀錄'}
          </button>
        </div>
      </div>
    )
  }

  const stakeholderName = memo.stakeholderSummary?.name || '未命名受訪者'
  const stakeholderRole = memo.stakeholderSummary?.role || '角色未設定'
  const stakeholderDepartment = memo.stakeholderSummary?.department
  const initials = stakeholderName.slice(0, 2)
  const outline = [
    { id: 'pain-points', label: '痛點與阻礙', count: mergedPainPoints.length },
    { id: 'requirements', label: '需求線索', count: mergedRequirements.length },
    { id: 'constraints', label: '限制與假設', count: mergedConstraints.length },
    { id: 'unresolved', label: '未解問題', count: mergedUnresolved.length },
    { id: 'next-steps', label: '建議下一步', count: mergedSuggestions.length },
  ]

  return (
    <div className="min-h-screen bg-cream-50 text-natural-700">
      <header className="border-b border-cream-300 bg-white">
        <div className="mx-auto max-w-6xl px-6 pb-0 pt-8 lg:px-8">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div className="flex items-start gap-4">
              <button
                type="button"
                onClick={() => memo.projectId ? navigate(`/projects/${memo.projectId}`) : navigate(-1)}
                aria-label="返回上一頁"
                className="mt-1 flex h-9 w-9 items-center justify-center rounded-lg border border-cream-300 text-lg text-natural-500 transition-colors hover:border-sage-300 hover:text-sage-500"
              >
                ←
              </button>
              <div>
                <p className="text-xs font-semibold tracking-[0.16em] text-sage-500">INTERVIEW RECORD</p>
                <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h1 className="text-3xl font-semibold tracking-tight text-natural-800">訪談紀錄</h1>
                  <span className="text-sm text-natural-400">{stakeholderName}</span>
                </div>
                <p className="mt-1 text-sm text-natural-500">整合訪談證據、產品洞察與後續研究方向</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {allMemos.length > 1 && (
                <span className="rounded-lg border border-sage-200 bg-sage-50 px-3 py-2 text-xs font-medium text-sage-500">
                  已合併 {allMemos.length} 場訪談
                </span>
              )}
              {memo.projectId && (
                <button
                  type="button"
                  onClick={() => navigate(`/projects/${memo.projectId}`)}
                  className="rounded-lg border border-cream-400 bg-white px-4 py-2 text-sm font-medium text-natural-600 transition-colors hover:border-sage-300 hover:text-sage-500"
                >
                  回到專案
                </button>
              )}
            </div>
          </div>

          <nav className="mt-8 flex gap-8" aria-label="訪談紀錄檢視模式">
            {(['memo', 'transcript'] as const).map(tab => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`border-b-2 pb-3 text-sm font-semibold transition-colors ${
                  activeTab === tab
                    ? 'border-sage-500 text-sage-500'
                    : 'border-transparent text-natural-400 hover:text-natural-600'
                }`}
              >
                {tab === 'memo' ? '洞察分析' : `完整逐字稿 · ${transcriptSessions.length} 場`}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8 lg:px-8">
        {activeTab === 'transcript' ? (
          <section className="animate-themeFadeIn">
            <div className="mb-6 flex flex-col gap-3 border-b border-cream-300 pb-5 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-semibold tracking-[0.14em] text-sage-500">FULL TRANSCRIPT</p>
                <h2 className="mt-1 text-2xl font-semibold text-natural-800">完整逐字稿</h2>
                <p className="mt-1 text-sm text-natural-500">依照發言順序保留訪談內容，方便回查洞察來源。</p>
              </div>
              <div className="flex gap-5 text-xs text-natural-500">
                <span><i className="mr-2 inline-block h-2 w-2 bg-sage-400" />訪談者</span>
                <span><i className="mr-2 inline-block h-2 w-2 bg-wood-300" />受訪者</span>
              </div>
            </div>

            <nav className="mb-6 border-b border-cream-300" aria-label="逐字稿場次">
              <div className="flex gap-1 overflow-x-auto pb-px">
                {transcriptSessions.map((sessionMemo, index) => {
                  const selected = sessionMemo.sessionId === selectedTranscriptSessionId
                  return (
                    <button
                      key={sessionMemo.sessionId}
                      type="button"
                      aria-current={selected ? 'page' : undefined}
                      onClick={() => setSelectedTranscriptSessionId(sessionMemo.sessionId)}
                      className={`min-w-48 border-b-2 px-4 py-3 text-left transition-colors ${
                        selected
                          ? 'border-sage-500 bg-sage-50 text-sage-600'
                          : 'border-transparent text-natural-500 hover:border-cream-400 hover:bg-white'
                      }`}
                    >
                      <span className="block text-sm font-semibold">第 {index + 1} 場</span>
                      <span className="mt-1 block whitespace-nowrap text-xs tabular-nums text-natural-400">
                        {formatInterviewDate(sessionMemo.interviewDate || sessionMemo.createdAt)}
                      </span>
                      <span className="mt-1 block text-xs text-natural-400">
                        {sessionMemo.interviewDurationMinutes || 0} 分鐘 · {sessionMemo.topicsCovered?.length || 0} 個主題
                      </span>
                    </button>
                  )
                })}
              </div>
            </nav>

            {selectedTranscriptMemo && (
              <div className="mb-5 grid gap-4 border-b border-cream-300 pb-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                <div>
                  <p className="text-sm font-semibold text-natural-700">
                    第 {selectedTranscriptSessionIndex + 1} 場訪談
                    <span className="ml-2 font-normal text-natural-400">
                      {formatInterviewDate(selectedTranscriptMemo.interviewDate || selectedTranscriptMemo.createdAt)}
                    </span>
                  </p>
                  {selectedTranscriptMemo.topicsCovered?.length ? (
                    <ul className="mt-2 space-y-1 text-sm text-natural-500">
                      {selectedTranscriptMemo.topicsCovered.map((topic, index) => (
                        <li key={`${topic}-${index}`} className="relative pl-3 before:absolute before:left-0 before:top-[0.65em] before:h-1 before:w-1 before:bg-sage-300">
                          {topic}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-sm text-natural-400">此場尚未整理涵蓋主題</p>
                  )}
                </div>
                <div className="flex gap-6 text-sm text-natural-500">
                  <span><strong className="mr-1 font-semibold text-natural-700">{selectedTranscriptMemo.interviewDurationMinutes || 0}</strong>分鐘</span>
                  <span><strong className="mr-1 font-semibold text-natural-700">{transcript.length}</strong>段發言</span>
                </div>
              </div>
            )}

            {transcriptLoading ? (
              <div className="rounded-xl border border-cream-300 bg-white px-6 py-16 text-center text-sm text-natural-400">載入逐字稿中…</div>
            ) : transcript.length === 0 ? (
              <EmptyState>此場訪談沒有可顯示的逐字稿。</EmptyState>
            ) : (
              <div className="overflow-hidden rounded-xl border border-cream-300 bg-white shadow-natural">
                {transcript.map((utterance, index) => {
                  const interviewer = utterance.speaker === 'interviewer'
                  return (
                    <article
                      key={utterance.id || `${utterance.startedAt || 'utterance'}-${index}`}
                      className="grid grid-cols-[44px_80px_minmax(0,1fr)] gap-3 border-b border-cream-200 px-4 py-5 last:border-b-0 sm:grid-cols-[56px_100px_minmax(0,1fr)] sm:gap-5 sm:px-6"
                    >
                      <span className="pt-0.5 font-mono text-xs tabular-nums text-natural-300">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <div>
                        <div className={`border-l-2 pl-3 text-sm font-semibold ${interviewer ? 'border-sage-400 text-sage-500' : 'border-wood-300 text-wood-500'}`}>
                          {interviewer ? '訪談者' : '受訪者'}
                        </div>
                        {formatTime(utterance.startedAt) && (
                          <div className="mt-1 pl-3 text-xs tabular-nums text-natural-300">{formatTime(utterance.startedAt)}</div>
                        )}
                      </div>
                      <p className="text-base leading-8 text-natural-700">{utterance.transcript}</p>
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        ) : (
          <div className="animate-themeFadeIn">
            <section className="overflow-hidden rounded-xl border border-cream-300 bg-white shadow-natural">
              <div className="grid gap-6 border-b border-cream-300 p-6 md:grid-cols-[minmax(0,1.3fr)_minmax(320px,1fr)] md:p-8">
                <div className="flex items-start gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-sm bg-sage-100 text-sm font-semibold text-sage-600">
                    {initials}
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-natural-800">{stakeholderName}</h2>
                    <p className="mt-0.5 text-sm text-natural-500">
                      {stakeholderRole}{stakeholderDepartment ? ` · ${stakeholderDepartment}` : ''}
                    </p>
                    {memo.stakeholderSummary?.expertise?.length ? (
                      <p className="mt-3 text-sm leading-6 text-natural-500">
                        <span className="font-medium text-natural-600">熟悉領域：</span>
                        {memo.stakeholderSummary.expertise.join('、')}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-y-5 sm:grid-cols-4 md:grid-cols-2 lg:grid-cols-4">
                  <Metric value={allMemos.length} label="訪談場次" />
                  <Metric value={totalMinutes} label="總分鐘" />
                  <Metric value={mergedTopics.length} label="涵蓋主題" />
                  <Metric value={mergedPainPoints.length + mergedRequirements.length} label="洞察線索" />
                </div>
              </div>

              <div className="grid gap-6 p-6 md:grid-cols-[minmax(0,1fr)_320px] md:p-8">
                <div>
                  <p className="text-xs font-semibold tracking-[0.12em] text-natural-400">涵蓋主題</p>
                  {mergedTopics.length ? (
                    <ul className="mt-3 space-y-2 text-sm text-natural-600">
                      {mergedTopics.map((topic, index) => (
                        <li key={`${topic}-${index}`} className="relative pl-3 before:absolute before:left-0 before:top-[0.65em] before:h-1 before:w-1 before:bg-sage-300">
                          {topic}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-natural-400">尚未整理涵蓋主題</p>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold tracking-[0.12em] text-natural-400">資訊可信度</span>
                    <span className="text-natural-400">共 {sourceTotal} 筆</span>
                  </div>
                  <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-cream-200" aria-label="資訊可信度分布">
                    {sourceTotal > 0 && (
                      <>
                        <span className="bg-sage-400" style={{ width: `${sourceTotals.explicit / sourceTotal * 100}%` }} />
                        <span className="bg-natural-300" style={{ width: `${sourceTotals.inferred / sourceTotal * 100}%` }} />
                        <span className="bg-wood-300" style={{ width: `${sourceTotals.unverified / sourceTotal * 100}%` }} />
                      </>
                    )}
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-natural-500">
                    <span>明確 <b className="font-semibold text-sage-500">{sourceTotals.explicit}</b></span>
                    <span>推論 <b className="font-semibold text-natural-600">{sourceTotals.inferred}</b></span>
                    <span>待驗 <b className="font-semibold text-wood-500">{sourceTotals.unverified}</b></span>
                  </div>
                </div>
              </div>
            </section>

            <div className="mt-10 grid gap-10 lg:grid-cols-[190px_minmax(0,1fr)]">
              <aside className="hidden lg:block">
                <div className="sticky top-6 border-l border-cream-400 pl-5">
                  <p className="mb-4 text-xs font-semibold tracking-[0.14em] text-natural-400">CONTENTS</p>
                  <nav className="space-y-1" aria-label="洞察分析章節">
                    {outline.map(item => (
                      <a
                        key={item.id}
                        href={`#${item.id}`}
                        className="flex items-center justify-between py-2 text-sm text-natural-500 transition-colors hover:text-sage-500"
                      >
                        <span>{item.label}</span>
                        <span className="font-mono text-xs text-natural-300">{item.count}</span>
                      </a>
                    ))}
                  </nav>
                </div>
              </aside>

              <div className="min-w-0 space-y-14">
                <section id="pain-points" className="scroll-mt-6">
                  <SectionHeader index="01" title="痛點與阻礙" description="受訪者在現有流程中明確感受到的摩擦與影響。" count={mergedPainPoints.length} />
                  {mergedPainPoints.length ? (
                    <div className="overflow-hidden rounded-xl border border-cream-300 bg-white shadow-natural">
                      {mergedPainPoints.map((painPoint, index) => (
                        <article key={`${painPoint.description}-${index}`} className="grid gap-3 border-b border-cream-200 p-5 last:border-b-0 sm:grid-cols-[34px_minmax(0,1fr)] sm:gap-5 sm:p-6">
                          <span className="font-mono text-xs text-natural-300">{String(index + 1).padStart(2, '0')}</span>
                          <div>
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <h3 className="max-w-2xl text-base font-semibold leading-7 text-natural-800">{painPoint.description}</h3>
                              <SeverityBadge severity={painPoint.severity} />
                            </div>
                            {painPoint.evidence_quote && (
                              <blockquote className="mt-4 border-l-2 border-sage-200 bg-sage-50 px-4 py-3 text-sm leading-6 text-natural-600">
                                「{painPoint.evidence_quote}」
                              </blockquote>
                            )}
                            {painPoint.affected_roles?.length > 0 && (
                              <p className="mt-3 text-xs text-natural-400">影響角色 · {painPoint.affected_roles.join('、')}</p>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : <EmptyState>這次訪談尚未辨識出明確痛點。</EmptyState>}
                </section>

                <section id="requirements" className="scroll-mt-6">
                  <SectionHeader index="02" title="需求線索" description="可進一步轉換為產品需求，但仍需依證據成熟度驗證。" count={mergedRequirements.length} />
                  {mergedRequirements.length ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      {mergedRequirements.map((requirement, index) => (
                        <article key={`${requirement.description}-${index}`} className="flex min-h-56 flex-col rounded-xl border border-cream-300 bg-white p-5 shadow-natural">
                          <div className="flex items-center justify-between gap-3">
                            <SourceBadge source={requirement.source} />
                            <span className="text-xs text-natural-400">信心 {requirement.confidence}</span>
                          </div>
                          <h3 className="mt-4 text-base font-semibold leading-7 text-natural-800">{requirement.description}</h3>
                          {requirement.evidence_quote && (
                            <p className="mt-3 text-sm leading-6 text-natural-500">「{requirement.evidence_quote}」</p>
                          )}
                          <div className="mt-auto border-t border-cream-200 pt-4 text-xs text-natural-400">
                            {requirement.brd_ready
                              ? <span className="font-medium text-sage-500">可納入 BRD 草稿</span>
                              : requirement.needs_validation_from?.length
                                ? `待 ${requirement.needs_validation_from.join('、')} 驗證`
                                : '需要更多訪談證據'}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : <EmptyState>尚無可整理的需求線索。</EmptyState>}
                </section>

                <section id="constraints" className="scroll-mt-6">
                  <SectionHeader index="03" title="限制與假設" description="把已知限制與分析假設拆開呈現，避免兩者混為既定事實。" count={mergedConstraints.length} />
                  {mergedConstraints.length ? (
                    <div className="grid overflow-hidden rounded-xl border border-cream-300 bg-white shadow-natural md:grid-cols-2">
                      <div className="border-b border-cream-300 p-5 md:border-b-0 md:border-r md:p-6">
                        <div className="mb-4 flex items-center justify-between">
                          <h3 className="font-semibold text-wood-500">已知限制</h3>
                          <span className="font-mono text-xs text-natural-300">{constraints.length}</span>
                        </div>
                        <div className="space-y-5">
                          {constraints.length ? constraints.map((constraint, index) => (
                            <div key={`${constraint.content}-${index}`} className="border-l-2 border-wood-200 pl-4">
                              <p className="text-sm leading-7 text-natural-700">{constraint.content}</p>
                              <div className="mt-2"><SourceBadge source={constraint.source} /></div>
                            </div>
                          )) : <p className="text-sm text-natural-400">無已知限制</p>}
                        </div>
                      </div>
                      <div className="p-5 md:p-6">
                        <div className="mb-4 flex items-center justify-between">
                          <h3 className="font-semibold text-natural-600">待驗證假設</h3>
                          <span className="font-mono text-xs text-natural-300">{assumptions.length}</span>
                        </div>
                        <div className="space-y-5">
                          {assumptions.length ? assumptions.map((assumption, index) => (
                            <div key={`${assumption.content}-${index}`} className="border-l-2 border-natural-200 pl-4">
                              <p className="text-sm leading-7 text-natural-700">{assumption.content}</p>
                              <div className="mt-2"><SourceBadge source={assumption.source} /></div>
                            </div>
                          )) : <p className="text-sm text-natural-400">無待驗證假設</p>}
                        </div>
                      </div>
                    </div>
                  ) : <EmptyState>尚未整理限制或假設。</EmptyState>}
                </section>

                <section id="unresolved" className="scroll-mt-6">
                  <SectionHeader index="04" title="未解問題" description="轉化為下一輪研究可以直接追蹤的問題清單。" count={mergedUnresolved.length} />
                  {mergedUnresolved.length ? (
                    <div className="overflow-hidden rounded-xl border border-cream-300 bg-white shadow-natural">
                      {mergedUnresolved.map((question, index) => (
                        <article key={`${question.question}-${index}`} className="grid gap-4 border-b border-cream-200 p-5 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_170px] sm:p-6">
                          <div className="flex gap-4">
                            <span className="font-mono text-xs text-natural-300">Q{String(index + 1).padStart(2, '0')}</span>
                            <div>
                              <h3 className="text-base font-semibold leading-7 text-natural-800">{question.question}</h3>
                              {question.reason && <p className="mt-2 text-sm leading-6 text-natural-500">{question.reason}</p>}
                            </div>
                          </div>
                          <div className="border-l border-cream-300 pl-4">
                            <SeverityBadge severity={question.priority} />
                            <p className="mt-3 text-xs text-natural-400">建議訪談對象</p>
                            <p className="mt-1 text-sm font-medium text-natural-600">{question.suggested_stakeholder_type}</p>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : <EmptyState>目前沒有未解問題。</EmptyState>}
                </section>

                <section id="next-steps" className="scroll-mt-6">
                  <SectionHeader index="05" title="建議下一步" description="依角色與研究目標安排後續訪談。" count={mergedSuggestions.length} />
                  {mergedSuggestions.length ? (
                    <div className="space-y-0 border-l-2 border-sage-200 pl-6">
                      {mergedSuggestions.map((suggestion, index) => (
                        <article key={`${suggestion.target_role}-${index}`} className="relative border-b border-cream-300 py-5 first:pt-0 last:border-b-0 last:pb-0 before:absolute before:-left-[31px] before:top-6 before:h-2 before:w-2 before:bg-sage-400 first:before:top-1">
                          <p className="text-xs font-semibold tracking-[0.1em] text-sage-500">{suggestion.target_role}</p>
                          <h3 className="mt-1 text-base font-semibold text-natural-800">{suggestion.objective}</h3>
                          {suggestion.key_questions?.length > 0 && (
                            <ol className="mt-3 space-y-2 text-sm leading-6 text-natural-500">
                              {suggestion.key_questions.map((question, questionIndex) => (
                                <li key={`${question}-${questionIndex}`} className="flex gap-3">
                                  <span className="font-mono text-xs text-natural-300">{questionIndex + 1}</span>
                                  <span>{question}</span>
                                </li>
                              ))}
                            </ol>
                          )}
                        </article>
                      ))}
                    </div>
                  ) : <EmptyState>尚無下一步建議。</EmptyState>}
                </section>

                <footer className="flex flex-col gap-3 border-t border-cream-300 pt-6 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-natural-400">
                    洞察內容由訪談證據與 AI 分析產生，重要決策前仍應回查逐字稿。
                  </p>
                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={generating}
                    className="shrink-0 rounded-lg border border-cream-400 bg-white px-4 py-2 text-sm font-medium text-natural-500 transition-colors hover:border-sage-300 hover:text-sage-500 disabled:opacity-50"
                  >
                    {generating ? '重新分析中…' : '重新產生分析'}
                  </button>
                </footer>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
