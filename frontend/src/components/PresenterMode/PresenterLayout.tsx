import { useCallback, useEffect, useRef, useState } from 'react'
import { presentationAPI } from '@/api/presentation'
import { usePresentationSession } from '@/hooks/usePresentationSession'
import { useRealtimeTranscription } from '@/hooks/useRealtimeTranscription'
import { useSSEEvents } from '@/hooks/useSSEEvents'
import { useResponsiveLayout } from '@/hooks/useResponsiveLayout'
import type { CardState } from '@/types/presentation'
import type { CardStatus } from '@/types/questionCard'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import SessionHeader from './SessionHeader'
import SessionReportEnhanced from '../SessionReport/SessionReportEnhanced'
import SlideViewer from './SlideViewer'
import TopicCardsPanel from './TopicCardsPanel'
import TranscriptDisplay from './TranscriptDisplay'
import { simplifiedToTraditional } from '@/utils/chineseConverter'

interface PresenterLayoutProps {
  sessionId: string
  deckId: string
}

export default function PresenterLayout({ sessionId, deckId }: PresenterLayoutProps) {
  const [cardStates, setCardStates] = useState<CardState[]>([])
  const [cardsLoading, setCardsLoading] = useState(true)
  const [transcriptHistory, setTranscriptHistory] = useState<string[]>([]) // 保留最近 3 句
  const [pendingTranscript, setPendingTranscript] = useState('')
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const [slideOrientation, setSlideOrientation] = useState<'landscape' | 'portrait' | 'unknown'>('unknown')
  const [isPreparingToPresent, setIsPreparingToPresent] = useState(false)
  const hasConfirmedScriptPreview = true
  const scriptReadiness = { isReady: true, isPreparing: false, error: null as string | null }

  // 動態響應式佈局
  const { layoutConfig } = useResponsiveLayout(slideOrientation)

  const {
    session,
    currentSlide,
    currentSlideIndex,
    slides,
    isLoading,
    error,
    startPresenting,
    pausePresenting,
    nextSlide,
    previousSlide,
    endSession,
  } = usePresentationSession(sessionId)

  const currentSlideRef = useRef(currentSlide)
  const isPresentingRef = useRef(false)
  const hasRequestedInitialPreparationRef = useRef(false)
  const partialTranscriptRef = useRef('')
  const lastPartialMatchTextRef = useRef('')
  const partialMatchTimeoutRef = useRef<number | null>(null)
  const partialMatchInFlightRef = useRef(false)
  const pendingPartialMatchRef = useRef<string | null>(null)

  useEffect(() => {
    currentSlideRef.current = currentSlide
  }, [currentSlide])

  useEffect(() => {
    isPresentingRef.current = session?.status === 'presenting'
  }, [session?.status])

  useEffect(() => {
    return () => {
      if (partialMatchTimeoutRef.current) {
        clearTimeout(partialMatchTimeoutRef.current)
      }
    }
  }, [])

  const loadCardStates = useCallback(async () => {
    try {
      setCardsLoading(true)
      const states = await presentationAPI.getSessionCards(sessionId, deckId)
      setCardStates(states)
    } finally {
      setCardsLoading(false)
    }
  }, [deckId, sessionId])

  useEffect(() => {
    loadCardStates()
  }, [loadCardStates])

  useSSEEvents(sessionId, {
    onCardListening: (data) => updateCardFromEvent(data.card_id, 'listening', data.confidence, data.evidence),
    onCardCovered: (data) => updateCardFromEvent(data.card_id, 'covered', data.confidence, data.evidence),
    onCardProbablyCovered: (data) => updateCardFromEvent(data.card_id, 'probably_covered', data.confidence, data.evidence),
    onCardAtRisk: (data) => updateCardFromEvent(data.card_id, 'at_risk', data.confidence, data.evidence),
    onCardSkipped: (data) => updateCardFromEvent(data.card_id, 'skipped', data.confidence, data.evidence),
    onMatchingError: (data) => {
      console.error('Topic matching error received:', data)
      setTranscriptionError(`Topic matching failed: ${data.error}`)
    },
  })

  const handleTranscriptCompleted = useCallback((payload: {
    transcript: string
    itemId?: string
    startedAt?: string
    endedAt?: string
  }) => {
    let text = payload.transcript.trim()
    const activeSlide = currentSlideRef.current

    partialTranscriptRef.current = ''
    lastPartialMatchTextRef.current = ''
    pendingPartialMatchRef.current = null
    if (partialMatchTimeoutRef.current) {
      clearTimeout(partialMatchTimeoutRef.current)
      partialMatchTimeoutRef.current = null
    }

    if (!text || !activeSlide || !isPresentingRef.current) {
      setPendingTranscript('')
      return
    }

    // 強制轉換簡體中文為繁體中文
    text = simplifiedToTraditional(text)

    // UI 保留最近 3 句（改善使用體驗）
    setTranscriptHistory((prev) => {
      const newHistory = [...prev, text]
      // 只保留最近 3 句
      return newHistory.slice(-3)
    })
    setPendingTranscript('')
    setTranscriptionError(null)

    console.log('[PresenterLayout] 新轉錄（準備存入資料庫）:', text)

    presentationAPI.createUtterance(
      sessionId,
      text,
      activeSlide.id,
      payload.itemId,
      payload.startedAt,
      payload.endedAt
    )
      .then(() => {
        console.log('[PresenterLayout] 轉錄已存入資料庫:', text)
      })
      .catch((err) => {
        console.error('Failed to save utterance:', err)
        setTranscriptionError(err instanceof Error ? err.message : 'Failed to save transcript')
      })
  }, [sessionId])

  const sendPartialTranscriptMatch = useCallback((text: string, itemId?: string) => {
    const activeSlide = currentSlideRef.current
    const trimmed = text.trim()

    if (!activeSlide || !isPresentingRef.current || trimmed.length < 12) return
    if (trimmed === lastPartialMatchTextRef.current) return
    if (trimmed.length - lastPartialMatchTextRef.current.length < 8) return

    if (partialMatchInFlightRef.current) {
      pendingPartialMatchRef.current = trimmed
      return
    }

    partialMatchInFlightRef.current = true
    lastPartialMatchTextRef.current = trimmed

    presentationAPI.matchPartialTranscript(sessionId, trimmed, activeSlide.id, itemId)
      .catch((err) => {
        console.warn('[PresenterLayout] Partial transcript matching failed:', err)
      })
      .finally(() => {
        partialMatchInFlightRef.current = false
        const pending = pendingPartialMatchRef.current
        pendingPartialMatchRef.current = null
        if (pending && pending !== lastPartialMatchTextRef.current) {
          sendPartialTranscriptMatch(pending, itemId)
        }
      })
  }, [sessionId])

  const schedulePartialTranscriptMatch = useCallback((text: string, itemId?: string) => {
    if (partialMatchTimeoutRef.current) {
      clearTimeout(partialMatchTimeoutRef.current)
    }

    partialMatchTimeoutRef.current = window.setTimeout(() => {
      sendPartialTranscriptMatch(text, itemId)
    }, 750)
  }, [sendPartialTranscriptMatch])

  const {
    status: realtimeStatus,
    isRecording,
    isTranscribing,
    startTranscription,
    stopTranscription,
    error: realtimeError,
  } = useRealtimeTranscription({
    onSpeechStarted: () => {
      setTranscriptionError(null)
      setPendingTranscript('正在聽取...')
      partialTranscriptRef.current = ''
      lastPartialMatchTextRef.current = ''
      pendingPartialMatchRef.current = null
    },
    onTranscriptDelta: (delta, itemId) => {
      // 即時轉換簡體為繁體
      const convertedDelta = simplifiedToTraditional(delta)
      setPendingTranscript((previous) => {
        const nextTranscript =
          !previous || previous === '正在聽取...' || previous === '轉錄中...'
            ? convertedDelta
            : `${previous}${convertedDelta}`

        partialTranscriptRef.current = nextTranscript
        schedulePartialTranscriptMatch(nextTranscript, itemId)
        return nextTranscript
      })
    },
    onTranscriptCompleted: handleTranscriptCompleted,
  })

  const handleStartRequested = useCallback(() => {
    if (session?.status === 'presenting') return
    setTranscriptionError(null)
    setIsPreparingToPresent(true)
    if (realtimeStatus === 'idle' || realtimeStatus === 'error') {
      startTranscription()
    }
  }, [realtimeStatus, session?.status, startTranscription])

  useEffect(() => {
    if (hasRequestedInitialPreparationRef.current) return
    if (!session || !currentSlide) return

    if (session.status === 'idle' || session.status === 'ready') {
      hasRequestedInitialPreparationRef.current = true
      return
    }

    setIsPreparingToPresent(false)
  }, [currentSlide, session])


  useEffect(() => {
    if (session?.status === 'presenting' && realtimeStatus === 'idle') {
      startTranscription()
    }

    if (session?.status !== 'presenting' && !isPreparingToPresent && realtimeStatus !== 'idle') {
      stopTranscription()
    }

    // If session ended, show error message
    if (session?.status === 'ended' && realtimeStatus !== 'idle') {
      setTranscriptionError('Session has ended. Please start a new session to continue.')
    }
  }, [isPreparingToPresent, realtimeStatus, session?.status, startTranscription, stopTranscription])

  useEffect(() => {
    if (!isPreparingToPresent) return

    if (scriptReadiness.error) {
      setIsPreparingToPresent(false)
      setTranscriptionError(`建議逐字稿尚未準備完成：${scriptReadiness.error}`)
      return
    }

    if (realtimeError) {
      setIsPreparingToPresent(false)
      setTranscriptionError(`麥克風尚未連接成功：${realtimeError.message}`)
      return
    }

    if ((realtimeStatus === 'idle' || realtimeStatus === 'error') && !realtimeError) {
      startTranscription()
      return
    }

    if (
      hasConfirmedScriptPreview &&
      scriptReadiness.isReady &&
      realtimeStatus === 'connected'
    ) {
      void startPresenting().finally(() => {
        setIsPreparingToPresent(false)
      })
    }
  }, [
    hasConfirmedScriptPreview,
    isPreparingToPresent,
    realtimeError,
    realtimeStatus,
    scriptReadiness.error,
    scriptReadiness.isReady,
    startPresenting,
    startTranscription,
  ])

  if (isLoading) {
    return <LoadingSpinner label="載入演講 Session..." />
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 p-6">
        <div className="max-w-md rounded border border-red-200 bg-white p-6 text-center">
          <p className="mb-2 text-lg font-semibold text-red-700">載入失敗</p>
          <p className="text-sm text-gray-600">{error.message}</p>
        </div>
      </div>
    )
  }

  const isStartControlPreparing = isPreparingToPresent || scriptReadiness.isPreparing

  return (
    <div className="flex h-screen flex-col bg-cream-100 text-natural-800">
      <SessionHeader
        session={session}
        deckId={deckId}
        isRecording={isRecording}
        isPreparingToPresent={isStartControlPreparing}
        onStart={handleStartRequested}
        onPause={pausePresenting}
        onEnd={endSession}
      />

      {session?.status === 'ended' ? (
        <SessionReportEnhanced
          sessionId={sessionId}
          cardStates={cardStates}
          onBackToEditor={() => window.location.assign(`/editor/${deckId}`)}
          onRestart={() => window.location.assign(`/presenter/${deckId}`)}
        />
      ) : (
        <>
          <main className="flex min-h-0 flex-1 overflow-hidden">
            {/* 投影片區域 - 動態寬度 */}
            <div className={`min-w-0 p-4 transition-all duration-300 ${layoutConfig.slideArea.width}`}>
              <SlideViewer
                slide={currentSlide}
                currentSlideIndex={currentSlideIndex}
                totalSlides={slides.length}
                onPrevious={previousSlide}
                onNext={nextSlide}
                onOrientationChange={setSlideOrientation}
              />
            </div>

            {/* 右側：卡片 + 建議逐字稿 - 動態寬度和高度分配 */}
            <div className={`flex min-h-0 shrink-0 flex-col overflow-hidden pb-3 transition-all duration-300 ${layoutConfig.cardsArea.width}`}>
              {/* 卡片區域 - 動態高度 */}
              <div className={`min-h-0 overflow-hidden rounded-xl border border-cream-300 shadow-natural m-4 mb-0 ${layoutConfig.cardsArea.height}`}>
                {cardsLoading ? (
                  <div className="h-full bg-white">
                    <LoadingSpinner label="載入卡片..." />
                  </div>
                ) : (
                  <TopicCardsPanel
                    cardStates={cardStates}
                    currentSlideId={currentSlide?.id}
                    slideOrientation={slideOrientation}
                    cardHeight={layoutConfig.cardsLayout.cardHeight}
                    cardWidth={layoutConfig.cardsLayout.cardWidth}
                    onMarkStatus={markCardStatus}
                  />
                )}
              </div>

              {/* Script panel removed */}
            </div>
          </main>

          {/* 底部：轉錄區 - 動態高度 */}
          <div className={layoutConfig.transcriptArea.height}>
            <TranscriptDisplay
              transcriptHistory={transcriptHistory}
              pendingTranscript={pendingTranscript}
              isRecording={isRecording}
              isTranscribing={isTranscribing}
              error={realtimeError?.message ?? transcriptionError}
            />
          </div>

          {isPreparingToPresent && <PreparingOverlay />}
        </>
      )}
    </div>
  )

  function updateCardFromEvent(
    cardId: string | undefined,
    status: CardState['status'],
    confidence?: number,
    evidence?: unknown,
  ) {
    console.log('📋 updateCardFromEvent called:', {
      cardId,
      status,
      confidence,
      hasEvidence: !!evidence,
      totalCards: cardStates.length
    })

    if (!cardId) {
      console.warn('❌ No card_id provided in event')
      return
    }

    const matchingCard = cardStates.find(c => c.questionCard.id === cardId)
    console.log('🔍 Card lookup result:', {
      found: !!matchingCard,
      cardTitle: matchingCard?.questionCard.questionText,
      oldStatus: matchingCard?.status,
      newStatus: status
    })

    const evidenceTranscript =
      evidence && typeof evidence === 'object' && 'matchedTranscript' in evidence
        ? String((evidence as { matchedTranscript?: unknown }).matchedTranscript ?? '')
        : ''

    setCardStates((previous) =>
      previous.map((cardState) =>
        cardState.questionCard.id === cardId
          ? {
              ...cardState,
              status,
              confidence: confidence ?? cardState.confidence,
              evidence: evidence && typeof evidence === 'object' ? evidence as Record<string, unknown> : cardState.evidence,
              evidenceTranscript:
                evidenceTranscript
                  ? evidenceTranscript
                  : cardState.evidenceTranscript,
              questionCard: {
                ...cardState.questionCard,
                status,
                confidence: confidence ?? cardState.questionCard.confidence,
              },
            }
          : cardState,
      ),
    )
  }

  async function markCardStatus(cardState: CardState, status: CardStatus) {
    const confidence = status === 'covered' ? 1 : status === 'pending' ? null : cardState.confidence ?? null
    const evidenceTranscript = status === 'covered'
      ? 'Manually marked during presentation'
      : status === 'pending'
        ? null
        : cardState.evidenceTranscript ?? null

    const updated = await presentationAPI.updateCardState(sessionId, cardState.id, {
      status,
      confidence,
      evidenceTranscript,
      evidence: status === 'covered'
        ? { matchedTranscript: evidenceTranscript, source: 'manual' }
        : status === 'pending'
          ? null
          : cardState.evidence ?? null,
    })

    setCardStates((previous) =>
      previous.map((previousState) =>
        previousState.id === updated.id
          ? {
              ...previousState,
              ...updated,
              questionCard: {
                ...previousState.questionCard,
                status: updated.status,
                confidence: updated.confidence ?? undefined,
              },
            }
          : previousState,
      ),
    )
  }
}

function PreparingOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-cream-100/85 backdrop-blur-sm">
      <div className="flex flex-col items-center justify-center rounded-lg border border-cream-300 bg-white px-8 py-7 shadow-natural">
        <div className="mb-4 h-11 w-11 animate-spin rounded-full border-2 border-cream-200 border-t-sage-500" />
        <p className="text-base font-medium tracking-wide text-natural-700">準備中</p>
      </div>
    </div>
  )
}
