import { useEffect, useMemo, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { deckApi } from '@/api/decks'
import { questionCardsAPI, type QuestionCardFormData } from '@/api/questionCards'
import { useDeckEvents, type AnalysisCompleteEvent, type CardCreatedEvent } from '@/hooks/useDeckEvents'
import CardEditor from '@/components/EditorMode/CardEditor'
import SlidePreview from '@/components/EditorMode/SlidePreview'
import Button from '@/components/common/Button'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import { formatTokenCount, formatUsdCost } from '@/utils/formatters'
import type { Slide } from '@/types/presentation'
import type { QuestionCard } from '@/types/questionCard'

type ApiRecord = Record<string, unknown>

function asString(value: unknown) {
  return typeof value === 'string' ? value : undefined
}

function asNumber(value: unknown) {
  return typeof value === 'number' ? value : 0
}

function normalizeImageUrl(value: unknown) {
  const url = asString(value)
  if (!url) return undefined
  return url.replace('http://minio:9000', 'http://localhost:9000')
}

function normalizeSlide(raw: ApiRecord): Slide {
  return {
    id: asString(raw.id) ?? '',
    deckId: asString(raw.deckId) ?? asString(raw.deck_id) ?? '',
    pageNumber: asNumber(raw.pageNumber ?? raw.page_number),
    title: asString(raw.title),
    imageUrl: normalizeImageUrl(raw.imageUrl ?? raw.image_url),
    extractedText: asString(raw.extractedText) ?? asString(raw.extracted_text),
    aiSummary: asString(raw.aiSummary) ?? asString(raw.ai_summary),
    topicCardsCount: asNumber(raw.topicCardsCount ?? raw.topic_cards_count),
  }
}

export default function EditorPage() {
  const { deckId } = useParams<{ deckId: string }>()
  const [slides, setSlides] = useState<Slide[]>([])
  const [cards, setCards] = useState<QuestionCard[]>([])
  const [selectedSlideId, setSelectedSlideId] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [processingStatus, setProcessingStatus] = useState<string | null>(null)
  const [processingMessage, setProcessingMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [progress, setProgress] = useState<{
    currentCard: number
    currentSlide: number
    totalSlides: number
    percentage: number
  } | null>(null)
  const [deckAnalysisCost, setDeckAnalysisCost] = useState<{
    costUsd: number
    totalTokens: number
  }>({ costUsd: 0, totalTokens: 0 })

  const refreshEditorData = useCallback(async () => {
    if (!deckId) return null

    const [analysis, deckCards] = await Promise.all([
      deckApi.getDeckAnalysis(deckId),
      questionCardsAPI.getDocumentCards(deckId),
    ])
    const normalizedSlides = Array.isArray(analysis.slides)
      ? analysis.slides.map((slide) => normalizeSlide(slide))
      : []

    setSlides(normalizedSlides)
    setCards(deckCards)
    setDeckAnalysisCost({
      costUsd: analysis.cost_usd ?? 0,
      totalTokens: analysis.ai_usage?.totalTokens ?? 0,
    })
    setSelectedSlideId((current) => {
      if (current && normalizedSlides.some((slide) => slide.id === current)) return current
      return normalizedSlides[0]?.id ?? ''
    })

    return analysis
  }, [deckId])

  // Fetch a single new card by ID
  const fetchNewCard = useCallback(async (cardId: string) => {
    try {
      const card = await questionCardsAPI.getCard(cardId)
      setCards((previous) => {
        // Check if card already exists
        const exists = previous.some((c) => c.id === cardId)
        if (exists) {
          return previous
        }
        // Add new card and sort by slide page number and order index
        return [...previous, card].sort(
          (a, b) => a.sectionNumber - b.sectionNumber || a.orderIndex - b.orderIndex
        )
      })
      setSlides((previous) =>
        previous.map((slide) =>
          slide.id === card.sectionId
            ? { ...slide, topicCardsCount: Math.max(slide.topicCardsCount ?? 0, (card.orderIndex ?? 0) + 1) }
            : slide
        )
      )
    } catch (err) {
      console.error('Failed to fetch new card:', err)
    }
  }, [])

  // SSE event handlers
  useDeckEvents(deckId, {
    onCardCreated: useCallback((data: CardCreatedEvent) => {
      console.log('📋 New card created, fetching...', data.card_id)
      setIsAnalyzing(true)
      setProgress({
        currentCard: data.progress.current_card,
        currentSlide: data.progress.current_slide,
        totalSlides: data.progress.total_slides,
        percentage: data.progress.percentage
      })
      // Fetch the new card
      fetchNewCard(data.card_id)
      refreshEditorData().catch((err) => console.error('Failed to refresh editor data:', err))
    }, [fetchNewCard, refreshEditorData]),

    onAnalysisComplete: useCallback((data: AnalysisCompleteEvent) => {
      console.log('✅ Analysis complete!', data)
      setIsAnalyzing(false)
      setProgress(null)
      setProcessingStatus(null)
      setProcessingMessage(null)
      refreshEditorData().catch((err) => console.error('Failed to refresh completed analysis:', err))
    }, [refreshEditorData]),

    onError: useCallback((error: Error) => {
      console.error('SSE error:', error)
      // Don't set error state, just log it
    }, [])
  })

  useEffect(() => {
    if (!deckId) return

    let isMounted = true
    let retryTimer: number | undefined

    const readyStatuses = new Set(['uploaded', 'converted', 'analyzing', 'analyzed'])

    async function loadEditor() {
      try {
        setIsLoading(true)
        setError(null)

        const deckStatus = await deckApi.getDeckStatus(deckId!)
        if (!isMounted) return

        setProcessingStatus(deckStatus.status)
        setProcessingMessage(deckStatus.message ?? null)

        if (deckStatus.status === 'failed') {
          setError(deckStatus.message ?? 'Deck processing failed')
          setIsLoading(false)
          return
        }

        if (!readyStatuses.has(deckStatus.status)) {
          setIsLoading(false)
          retryTimer = window.setTimeout(loadEditor, 5000)
          return
        }

        const analysis = await refreshEditorData()

        if (!isMounted) return

        // Set analyzing state if still analyzing (SSE will handle updates)
        if (deckStatus.status === 'analyzing' || analysis?.status === 'analyzing') {
          setIsAnalyzing(true)
          setProcessingStatus(null)
          setProcessingMessage(null)
        } else {
          setIsAnalyzing(false)
          setProcessingStatus(null)
          setProcessingMessage(null)
        }

        // Note: PrepSession is now auto-created when deck is uploaded
        // No need to create it here anymore
      } catch (err) {
        if (isMounted) {
          const message = getErrorMessage(err)
          if (message.includes('not ready for analysis')) {
            setIsLoading(false)
            retryTimer = window.setTimeout(loadEditor, 5000)
            return
          }
          setError(message)
        }
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    loadEditor()

    return () => {
      isMounted = false
      if (retryTimer) window.clearTimeout(retryTimer)
    }
  }, [deckId, refreshEditorData])

  useEffect(() => {
    if (!deckId || !isAnalyzing) return

    let isMounted = true
    const interval = window.setInterval(async () => {
      try {
        const [deckStatus, analysis] = await Promise.all([
          deckApi.getDeckStatus(deckId),
          refreshEditorData(),
        ])

        if (!isMounted) return

        if (deckStatus.status === 'analyzed' || analysis?.status === 'analyzed') {
          setIsAnalyzing(false)
          setProgress(null)
          setProcessingStatus(null)
          setProcessingMessage(null)
        }

        if (deckStatus.status === 'failed') {
          setIsAnalyzing(false)
          setError(deckStatus.message ?? 'Deck processing failed')
        }
      } catch (err) {
        console.warn('Background editor refresh failed:', err)
      }
    }, 2500)

    return () => {
      isMounted = false
      window.clearInterval(interval)
    }
  }, [deckId, isAnalyzing, refreshEditorData])

  const selectedSlide = slides.find((slide) => slide.id === selectedSlideId) ?? null
  const slideCards = useMemo(
    () => cards.filter((card) => card.sectionId === selectedSlideId).sort((a, b) => a.orderIndex - b.orderIndex),
    [cards, selectedSlideId],
  )

  async function updateCard(cardId: string, form: QuestionCardFormData) {
    const updated = await questionCardsAPI.updateCard(cardId, form)
    setCards((previous) => previous.map((card) => (card.id === updated.id ? updated : card)))
  }

  async function regenerateCardScript(cardId: string) {
    const updated = await questionCardsAPI.regenerateFollowup(cardId)
    setCards((previous) => previous.map((card) => (card.id === updated.id ? updated : card)))
    return updated
  }

  async function createCard() {
    if (!selectedSlide) return
    const newCard = await questionCardsAPI.createCard({
      sectionId: selectedSlide.id,
      questionText: '新問題',
      suggestedFollowup: '請輸入追問內容',
      importance: 'must',
    })
    setCards((previous) => [...previous, newCard])
  }

  async function deleteCard(card: QuestionCard) {
    await questionCardsAPI.deleteCard(card.id)
    setCards((previous) => previous.filter((item) => item.id !== card.id))
  }

  async function reorderCards(reorderedSlideCards: QuestionCard[]) {
    const updated = await questionCardsAPI.reorderSectionCards(
      selectedSlideId,
      reorderedSlideCards.map((item) => item.id)
    )
    setCards((previous) => {
      const otherCards = previous.filter((item) => item.sectionId !== selectedSlideId)
      return [...otherCards, ...updated].sort(
        (a, b) => a.sectionNumber - b.sectionNumber || a.orderIndex - b.orderIndex
      )
    })
  }

  if (isLoading) {
    return <LoadingSpinner label="載入編輯器..." />
  }

  if (processingStatus) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-md rounded border border-gray-200 bg-white p-6 text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-gray-200 border-t-blue-600" />
          <p className="text-lg font-semibold text-gray-950">文件處理中</p>
          <p className="mt-2 text-sm text-gray-600">
            {processingMessage ?? `目前狀態：${processingStatus}`}
          </p>
          <p className="mt-3 text-xs text-gray-500">系統會自動重新檢查，完成後進入準備模式。</p>
          <div className="mt-5">
            <Button variant="secondary" onClick={() => window.location.reload()}>手動重試</Button>
          </div>
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

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-5">
        <div>
          <h1 className="text-lg font-semibold text-gray-950">準備模式</h1>
          <div className="flex items-center gap-2">
            <p className="text-xs text-gray-500">Deck {deckId}</p>
            <span className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-600">
              分析成本 {formatUsdCost(deckAnalysisCost.costUsd)} · {formatTokenCount(deckAnalysisCost.totalTokens)} tokens
            </span>
            {isAnalyzing && progress && (
              <span className="flex items-center gap-1.5 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                正在生成卡片 {progress.currentCard} 張 ({progress.percentage}%)
              </span>
            )}
            {isAnalyzing && !progress && (
              <span className="flex items-center gap-1.5 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                正在生成卡片...
              </span>
            )}
          </div>
        </div>
        <Button onClick={() => window.location.assign(`/interview/${deckId}`)}>開始訪談</Button>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-[14rem_minmax(0,1fr)_24rem] overflow-hidden">
        {/* Left sidebar - Slide thumbnails */}
        <aside className="min-h-0 overflow-y-auto border-r border-gray-200 bg-white p-3">
          <h2 className="mb-3 px-1 text-sm font-semibold text-gray-700">段落</h2>
          <div className="space-y-2">
            {slides.map((slide) => (
              <button
                key={slide.id}
                type="button"
                onClick={() => setSelectedSlideId(slide.id)}
                className={`w-full rounded border p-2 text-left transition-colors ${
                  selectedSlideId === slide.id ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white hover:bg-gray-50'
                }`}
              >
                {slide.imageUrl ? (
                  <div className="mb-2 aspect-video overflow-hidden rounded border border-gray-200 bg-gray-100">
                    <img src={slide.imageUrl} alt={`Slide ${slide.pageNumber}`} className="h-full w-full object-cover" />
                  </div>
                ) : (
                  <div className="mb-2 flex aspect-video items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50 text-xs text-gray-400">
                    No preview
                  </div>
                )}
                <p className="text-sm font-medium text-gray-950">段落 {slide.pageNumber}</p>
                <p className="mt-0.5 line-clamp-1 text-xs text-gray-600">{slide.title || '未命名'}</p>
              </button>
            ))}
          </div>
        </aside>

        {/* Center - Large slide preview */}
        <section className="flex min-h-0 flex-col overflow-hidden p-4">
          <SlidePreview slide={selectedSlide} />
        </section>

        {/* Right sidebar - Cards editor with inline editing */}
        <aside className="flex min-h-0 flex-col border-l border-gray-200 bg-white">
          {isAnalyzing && slideCards.length === 0 && (
            <div className="flex items-center justify-center p-6 text-center">
              <div>
                <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-gray-200 border-t-blue-600" />
                <p className="text-sm font-medium text-gray-700">AI 正在分析段落</p>
                <p className="mt-1 text-xs text-gray-500">卡片將即時出現，無需重新整理</p>
                {progress && (
                  <p className="mt-2 text-xs font-medium text-blue-600">
                    進度：{progress.currentSlide}/{progress.totalSlides} 段落 · {progress.currentCard} 個問題
                  </p>
                )}
              </div>
            </div>
          )}
          <CardEditor
            cards={slideCards}
            onUpdate={updateCard}
            onRegenerateFollowup={regenerateCardScript}
            onDelete={deleteCard}
            onReorder={reorderCards}
            onCreate={createCard}
          />
        </aside>
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
