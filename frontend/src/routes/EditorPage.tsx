import { useEffect, useMemo, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { deckApi } from '@/api/decks'
import { questionCardsAPI, type QuestionCardFormData } from '@/api/questionCards'
import { useDeckEvents, type AnalysisCompleteEvent } from '@/hooks/useDeckEvents'
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

export default function EditorPage() {
  const { deckId } = useParams<{ deckId: string }>()
  const [plan, setPlan] = useState<InterviewPlan | null>(null)
  const [cards, setCards] = useState<QuestionCard[]>([])
  const [selectedThemeId, setSelectedThemeId] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadPlan = useCallback(async () => {
    if (!deckId) return
    const response = await apiClient.get(`/api/documents/${deckId}/interview-plan`)
    const data: InterviewPlan = response.data
    setPlan(data)

    if (data.themes.length > 0 && !selectedThemeId) {
      setSelectedThemeId(data.themes[0].id)
    }

    // Also load full cards for editing
    const fullCards = await questionCardsAPI.getDocumentCards(deckId)
    setCards(fullCards)

    return data
  }, [deckId, selectedThemeId])

  useEffect(() => {
    if (!deckId) return

    let isMounted = true

    async function init() {
      try {
        setIsLoading(true)
        setError(null)

        const deckStatus = await deckApi.getDeckStatus(deckId!)
        if (!isMounted) return

        if (deckStatus.status === 'failed') {
          setError(deckStatus.message ?? 'Analysis failed')
          setIsLoading(false)
          return
        }

        if (deckStatus.status === 'analyzing') {
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
  }, [deckId, loadPlan])

  // SSE: refresh when analysis completes
  useDeckEvents(deckId, {
    onAnalysisComplete: useCallback((_data: AnalysisCompleteEvent) => {
      setIsAnalyzing(false)
      loadPlan().catch(console.error)
    }, [loadPlan]),
    onError: useCallback(() => {}, []),
  })

  // Poll during analysis
  useEffect(() => {
    if (!deckId || !isAnalyzing) return
    const interval = window.setInterval(async () => {
      try {
        const status = await deckApi.getDeckStatus(deckId)
        if (status.status === 'analyzed') {
          setIsAnalyzing(false)
          await loadPlan()
        }
      } catch { /* ignore */ }
    }, 5000)
    return () => window.clearInterval(interval)
  }, [deckId, isAnalyzing, loadPlan])

  const selectedTheme = plan?.themes.find((t) => t.id === selectedThemeId) ?? null
  const themeCards = useMemo(
    () => cards.filter((c) => c.interviewThemeId === selectedThemeId).sort((a, b) => a.orderIndex - b.orderIndex),
    [cards, selectedThemeId],
  )

  async function updateCard(cardId: string, form: QuestionCardFormData) {
    const updated = await questionCardsAPI.updateCard(cardId, form)
    setCards((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
  }

  async function regenerateFollowup(cardId: string) {
    const updated = await questionCardsAPI.regenerateFollowup(cardId)
    setCards((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
    return updated
  }

  async function createCard() {
    if (!selectedTheme) return
    const firstSectionId = selectedTheme.cards[0]?.id ? undefined : undefined
    const newCard = await questionCardsAPI.createCard({
      sectionId: firstSectionId ?? selectedThemeId,
      questionText: '新問題',
      suggestedFollowup: '請輸入追問內容',
      importance: 'must',
    })
    setCards((prev) => [...prev, newCard])
  }

  async function deleteCard(card: QuestionCard) {
    await questionCardsAPI.deleteCard(card.id)
    setCards((prev) => prev.filter((c) => c.id !== card.id))
  }

  async function reorderCards(reordered: QuestionCard[]) {
    const updated = await questionCardsAPI.reorderSectionCards(
      selectedThemeId,
      reordered.map((c) => c.id)
    )
    setCards((prev) => {
      const others = prev.filter((c) => c.interviewThemeId !== selectedThemeId)
      return [...others, ...updated]
    })
  }

  if (isLoading) return <LoadingSpinner label="載入編輯器..." />

  if (isAnalyzing) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-md rounded border border-gray-200 bg-white p-6 text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-gray-200 border-t-blue-600" />
          <p className="text-lg font-semibold text-gray-950">正在分析文件</p>
          <p className="mt-2 text-sm text-gray-600">系統正在產生訪談單元與提問重點...</p>
          <p className="mt-3 text-xs text-gray-500">完成後將自動載入。</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 p-6">
        <div className="max-w-md rounded border border-red-200 bg-white p-6 text-center">
          <p className="mb-2 text-lg font-semibold text-red-700">無法載入編輯器</p>
          <p className="mb-5 text-sm text-gray-600">{error}</p>
          <Button onClick={() => window.location.reload()}>重試</Button>
        </div>
      </div>
    )
  }

  if (!plan || plan.themes.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 p-6">
        <div className="max-w-md rounded border border-gray-200 bg-white p-6 text-center">
          <p className="text-lg font-semibold text-gray-950">尚無訪談單元</p>
          <p className="mt-2 text-sm text-gray-600">請先上傳 BRD 初稿，系統將自動產生訪談計畫。</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-5">
        <div>
          <h1 className="text-base font-semibold text-gray-950">準備模式</h1>
          <p className="text-xs text-gray-500">
            {plan.themes.length} 個訪談單元 · {plan.totalCards} 個提問重點
          </p>
        </div>
        <Button onClick={() => window.location.assign(`/interview/${deckId}`)}>開始訪談</Button>
      </header>

      {/* Interview objective banner */}
      {plan.interviewObjective && (
        <div className="border-b border-blue-100 bg-blue-50 px-5 py-2">
          <p className="text-xs text-blue-800">
            <span className="font-medium">訪談目標：</span>{plan.interviewObjective}
          </p>
        </div>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-[15rem_minmax(0,1fr)] overflow-hidden">
        {/* Left: Theme list */}
        <aside className="min-h-0 overflow-y-auto border-r border-gray-200 bg-white p-3">
          <h2 className="mb-3 px-1 text-sm font-semibold text-gray-700">訪談單元</h2>
          <div className="space-y-1">
            {plan.themes.map((theme) => (
              <button
                key={theme.id}
                type="button"
                onClick={() => setSelectedThemeId(theme.id)}
                className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                  selectedThemeId === theme.id
                    ? 'border border-blue-400 bg-blue-50'
                    : 'border border-transparent hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-medium text-gray-600">
                    {theme.themeNumber}
                  </span>
                  <span className="text-sm font-medium text-gray-900 line-clamp-1">{theme.title}</span>
                </div>
                <div className="mt-1 flex items-center gap-2 pl-7">
                  <span className="text-xs text-gray-500">{theme.cards.length} 題</span>
                  {theme.estimatedMinutes && (
                    <span className="text-xs text-gray-400">~{theme.estimatedMinutes}min</span>
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
            <div className="mx-auto w-full max-w-3xl space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-gray-950">
                  {selectedTheme.themeNumber}. {selectedTheme.title}
                </h2>
                {selectedTheme.estimatedMinutes && (
                  <p className="mt-1 text-xs text-gray-500">預估 {selectedTheme.estimatedMinutes} 分鐘</p>
                )}
              </div>

              {/* Rationale */}
              <div className="rounded-lg border border-gray-200 bg-white p-4">
                <h3 className="mb-2 text-sm font-semibold text-gray-700">提問依據</h3>
                <p className="text-sm leading-relaxed text-gray-600 whitespace-pre-wrap">
                  {selectedTheme.rationale}
                </p>
              </div>

              {/* BRD Mapping */}
              {selectedTheme.brdMapping.length > 0 && (
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <h3 className="mb-2 text-sm font-semibold text-gray-700">對應 BRD 章節</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedTheme.brdMapping.map((section) => (
                      <span key={section} className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-0.5 text-xs text-gray-700">
                        {section}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Inline card editor below rationale */}
              <div className="rounded-lg border border-gray-200 bg-white">
                <div className="border-b border-gray-100 px-4 py-3">
                  <h3 className="text-sm font-semibold text-gray-700">
                    訪談問題 ({themeCards.length})
                  </h3>
                </div>
                <CardEditor
                  cards={themeCards}
                  onUpdate={updateCard}
                  onRegenerateFollowup={regenerateFollowup}
                  onDelete={deleteCard}
                  onReorder={reorderCards}
                  onCreate={createCard}
                />
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
              請選擇訪談單元
            </div>
          )}
        </section>
      </main>
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
