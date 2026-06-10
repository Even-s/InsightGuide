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
import TranscriptDisplay from './TranscriptDisplay'
import { simplifiedToTraditional } from '@/utils/chineseConverter'

interface PresenterLayoutProps {
  sessionId: string
  deckId: string
}

export default function PresenterLayout({ sessionId, deckId }: PresenterLayoutProps) {
  const [cardStates, setCardStates] = useState<CardState[]>([])
  const [, setCardsLoading] = useState(true)
  const [transcriptHistory, setTranscriptHistory] = useState<string[]>([]) // 保留最近 3 句
  const [pendingTranscript, setPendingTranscript] = useState('')
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const [slideOrientation] = useState<'landscape' | 'portrait' | 'unknown'>('unknown')
  const [isPreparingToPresent, setIsPreparingToPresent] = useState(false)
  const hasConfirmedScriptPreview = true
  const scriptReadiness = { isReady: true, isPreparing: false, error: null as string | null }

  // 動態響應式佈局
  const { layoutConfig } = useResponsiveLayout(slideOrientation)

  const {
    session,
    themes,
    currentTheme,
    currentThemeIndex,
    currentSlide,
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
  const currentThemeRef = useRef(currentTheme)
  const isPresentingRef = useRef(false)
  const hasRequestedInitialPreparationRef = useRef(false)
  const partialTranscriptRef = useRef('')
  const partialMatchTimeoutRef = useRef<number | null>(null)
  const partialMatchInFlightRef = useRef(false)
  const pendingPartialMatchRef = useRef<string | null>(null)
  const lastPartialMatchTextRef = useRef('')

  useEffect(() => {
    currentSlideRef.current = currentSlide
    currentThemeRef.current = currentTheme
  }, [currentSlide, currentTheme])

  useEffect(() => {
    isPresentingRef.current = session?.status === 'interviewing'
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
    onCardListening: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'listening'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardCovered: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'sufficient'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardProbablyCovered: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'probably_sufficient'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardAtRisk: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'at_risk'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardSkipped: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'skipped'), data.confidence, data.evidence, data.evidenceTranscript),
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
    const activeTheme = currentThemeRef.current
    const activeSlide = currentSlideRef.current
    const activeId = activeTheme?.id ?? activeSlide?.id

    partialTranscriptRef.current = ''
    lastPartialMatchTextRef.current = ''
    pendingPartialMatchRef.current = null
    if (partialMatchTimeoutRef.current) {
      clearTimeout(partialMatchTimeoutRef.current)
      partialMatchTimeoutRef.current = null
    }

    if (!text || !activeId || !isPresentingRef.current) {
      setPendingTranscript('')
      return
    }

    text = simplifiedToTraditional(text)

    setTranscriptHistory((prev) => {
      const newHistory = [...prev, text]
      return newHistory.slice(-3)
    })
    setPendingTranscript('')
    setTranscriptionError(null)

    // Save utterance — backend will classify speaker and evaluate
    presentationAPI.createUtterance(
      sessionId,
      text,
      activeId,
      payload.itemId,
      payload.startedAt,
      payload.endedAt
    )
      .catch((err) => {
        console.error('Failed to save utterance:', err)
        setTranscriptionError(err instanceof Error ? err.message : 'Failed to save transcript')
      })
  }, [sessionId])

  const sendPartialTranscriptMatch = useCallback((text: string, itemId?: string) => {
    const activeTheme = currentThemeRef.current
    const activeSlide = currentSlideRef.current
    const activeId = activeTheme?.id ?? activeSlide?.id
    const trimmed = text.trim()

    if (!activeId || !isPresentingRef.current || trimmed.length < 12) return
    if (trimmed === lastPartialMatchTextRef.current) return
    if (trimmed.length - lastPartialMatchTextRef.current.length < 8) return

    if (partialMatchInFlightRef.current) {
      pendingPartialMatchRef.current = trimmed
      return
    }

    partialMatchInFlightRef.current = true
    lastPartialMatchTextRef.current = trimmed

    presentationAPI.matchPartialTranscript(sessionId, trimmed, activeId, itemId)
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
    }, 800)
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
    },
    onTranscriptDelta: (delta, itemId) => {
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

  const handleStartRequested = useCallback(async () => {
    if (session?.status === 'interviewing') return
    setTranscriptionError(null)
    setIsPreparingToPresent(true)

    try {
      // Start session first (so isPresentingRef becomes true)
      await startPresenting()

      // Then start transcription
      if (realtimeStatus === 'idle' || realtimeStatus === 'error') {
        startTranscription()
      }
    } catch (err) {
      console.error('Failed to start interview:', err)
      setTranscriptionError(err instanceof Error ? err.message : 'Failed to start')
    } finally {
      setIsPreparingToPresent(false)
    }
  }, [realtimeStatus, session?.status, startPresenting, startTranscription])

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
    if (session?.status === 'interviewing' && realtimeStatus === 'idle') {
      startTranscription()
    }

    if (session?.status !== 'interviewing' && !isPreparingToPresent && realtimeStatus !== 'idle') {
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
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <InterviewOutputsPanel sessionId={sessionId} />
          <SessionReportEnhanced
            sessionId={sessionId}
            cardStates={cardStates}
            onBackToEditor={() => window.location.assign(`/editor/${deckId}`)}
            onRestart={() => window.location.assign(`/presenter/${deckId}`)}
          />
        </div>
      ) : (
        <>
          <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {/* Theme nav bar */}
            <div className="flex shrink-0 items-center justify-between border-b border-gray-200 bg-white px-5 py-2.5">
              <button type="button" onClick={previousSlide} disabled={currentThemeIndex === 0}
                className="rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-30">
                ← 上一單元
              </button>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-900">
                  {currentTheme ? `${currentTheme.themeNumber}. ${currentTheme.title}` : `段落 ${currentSlide?.pageNumber ?? ''}`}
                </p>
                <p className="text-xs text-gray-500">
                  單元 {currentThemeIndex + 1} / {themes.length || slides.length}
                </p>
              </div>
              <button type="button" onClick={nextSlide} disabled={currentThemeIndex >= (themes.length || slides.length) - 1}
                className="rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-30">
                下一單元 →
              </button>
            </div>

            {/* Questions with inline strikethrough status */}
            <div className="min-h-0 flex-1 overflow-y-auto bg-gray-50 px-6 py-5">
              {currentTheme ? (
                <div className="mx-auto max-w-3xl space-y-4">
                  {(() => {
                    const cardStateMap = new Map(cardStates.map(cs => [cs.questionCard.id, cs.status]))
                    const completedStatuses = new Set(['sufficient', 'covered', 'manually_checked'])

                    const groups: { focus: string; cards: typeof currentTheme.cards }[] = []
                    let cur: typeof groups[number] | null = null
                    for (const card of currentTheme.cards) {
                      const f = card.focusText || ''
                      if (!cur || cur.focus !== f) {
                        cur = { focus: f, cards: [card] }
                        groups.push(cur)
                      } else {
                        cur.cards.push(card)
                      }
                    }

                    return groups.map((group, gi) => {
                      const groupCardStates = group.cards.map(c => {
                        const cs = cardStates.find(s => s.questionCard.id === c.id)
                        return { card: c, status: cardStateMap.get(c.id) ?? 'pending', confidence: cs?.confidence ?? 0 }
                      })
                      const groupDone = groupCardStates.every(c => completedStatuses.has(c.status))
                      const groupConfidenceSum = groupCardStates.reduce((sum, c) => sum + (completedStatuses.has(c.status) ? 1 : (c.confidence ?? 0)), 0)
                      const groupProgress = groupCardStates.length > 0 ? Math.round((groupConfidenceSum / groupCardStates.length) * 100) : 0

                      return (
                        <div key={gi} className={`relative rounded-xl border shadow-sm overflow-hidden ${groupDone ? 'border-green-200' : 'border-gray-200'}`}>
                          {/* Water fill background for the whole group */}
                          <div
                            className="pointer-events-none absolute inset-x-0 bottom-0 z-0 transition-[height] duration-1000 ease-out"
                            style={{ height: `${groupProgress}%` }}
                            aria-hidden="true"
                          >
                            <div className={`absolute inset-0 ${groupDone ? 'bg-green-100/60' : 'bg-blue-50/50'}`} />
                          </div>

                          {/* Content on top */}
                          <div className="relative z-10">
                            {group.focus && (
                              <div className={`border-b px-5 py-2.5 ${groupDone ? 'border-green-200' : 'border-blue-100'}`}>
                                <div className="flex items-center justify-between">
                                  <p className={`text-sm font-semibold ${groupDone ? 'text-green-800 line-through' : 'text-blue-900'}`}>
                                    {groupDone && '✓ '}{group.focus}
                                  </p>
                                  {groupProgress > 0 && !groupDone && (
                                    <span className="text-xs font-medium text-blue-600">{groupProgress}%</span>
                                  )}
                                </div>
                              </div>
                            )}
                            <ol className="divide-y divide-gray-100/80">
                              {groupCardStates.map(({ card, status, confidence }, qi) => {
                                const isDone = completedStatuses.has(status)
                                const isListening = status === 'listening'
                                const itemProgress = isDone ? 100 : Math.round((confidence ?? 0) * 100)

                                return (
                                  <li key={card.id} className={`flex items-start gap-4 px-5 py-4 transition-all ${isListening ? 'bg-yellow-50/70' : ''}`}>
                                    <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                                      isDone ? 'bg-green-100 text-green-700' : isListening ? 'bg-yellow-200 text-yellow-800 animate-pulse' : 'bg-gray-100 text-gray-600'
                                    }`}>
                                      {isDone ? '✓' : qi + 1}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-start justify-between gap-3">
                                        <p className={`text-base leading-relaxed ${isDone ? 'text-gray-400 line-through' : 'text-gray-900'}`}>
                                          {card.questionText}
                                        </p>
                                        {!isDone && card.importance === 'must' && (
                                          <span className="mt-0.5 shrink-0 rounded bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">必問</span>
                                        )}
                                      </div>
                                      {!isDone && card.suggestedFollowup && (
                                        <p className="mt-1.5 text-sm text-gray-500">追問：{card.suggestedFollowup}</p>
                                      )}
                                      {!isDone && (
                                        <div className="mt-2 h-1.5 w-full rounded-full bg-gray-200">
                                          <div
                                            className="h-1.5 rounded-full bg-blue-400 transition-[width] duration-700 ease-out"
                                            style={{ width: `${itemProgress}%` }}
                                          />
                                        </div>
                                      )}
                                    </div>
                                  </li>
                                )
                              })}
                            </ol>
                          </div>
                        </div>
                      )
                    })
                  })()}
                </div>
              ) : currentSlide ? (
                <div className="mx-auto max-w-3xl">
                  <p className="text-base text-gray-700 whitespace-pre-wrap">{currentSlide.extractedText}</p>
                </div>
              ) : null}
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
    evidenceTranscriptFromEvent?: string,
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
      evidenceTranscriptFromEvent
        ? evidenceTranscriptFromEvent
        : evidence && typeof evidence === 'object' && 'matchedTranscript' in evidence
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

function statusFromEvent(
  data: { new_status?: string; status?: string },
  fallback: CardStatus,
): CardStatus {
  const status = data.new_status ?? data.status
  if (
    status === 'pending' ||
    status === 'listening' ||
    status === 'probably_sufficient' ||
    status === 'sufficient' ||
    status === 'probably_covered' ||
    status === 'covered' ||
    status === 'at_risk' ||
    status === 'skipped' ||
    status === 'manually_checked' ||
    status === 'disabled'
  ) {
    return status
  }
  return fallback
}

function InterviewOutputsPanel({ sessionId }: { sessionId: string }) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [outputs, setOutputs] = useState<{
    brd?: { markdown: string; openIssuesCount: number }
    transcript?: { markdown: string; utteranceCount: number }
  } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate() {
    setIsGenerating(true)
    setError(null)
    try {
      const response = await presentationAPI.generateOutputs(sessionId)
      setOutputs(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate outputs')
    } finally {
      setIsGenerating(false)
    }
  }

  function downloadMarkdown(content: string, filename: string) {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="shrink-0 border-b border-gray-200 bg-white px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">訪談產出</h2>
          <p className="text-xs text-gray-500">產生 BRD 草稿與訪談逐字稿</p>
        </div>
        {!outputs ? (
          <button
            type="button"
            onClick={handleGenerate}
            disabled={isGenerating}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {isGenerating ? '正在產生...' : '產生 BRD 與逐字稿'}
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => downloadMarkdown(outputs.brd!.markdown, 'BRD_草稿.md')}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              下載 BRD
            </button>
            <button
              type="button"
              onClick={() => downloadMarkdown(outputs.transcript!.markdown, '訪談逐字稿.md')}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              下載逐字稿
            </button>
          </div>
        )}
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      {outputs && (
        <div className="mt-3 flex gap-4 text-xs text-gray-500">
          <span>BRD：{outputs.brd?.openIssuesCount ?? 0} 項待補</span>
          <span>逐字稿：{outputs.transcript?.utteranceCount ?? 0} 句</span>
        </div>
      )}
    </div>
  )
}
