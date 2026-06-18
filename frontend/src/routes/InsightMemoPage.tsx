import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getInsightMemo, generateInsightMemo, type InsightMemo } from '@/api/projects'
import { apiClient } from '@/api/client'

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    high: 'bg-red-100 text-red-700',
    medium: 'bg-amber-100 text-amber-700',
    low: 'bg-cream-100 text-natural-600',
  }
  return (
    <span className={`px-1.5 py-0.5 text-xs rounded ${colors[severity] || colors.low}`}>
      {severity === 'high' ? '高' : severity === 'medium' ? '中' : '低'}
    </span>
  )
}

function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, string> = {
    explicit: 'bg-green-100 text-green-700',
    inferred: 'bg-blue-100 text-blue-700',
    unverified: 'bg-orange-100 text-orange-700',
  }
  const labels: Record<string, string> = {
    explicit: '明確',
    inferred: '推論',
    unverified: '待驗證',
  }
  return (
    <span className={`px-1.5 py-0.5 text-xs rounded ${colors[source] || 'bg-cream-100 text-natural-600'}`}>
      {labels[source] || source}
    </span>
  )
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
  const [transcript, setTranscript] = useState<{ speaker: string; transcript: string; startedAt?: string }[]>([])
  const [transcriptLoading, setTranscriptLoading] = useState(false)

  const loadMemo = useCallback(async () => {
    if (!sessionId) return
    try {
      setLoading(true)

      // Try GET first; if not ready, wait and retry (background task is generating)
      let data: InsightMemo | null = null
      let retries = 0
      while (!data && retries < 10) {
        try {
          data = await getInsightMemo(sessionId)
        } catch {
          retries++
          if (retries >= 10) break
          setGenerating(true)
          await new Promise(r => setTimeout(r, 2000))
        }
      }

      if (!data) {
        // Last resort: trigger generation directly
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

      // Load all memos from the same stakeholder (stakeholder view)
      if (data.projectId && data.stakeholderProfileId) {
        try {
          const res = await apiClient.get(`/api/projects/${data.projectId}/insight-memos`)
          const memos: InsightMemo[] = (res.data?.memos || res.data || [])
          const stakeholderMemos = memos.filter(
            (m: InsightMemo) => m.stakeholderProfileId === data!.stakeholderProfileId
          )
          setAllMemos(stakeholderMemos)
        } catch { setAllMemos([data]) }
      } else {
        setAllMemos([data])
      }
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  const loadTranscript = useCallback(async () => {
    if (!sessionId) return
    setTranscriptLoading(true)
    try {
      const res = await apiClient.get(`/api/interview-sessions/${sessionId}/utterances`)
      setTranscript(res.data || [])
    } catch {
      setTranscript([])
    } finally {
      setTranscriptLoading(false)
    }
  }, [sessionId])

  useEffect(() => { loadMemo() }, [loadMemo])
  useEffect(() => { if (activeTab === 'transcript') loadTranscript() }, [activeTab, loadTranscript])

  // Merged view: combine all memos from same stakeholder
  const mergedPainPoints = allMemos.flatMap(m => m.painPoints.map(p => ({ ...p, _memoDate: m.interviewDate })))
  const mergedRequirements = allMemos.flatMap(m => m.requirementCandidates.map(r => ({ ...r, _memoDate: m.interviewDate })))
  const mergedConstraints = allMemos.flatMap(m => m.constraintsAndAssumptions)
  const mergedUnresolved = allMemos.flatMap(m => m.unresolvedQuestions)
  const mergedSuggestions = allMemos.flatMap(m => m.nextInterviewSuggestions)
  const mergedTopics = [...new Set(allMemos.flatMap(m => m.topicsCovered))]

  const handleGenerate = async () => {
    if (!sessionId) return
    try {
      setGenerating(true)
      setError(null)
      const data = await generateInsightMemo(sessionId)
      setMemo(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || '無法產生洞察紀錄')
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return <div className="max-w-4xl mx-auto px-6 py-8 text-natural-500">載入中...</div>
  }

  if (!memo) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-natural-800 mb-4">訪談洞察紀錄</h1>
        <p className="text-natural-500 mb-4">尚未產生此訪談的洞察紀錄。</p>
        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:opacity-50"
        >
          {generating ? '分析中...' : '產生洞察紀錄'}
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => memo.projectId ? navigate(`/projects/${memo.projectId}`) : navigate(-1)} className="text-natural-400 hover:text-natural-600">&larr;</button>
        <h1 className="text-2xl font-bold text-natural-800">訪談紀錄</h1>
        {memo.stakeholderSummary && (
          <span className="text-sm text-natural-500">— {memo.stakeholderSummary.name}</span>
        )}
        {allMemos.length > 1 && (
          <span className="px-2 py-0.5 text-xs bg-sage-50 text-sage-600 rounded-full">
            {allMemos.length} 場訪談合併
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {memo.projectId && (
            <button
              onClick={() => navigate(`/projects/${memo.projectId}`)}
              className="px-3 py-1.5 text-xs font-medium text-sage-600 border border-sage-200 rounded-lg hover:bg-sage-50"
            >
              回到專案
            </button>
          )}
          {activeTab === 'memo' && memo.sourceDistinction && (
            <div className="flex gap-2 text-xs">
              <span className="px-2 py-0.5 bg-green-50 text-green-600 rounded">明確 {memo.sourceDistinction.explicit_statements}</span>
              <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded">推論 {memo.sourceDistinction.inferences}</span>
              <span className="px-2 py-0.5 bg-orange-50 text-orange-600 rounded">待驗 {memo.sourceDistinction.unverified}</span>
            </div>
          )}
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex rounded-lg border border-cream-300 bg-cream-100 p-0.5 w-fit mb-6">
        <button
          onClick={() => setActiveTab('memo')}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${activeTab === 'memo' ? 'bg-white text-natural-700 shadow-sm' : 'text-natural-400 hover:text-natural-600'}`}
        >
          洞察分析
        </button>
        <button
          onClick={() => setActiveTab('transcript')}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${activeTab === 'transcript' ? 'bg-white text-natural-700 shadow-sm' : 'text-natural-400 hover:text-natural-600'}`}
        >
          逐字稿
        </button>
      </div>

      {activeTab === 'transcript' ? (
        <div>
          {transcriptLoading ? (
            <p className="text-natural-500">載入逐字稿中...</p>
          ) : transcript.length === 0 ? (
            <p className="text-natural-500">尚無逐字稿資料。</p>
          ) : (
            <div>
              <div className="space-y-3">
                {transcript.map((utt, i) => (
                  <div key={i} className="flex gap-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 mt-0.5 ${
                      utt.speaker === 'interviewer' ? 'bg-sage-100 text-sage-700' : 'bg-cream-100 text-natural-700'
                    }`}>
                      {utt.speaker === 'interviewer' ? '訪談者' : '受訪者'}
                    </span>
                    <p className="text-sm text-natural-700 leading-relaxed">{utt.transcript}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
      <>

      {/* Basic info */}
      {memo.stakeholderSummary && (
        <div className="mb-6 p-4 bg-cream-50 rounded-xl">
          <div className="flex items-center gap-4 text-sm">
            <span className="font-medium text-natural-700">{memo.stakeholderSummary.name}</span>
            <span className="text-natural-500">{memo.stakeholderSummary.role}</span>
            {memo.stakeholderSummary.department && (
              <span className="text-natural-400">{memo.stakeholderSummary.department}</span>
            )}
            <span className="text-natural-400 ml-auto">
              {allMemos.length} 場，共 {allMemos.reduce((s, m) => s + (m.interviewDurationMinutes || 0), 0)} 分鐘
            </span>
          </div>
          {mergedTopics.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {mergedTopics.map((t, i) => (
                <span key={i} className="px-2 py-0.5 bg-white text-natural-600 text-xs rounded border border-cream-200">{t}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pain points */}
      {mergedPainPoints.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-natural-800 mb-3">痛點</h2>
          <div className="space-y-3">
            {mergedPainPoints.map((p, i) => (
              <div key={i} className="p-3 bg-white border border-cream-200 rounded-xl shadow-natural">
                <div className="flex items-center gap-2 mb-1">
                  <SeverityBadge severity={p.severity} />
                  <span className="text-sm font-medium text-natural-700">{p.description}</span>
                </div>
                {p.evidence_quote && (
                  <p className="text-xs text-natural-500 italic border-l-2 border-cream-200 pl-2 mt-1">
                    {p.evidence_quote}
                  </p>
                )}
                {p.affected_roles.length > 0 && (
                  <div className="text-xs text-natural-400 mt-1">影響：{p.affected_roles.join(', ')}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Requirement candidates */}
      {mergedRequirements.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-natural-800 mb-3">需求線索</h2>
          <div className="space-y-3">
            {mergedRequirements.map((r, i) => (
              <div key={i} className="p-3 bg-white border border-cream-200 rounded-xl shadow-natural">
                <div className="flex items-center gap-2 mb-1">
                  <SourceBadge source={r.source} />
                  <span className="text-sm font-medium text-natural-700">{r.description}</span>
                  <span className="text-xs text-natural-400 ml-auto">信心：{r.confidence}</span>
                </div>
                {r.evidence_quote && (
                  <p className="text-xs text-natural-500 italic border-l-2 border-cream-200 pl-2 mt-1">
                    {r.evidence_quote}
                  </p>
                )}
                {r.needs_validation_from.length > 0 && (
                  <div className="text-xs text-amber-600 mt-1">
                    需驗證：{r.needs_validation_from.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Constraints */}
      {mergedConstraints.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-natural-800 mb-3">限制與假設</h2>
          <div className="space-y-2">
            {mergedConstraints.map((c, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className={`px-1.5 py-0.5 text-xs rounded ${
                  c.type === 'assumption' ? 'bg-blue-50 text-blue-600' : 'bg-red-50 text-red-600'
                }`}>
                  {c.type === 'assumption' ? '假設' : '限制'}
                </span>
                <div>
                  <span className="text-natural-700">{c.content}</span>
                  <SourceBadge source={c.source} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Unresolved questions */}
      {mergedUnresolved.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-natural-800 mb-3">未解問題</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-200 text-left">
                  <th className="py-2 pr-4 font-medium text-natural-600">問題</th>
                  <th className="py-2 pr-4 font-medium text-natural-600">建議訪談對象</th>
                  <th className="py-2 font-medium text-natural-600">優先級</th>
                </tr>
              </thead>
              <tbody>
                {mergedUnresolved.map((q, i) => (
                  <tr key={i} className="border-b border-cream-200">
                    <td className="py-2 pr-4 text-natural-700">{q.question}</td>
                    <td className="py-2 pr-4 text-natural-600">{q.suggested_stakeholder_type}</td>
                    <td className="py-2"><SeverityBadge severity={q.priority} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Next suggestions */}
      {mergedSuggestions.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-natural-800 mb-3">建議下一步</h2>
          <div className="space-y-3">
            {mergedSuggestions.map((s, i) => (
              <div key={i} className="p-3 bg-sage-50 rounded-xl">
                <div className="text-sm font-medium text-sage-700">{s.target_role}：{s.objective}</div>
                {s.key_questions.length > 0 && (
                  <ul className="mt-1 text-xs text-sage-600 list-disc list-inside">
                    {s.key_questions.map((q, j) => <li key={j}>{q}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Regenerate */}
      <div className="pt-6 border-t border-cream-200">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-3 py-1.5 text-sm text-natural-500 border border-cream-300 rounded hover:bg-cream-50 disabled:opacity-50"
        >
          {generating ? '重新分析中...' : '重新產生'}
        </button>
      </div>
      </>
      )}
    </div>
  )
}
