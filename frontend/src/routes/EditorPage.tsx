import { useEffect, useMemo, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { documentsAPI } from '@/api/documents'
import { questionCardsAPI, type QuestionCardFormData } from '@/api/questionCards'
import CardEditor from '@/components/EditorMode/CardEditor'
import Button from '@/components/common/Button'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import apiClient from '@/api/client'
import type { QuestionCard } from '@/types/questionCard'

interface InterviewTheme {
  id: string
  themeNumber: number
  title: string
  rationale: string
  brdMapping: string[]
  priority: number
  estimatedMinutes: number | null
  orderIndex: number
  isRequired: boolean
  isEnabled: boolean
  userNotes: string | null
  cards: ThemeCard[]
}

interface ThemeCard {
  id: string
  focusText: string
  questionText: string
  questionType: string
  importance: string
  suggestedFollowup: string
  expectedAnswerElements: string[]
  brdMapping: string[]
  estimatedSeconds: number
  orderIndex: number
  status: string
  confidence: number | null
  createdBy: string
}

interface InterviewPlan {
  documentId: string
  status: string
  interviewObjective: string | null
  priorityOrder: number[]
  priorityReasoning: string | null
  themes: InterviewTheme[]
  totalCards: number
}

interface SessionItem {
  id: string
  status: string
  startedAt: string | null
  endedAt: string | null
  createdAt: string
}

export default function EditorPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const [projectId, setProjectId] = useState<string | null>(null)
  const [plan, setPlan] = useState<InterviewPlan | null>(null)
  const [cards, setCards] = useState<QuestionCard[]>([])
  const [selectedThemeId, setSelectedThemeId] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisProgress, setAnalysisProgress] = useState<{
    message: string
    phase: string
    percentage: number
    currentTheme?: number
    totalThemes?: number
  }>({ message: '正在準備分析...', phase: 'init', percentage: 0 })
  const [error, setError] = useState<string | null>(null)
  const [showSessionPanel, setShowSessionPanel] = useState(false)
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)

  const loadPlan = useCallback(async () => {
    if (!documentId) return
    const response = await apiClient.get(`/api/documents/${documentId}/interview-plan`)
    const data: InterviewPlan = response.data
    setPlan(data)

    if (data.themes.length > 0) {
      setSelectedThemeId(prev => prev || data.themes[0].id)
    }

    // Also load full cards for editing
    const fullCards = await questionCardsAPI.getDocumentCards(documentId)
    setCards(fullCards)

    return data
  }, [documentId])

  useEffect(() => {
    if (!documentId) return

    let isMounted = true

    async function init() {
      try {
        setIsLoading(true)
        setError(null)

        // Load document to get project context
        try {
          const doc = await documentsAPI.getDocument(documentId!)
          if (doc.project_id) setProjectId(doc.project_id)
        } catch { /* continue without project context */ }

        const deckStatus = await documentsAPI.getDocumentStatus(documentId!)
        if (!isMounted) return

        if (deckStatus.status === 'failed') {
          setError(deckStatus.message ?? 'Analysis failed')
          setIsLoading(false)
          return
        }

        if (['uploading', 'uploaded', 'processing', 'converted', 'analyzing'].includes(deckStatus.status)) {
          setIsAnalyzing(true)
        }

        if (deckStatus.status === 'analyzed') {
          await loadPlan()
        }
      } catch (err) {
        if (isMounted) setError(getErrorMessage(err))
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    init()
    return () => { isMounted = false }
  }, [documentId, loadPlan])

  // SSE progress subscription during analysis
  useEffect(() => {
    if (!documentId || !isAnalyzing) return
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002'
    const eventSource = new EventSource(`${apiUrl}/api/events/sessions/${documentId}/stream`)

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'ANALYSIS_PROGRESS') {
          setAnalysisProgress({
            message: data.message || '分析中...',
            phase: data.phase || 'analyzing',
            percentage: data.percentage || 0,
            currentTheme: data.current_theme,
            totalThemes: data.total_themes,
          })
        } else if (data.type === 'THEMES_CREATED') {
          setAnalysisProgress(prev => ({
            ...prev,
            message: `已產生 ${data.theme_count} 個訪談單元，正在生成提問重點...`,
            phase: 'cards',
            percentage: 30,
          }))
        }
      } catch { /* ignore parse errors */ }
    }

    return () => eventSource.close()
  }, [documentId, isAnalyzing])

  // Poll during analysis
  useEffect(() => {
    if (!documentId || !isAnalyzing) return
    const interval = window.setInterval(async () => {
      try {
        const status = await documentsAPI.getDocumentStatus(documentId)
        if (status.status === 'analyzed') {
          setAnalysisProgress(prev => ({ ...prev, message: '分析完成！', percentage: 100 }))
          setTimeout(() => {
            setIsAnalyzing(false)
            loadPlan()
          }, 500)
        }
      } catch { /* ignore */ }
    }, 5000)
    return () => window.clearInterval(interval)
  }, [documentId, isAnalyzing, loadPlan])

  const selectedTheme = plan?.themes.find((t) => t.id === selectedThemeId) ?? null
  const themeCards = useMemo(
    () => cards.filter((c) => c.interviewThemeId === selectedThemeId).sort((a, b) => a.orderIndex - b.orderIndex),
    [cards, selectedThemeId],
  )

  async function handleOpenSessionPanel() {
    setShowSessionPanel(true)
    setSessionsLoading(true)
    try {
      const response = await apiClient.get(`/api/prep-sessions/${documentId}/interview-sessions`)
      setSessions(response.data)
    } catch {
      setSessions([])
    } finally {
      setSessionsLoading(false)
    }
  }

  async function updateCard(cardId: string, form: QuestionCardFormData) {
    try {
      const updated = await questionCardsAPI.updateCard(cardId, form)
      setCards((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function createCard() {
    if (!selectedTheme) return
    try {
      const firstSectionId = selectedTheme.cards[0]?.id ? undefined : undefined
      const newCard = await questionCardsAPI.createCard({
        sectionId: firstSectionId ?? selectedThemeId,
        questionText: '新問題',
        suggestedFollowup: '請輸入追問內容',
        importance: 'must',
      })
      setCards((prev) => [...prev, newCard])
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function deleteCard(card: QuestionCard) {
    try {
      await questionCardsAPI.deleteCard(card.id)
      setCards((prev) => prev.filter((c) => c.id !== card.id))
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function reorderCards(reordered: QuestionCard[]) {
    try {
      const updated = await questionCardsAPI.reorderSectionCards(
        selectedThemeId,
        reordered.map((c) => c.id)
      )
      setCards((prev) => {
        const others = prev.filter((c) => c.interviewThemeId !== selectedThemeId)
        return [...others, ...updated]
      })
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  if (isLoading) return <LoadingSpinner label="載入編輯器..." />

  if (isAnalyzing) {
    return (
      <div className="flex h-screen items-center justify-center bg-cream-100 p-6">
        <div className="w-full max-w-md rounded-2xl border border-cream-300 bg-white p-6">
          <div className="text-center mb-5">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-cream-300 border-t-sage-400" />
            <p className="text-lg font-semibold text-natural-700">正在分析文件</p>
          </div>

          {/* Progress Bar */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-natural-500">
                {analysisProgress.phase === 'themes' ? '階段 1/2：產生訪談單元' :
                 analysisProgress.phase === 'cards' ? '階段 2/2：產生提問重點' :
                 analysisProgress.phase === 'init' ? '準備中' : '分析中'}
              </span>
              <span className="text-xs font-mono text-natural-400">{analysisProgress.percentage}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-cream-200 overflow-hidden">
              <div
                className="h-full rounded-full bg-sage-400 transition-all duration-700 ease-out"
                style={{ width: `${analysisProgress.percentage}%` }}
              />
            </div>
          </div>

          {/* Current Step */}
          <div className="rounded-xl bg-cream-50 border border-cream-200 px-4 py-3">
            <p className="text-sm text-natural-600">{analysisProgress.message}</p>
            {analysisProgress.currentTheme && analysisProgress.totalThemes && (
              <p className="mt-1 text-xs text-natural-400">
                單元 {analysisProgress.currentTheme} / {analysisProgress.totalThemes}
              </p>
            )}
          </div>

          <p className="mt-4 text-center text-xs text-natural-400">完成後將自動載入</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-cream-100 p-6">
        <div className="max-w-md rounded border border-red-200 bg-white p-6 text-center">
          <p className="mb-2 text-lg font-semibold text-red-700">無法載入編輯器</p>
          <p className="mb-5 text-sm text-natural-500">{error}</p>
          <Button onClick={() => window.location.reload()}>重試</Button>
        </div>
      </div>
    )
  }

  if (!plan || plan.themes.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center bg-cream-100 p-6">
        <div className="max-w-md rounded border border-cream-300 bg-white p-6 text-center">
          <p className="text-lg font-semibold text-natural-700">尚無訪談單元</p>
          <p className="mt-2 text-sm text-natural-500">請先上傳 BRD 初稿，系統將自動產生訪談計畫。</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-cream-100">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-cream-300 bg-white px-5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => projectId ? window.location.assign(`/projects/${projectId}`) : window.history.back()}
            className="text-natural-400 hover:text-natural-600 text-sm"
          >
            &larr; 返回專案
          </button>
          <div>
            <h1 className="text-base font-semibold text-natural-700">準備模式</h1>
            <p className="text-xs text-natural-400">
              {plan.themes.length} 個訪談單元 · {plan.totalCards} 個提問重點
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={handleOpenSessionPanel}>管理訪談</Button>
          <Button onClick={() => window.location.assign(`/interview/${documentId}${projectId ? `?projectId=${projectId}` : ''}`)}>開始訪談</Button>
        </div>
      </header>

      {/* Interview objective banner */}
      {plan.interviewObjective && (
        <div className="border-b border-sage-100 bg-sage-50 px-5 py-2">
          <p className="text-xs text-sage-500">
            <span className="font-medium">訪談目標：</span>{plan.interviewObjective}
          </p>
        </div>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-[15rem_minmax(0,1fr)] overflow-hidden">
        {/* Left: Theme list */}
        <aside className="min-h-0 overflow-y-auto border-r border-cream-300 bg-white p-3">
          <h2 className="mb-3 px-1 text-sm font-semibold text-natural-600">訪談單元</h2>
          <div className="space-y-1">
            {plan.themes.map((theme) => (
              <button
                key={theme.id}
                type="button"
                onClick={() => setSelectedThemeId(theme.id)}
                className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                  selectedThemeId === theme.id
                    ? 'border border-sage-300 bg-sage-50'
                    : 'border border-transparent hover:bg-cream-100'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cream-200 text-xs font-medium text-natural-500">
                    {theme.themeNumber}
                  </span>
                  <span className="text-sm font-medium text-natural-700 line-clamp-1">{theme.title}</span>
                </div>
                <div className="mt-1 flex items-center gap-2 pl-7">
                  <span className="text-xs text-natural-400">{theme.cards.length} 題</span>
                  {theme.estimatedMinutes && (
                    <span className="text-xs text-natural-300">~{theme.estimatedMinutes}min</span>
                  )}
                  {theme.priority <= 3 && (
                    <span className="rounded bg-amber-50 px-1 py-0.5 text-[10px] font-medium text-amber-700">優先</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Right: Theme content + inline card editor */}
        <section className="flex min-h-0 flex-col overflow-y-auto p-5">
          {selectedTheme ? (
            <div className="mx-auto w-full max-w-4xl space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-natural-700">
                  {selectedTheme.themeNumber}. {selectedTheme.title}
                </h2>
                {selectedTheme.estimatedMinutes && (
                  <p className="mt-1 text-xs text-natural-400">預估 {selectedTheme.estimatedMinutes} 分鐘</p>
                )}
              </div>

              {/* Rationale */}
              <div className="rounded-lg border border-cream-300 bg-white p-4">
                <h3 className="mb-2 text-sm font-semibold text-natural-600">提問依據</h3>
                <p className="text-sm leading-relaxed text-natural-500 whitespace-pre-wrap">
                  {selectedTheme.rationale}
                </p>
              </div>

              {/* BRD Mapping */}
              {selectedTheme.brdMapping.length > 0 && (
                <div className="rounded-lg border border-cream-300 bg-white p-4">
                  <h3 className="mb-2 text-sm font-semibold text-natural-600">對應 BRD 章節</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedTheme.brdMapping.map((section) => (
                      <span key={section} className="rounded-full border border-cream-300 bg-cream-100 px-2.5 py-0.5 text-xs text-natural-600">
                        {section}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Inline card editor below rationale */}
              <div className="rounded-lg border border-cream-300 bg-white">
                <div className="border-b border-cream-200 px-4 py-3">
                  <h3 className="text-sm font-semibold text-natural-600">
                    訪談問題 ({themeCards.length})
                  </h3>
                </div>
                <CardEditor
                  cards={themeCards}
                  onUpdate={updateCard}
                  onDelete={deleteCard}
                  onReorder={reorderCards}
                  onCreate={createCard}
                />
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-natural-300">
              請選擇訪談單元
            </div>
          )}
        </section>
      </main>

      {/* Session management sidebar */}
      {showSessionPanel && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/20" onClick={() => setShowSessionPanel(false)} />
          <aside className="relative w-96 bg-white shadow-xl overflow-y-auto">
            <div className="sticky top-0 flex items-center justify-between border-b border-cream-300 bg-white px-5 py-4">
              <h2 className="text-base font-semibold text-natural-700">訪談記錄</h2>
              <button
                type="button"
                onClick={() => setShowSessionPanel(false)}
                className="rounded p-1 text-natural-300 hover:text-natural-500"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4">
              {sessionsLoading ? (
                <p className="text-sm text-natural-400 text-center py-8">載入中...</p>
              ) : sessions.length === 0 ? (
                <p className="text-sm text-natural-400 text-center py-8">尚無訪談記錄</p>
              ) : (
                <div className="space-y-3">
                  {sessions.map((session) => (
                    <div key={session.id} className="rounded-lg border border-cream-300 p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${
                          session.status === 'ended' ? 'bg-green-50 text-green-700' :
                          session.status === 'interviewing' ? 'bg-sage-50 text-sage-500' :
                          'bg-cream-100 text-natural-500'
                        }`}>
                          {session.status === 'ended' ? '已結束' :
                           session.status === 'interviewing' ? '進行中' :
                           session.status === 'paused' ? '已暫停' : '未開始'}
                        </span>
                        <span className="text-xs text-natural-300">
                          {session.createdAt ? new Date(session.createdAt).toLocaleDateString('zh-TW') : ''}
                        </span>
                      </div>
                      <p className="text-xs text-natural-400 mb-2">
                        {session.startedAt ? new Date(session.startedAt).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' }) : '未開始'}
                        {session.endedAt ? ` — ${new Date(session.endedAt).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}` : ''}
                      </p>
                      <div className="flex gap-2">
                        {session.status === 'ended' && (
                          <button
                            type="button"
                            onClick={() => window.location.assign(`/interview/${documentId}/report/${session.id}`)}
                            className="rounded border border-cream-300 px-2 py-1 text-xs text-natural-500 hover:bg-cream-100"
                          >
                            查看報告
                          </button>
                        )}
                        {(session.status === 'interviewing' || session.status === 'paused') && (
                          <button
                            type="button"
                            onClick={() => window.location.assign(`/interview/${documentId}`)}
                            className="rounded bg-sage-500 px-2 py-1 text-xs text-white hover:bg-sage-500"
                          >
                            繼續訪談
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}

function getErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
  }
  return error instanceof Error ? error.message : 'Failed to load editor'
}
