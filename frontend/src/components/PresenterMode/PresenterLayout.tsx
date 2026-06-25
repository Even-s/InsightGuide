import { useCallback, useEffect, useRef, useState } from 'react'
import { interviewAPI } from '@/api/interview'
import { apiClient } from '@/api/client'
import { useInterviewSession } from '@/hooks/useInterviewSession'
import { useRealtimeTranscription } from '@/hooks/useRealtimeTranscription'
import { useMediaRecorder } from '@/hooks/useMediaRecorder'
import { useSSEEvents } from '@/hooks/useSSEEvents'
import { useResponsiveLayout } from '@/hooks/useResponsiveLayout'
import type { CardState } from '@/types/interview'
import type { CardStatus } from '@/types/questionCard'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import SessionHeader from './SessionHeader'
import TranscriptDisplay from './TranscriptDisplay'
import { simplifiedToTraditional } from '@/utils/chineseConverter'
import { formatFocusText, formatQuestionText, formatThemeTitle } from '@/utils/interviewCopy'

interface PresenterLayoutProps {
  sessionId: string
  documentId: string
}

export default function PresenterLayout({ sessionId, documentId }: PresenterLayoutProps) {
  const [cardStates, setCardStates] = useState<CardState[]>([])
  const [, setCardsLoading] = useState(true)
  const [transcriptHistory, setTranscriptHistory] = useState<string[]>([]) // 保留最近 3 句
  const [pendingTranscript, setPendingTranscript] = useState('')
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const [followupQueue, setFollowupQueue] = useState<string[]>([]) // queue of card IDs
  const [skippedCards, setSkippedCards] = useState<Set<string>>(new Set())
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
    currentSection,
    sections,
    isLoading,
    themePreparing,
    error,
    startPresenting,
    pausePresenting,
    nextTheme,
    previousTheme,
    endSession,
  } = useInterviewSession(sessionId)

  const { start: startRecording, stop: stopRecording } = useMediaRecorder()
  const [isDiarizing, setIsDiarizing] = useState(false)
  const [candidateCards, setCandidateCards] = useState<Array<{ cardId: string; questionText: string; focusText: string; score: number }>>([])
  const [activeCardId, setActiveCardId] = useState<string | null>(null)
  const [bufferedAnswerCount, setBufferedAnswerCount] = useState(0)
  const recordingStartedAtRef = useRef<string | null>(null)
  const finalRecordingBlobRef = useRef<Blob | null>(null)

  const currentSectionRef = useRef(currentSection)
  const currentThemeRef = useRef(currentTheme)
  const cardStatesRef = useRef<CardState[]>([])
  const isPresentingRef = useRef(false)
  const hasRequestedInitialPreparationRef = useRef(false)
  const partialTranscriptRef = useRef('')
  const partialMatchTimeoutRef = useRef<number | null>(null)
  const partialMatchInFlightRef = useRef(false)
  const pendingPartialMatchRef = useRef<string | null>(null)
  const lastPartialMatchTextRef = useRef('')

  useEffect(() => {
    currentSectionRef.current = currentSection
    currentThemeRef.current = currentTheme
  }, [currentSection, currentTheme])

  useEffect(() => {
    isPresentingRef.current = session?.status === 'interviewing'
  }, [session?.status])

  useEffect(() => {
    cardStatesRef.current = cardStates
  }, [cardStates])

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
      const states = await interviewAPI.getSessionCards(sessionId, documentId)
      setCardStates(states)
    } finally {
      setCardsLoading(false)
    }
  }, [documentId, sessionId])

  useEffect(() => {
    loadCardStates()
  }, [loadCardStates])

  useSSEEvents(sessionId, {
    onCardListening: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'listening'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardCovered: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'sufficient'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardProbablyCovered: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'probably_sufficient'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardAtRisk: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'at_risk'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardSkipped: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'skipped'), data.confidence, data.evidence, data.evidenceTranscript),
    onQuestionCardCandidates: (data) => {
      setCandidateCards(data.candidates)
    },
    onActiveCardChanged: (data) => {
      setActiveCardId(data.card_id)
      setCandidateCards([])
      setBufferedAnswerCount(0)
      updateCardFromEvent(data.card_id, 'listening', 0, undefined, undefined)
    },
    onCardManuallyCompleted: (data) => {
      updateCardFromEvent(data.card_id, statusFromEvent(data, 'sufficient'), 1.0, data.evidence, data.evidenceTranscript)
      if (activeCardId === data.card_id) setActiveCardId(null)
    },
    onActiveCardCleared: () => {
      setActiveCardId(null)
    },
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
    const activeSlide = currentSectionRef.current
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

    // Detect if this utterance is asking a specific card (for question routing)
    const askedCard = findAskedCard(text, cardStatesRef.current, activeId)

    interviewAPI.createUtterance(
      sessionId,
      text,
      activeId,
      payload.itemId,
      payload.startedAt,
      payload.endedAt,
      askedCard ?? undefined,
    )
      .then(() => {
        // Track buffered answers when candidates are showing (waiting for user to pick a card)
        if (candidateCards.length > 0 && !askedCard) {
          setBufferedAnswerCount(prev => prev + 1)
        }
      })
      .catch((err) => {
        console.error('Failed to save utterance:', err)
        setTranscriptionError(err instanceof Error ? err.message : 'Failed to save transcript')
      })
  }, [sessionId])

  const sendPartialTranscriptMatch = useCallback((text: string, itemId?: string) => {
    const activeTheme = currentThemeRef.current
    const activeSlide = currentSectionRef.current
    const activeId = activeTheme?.id ?? activeSlide?.id
    const trimmed = text.trim()
    const activeCardId = getActiveCardId(cardStatesRef.current, activeId)

    if (!activeId || !activeCardId || !isPresentingRef.current || trimmed.length < 12) return
    if (trimmed === lastPartialMatchTextRef.current) return
    if (trimmed.length - lastPartialMatchTextRef.current.length < 8) return

    if (partialMatchInFlightRef.current) {
      pendingPartialMatchRef.current = trimmed
      return
    }

    partialMatchInFlightRef.current = true
    lastPartialMatchTextRef.current = trimmed

    interviewAPI.matchPartialTranscript(sessionId, trimmed, activeId, activeCardId, itemId)
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
    onMediaStreamReady: (stream) => {
      if (import.meta.env.VITE_DISABLE_DIARIZATION === 'true') return
      recordingStartedAtRef.current = recordingStartedAtRef.current ?? new Date().toISOString()
      startRecording(stream)
    },
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
    if (!session || !currentSection) return

    if (session.status === 'idle' || session.status === 'ready') {
      hasRequestedInitialPreparationRef.current = true
      return
    }

    setIsPreparingToPresent(false)
  }, [currentSection, session])


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

  // Followup queue: add new listening/probably_sufficient cards that have followups
  useEffect(() => {
    const activeSectionId = currentTheme?.id ?? currentSection?.id
    if (!activeSectionId) return

    const cardsWithFollowup = cardStates.filter((cs) => {
      const qc = cs.questionCard
      const isInSection = qc.interviewThemeId === activeSectionId || qc.sectionId === activeSectionId
      const hasFollowup = cs.evidence && getEvidenceSuggestedFollowup(cs.evidence as Record<string, unknown>)
      const needsFollowup = cs.status === 'listening' || cs.status === 'probably_sufficient'
      return isInSection && needsFollowup && hasFollowup && !skippedCards.has(cs.questionCard.id)
    })

    setFollowupQueue((prev) => {
      const existingSet = new Set(prev)
      const newIds = cardsWithFollowup
        .map((cs) => cs.questionCard.id)
        .filter((id) => !existingSet.has(id))
      if (newIds.length === 0) return prev
      return [...prev, ...newIds]
    })
  }, [cardStates, currentTheme?.id, currentSection?.id, skippedCards])

  // Current followup: first in queue that still needs followup
  const currentFollowupCard = followupQueue
    .filter((id) => !skippedCards.has(id))
    .map((id) => cardStates.find((cs) => cs.questionCard.id === id))
    .find((cs) => cs && (cs.status === 'listening' || cs.status === 'probably_sufficient'))

  const followupPrompt = currentFollowupCard
    ? buildFollowupPrompt([currentFollowupCard], currentTheme?.id ?? currentSection?.id)
    : null

  const followupQueueLength = followupQueue.filter((id) => !skippedCards.has(id)).length

  const handleSkipFollowup = useCallback(() => {
    if (currentFollowupCard) {
      setSkippedCards((prev) => new Set([...prev, currentFollowupCard.questionCard.id]))
    }
  }, [currentFollowupCard])

  if (isLoading) {
    return <LoadingSpinner label="載入演講 Session..." />
  }

  if (themePreparing) {
    return <LoadingSpinner label="準備訪談問題中..." />
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-cream-100 p-6">
        <div className="max-w-md rounded border border-red-200 bg-white p-6 text-center">
          <p className="mb-2 text-lg font-semibold text-red-700">載入失敗</p>
          <p className="text-sm text-natural-500">{error.message}</p>
        </div>
      </div>
    )
  }

  const isStartControlPreparing = isPreparingToPresent || scriptReadiness.isPreparing

  return (
    <div className="flex h-screen flex-col bg-cream-100 text-natural-800">
      <SessionHeader
        session={session}
        documentId={documentId}
        isRecording={isRecording}
        isPreparingToPresent={isStartControlPreparing}
        currentThemeTitle={currentTheme ? `${currentTheme.themeNumber}. ${formatThemeTitle(currentTheme.title)}` : `段落 ${currentSection?.pageNumber ?? ''}`}
        currentThemeIndex={currentThemeIndex}
        totalThemes={themes.length || sections.length}
        onStart={handleStartRequested}
        onPause={pausePresenting}
        onEnd={async () => {
          if (import.meta.env.VITE_DISABLE_DIARIZATION === 'true') {
            endSession()
            return
          }

          setIsDiarizing(true)
          try {
            const blob = finalRecordingBlobRef.current ?? await stopRecording()
            finalRecordingBlobRef.current = blob

            if (!blob || blob.size <= 1000) {
              throw new Error('沒有取得有效的訪談錄音檔，請先確認麥克風已開始錄音再停止訪談。')
            }

            if (!recordingStartedAtRef.current) {
              throw new Error('缺少錄音開始時間，無法產生正式逐字稿。')
            }

            const formData = new FormData()
            formData.append('audio', blob, 'session_audio.webm')
            formData.append('recording_started_at', recordingStartedAtRef.current)
            await apiClient.post(`/api/realtime/diarize/${sessionId}`, formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 300000,
            })

            finalRecordingBlobRef.current = null
            setTranscriptionError(null)
          } catch (err) {
            console.warn('Diarization failed:', err)
            setTranscriptionError(err instanceof Error ? err.message : '正式逐字稿產生失敗，訪談尚未結束。')
            setIsDiarizing(false)
            return
          } finally {
            setIsDiarizing(false)
          }
          endSession()
        }}
      />

      {isDiarizing ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-cream-300 border-t-sage-400" />
            <p className="text-base font-medium text-natural-600">正在辨識語者...</p>
          </div>
        </div>
      ) : session?.status === 'ended' ? (
        (() => { window.location.assign(`/sessions/${sessionId}/insight-memo`); return null })()
      ) : (
        <>
          <main className="relative flex min-h-0 flex-1 overflow-hidden">
            {/* Left arrow: previous theme */}
            <button
              type="button"
              onClick={previousTheme}
              disabled={currentThemeIndex === 0}
              className="absolute left-[2%] top-1/2 -translate-y-1/2 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-cream-300 bg-white shadow-natural text-natural-400 hover:text-natural-600 hover:border-cream-400 transition-all disabled:opacity-0 disabled:pointer-events-none"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            {/* Right arrow: next theme */}
            <button
              type="button"
              onClick={nextTheme}
              disabled={currentThemeIndex >= (themes.length || sections.length) - 1}
              className="absolute right-[2%] top-1/2 -translate-y-1/2 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-cream-300 bg-white shadow-natural text-natural-400 hover:text-natural-600 hover:border-cream-400 transition-all disabled:opacity-0 disabled:pointer-events-none"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>

            {/* Questions with inline strikethrough status */}
            <div className="min-h-0 flex-1 overflow-y-auto bg-cream-100 px-14 py-5">

              {/* Candidate suggestion bar */}
              {candidateCards.length > 0 && (
                <div className="mx-auto max-w-3xl mb-4 rounded-xl border border-wood-200 bg-wood-50 p-3 shadow-natural animate-themeFadeIn">
                  <p className="text-xs font-medium text-wood-500 mb-2">系統建議正在問的問題：</p>
                  <div className="space-y-1.5">
                    {candidateCards.map((c) => (
                      <button
                        key={c.cardId}
                        onClick={() => {
                          interviewAPI.confirmActiveCard(sessionId, c.cardId)
                          setActiveCardId(c.cardId)
                          setCandidateCards([])
                          setBufferedAnswerCount(0)
                        }}
                        className="w-full text-left px-3 py-2 rounded-xl border border-wood-100 bg-white hover:bg-wood-50 hover:border-wood-300 transition-colors text-sm"
                      >
                        <span className="text-natural-700">{c.focusText || c.questionText}</span>
                        <span className="ml-2 text-xs text-wood-400">{Math.round(c.score * 100)}%</span>
                      </button>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <button
                      onClick={() => { setCandidateCards([]); setBufferedAnswerCount(0) }}
                      className="text-xs text-natural-400 hover:text-natural-600"
                    >
                      忽略
                    </button>
                    {bufferedAnswerCount > 0 && (
                      <span className="text-xs text-wood-400">
                        💬 {bufferedAnswerCount} 句回答已暫存，選擇問題卡後將自動記錄
                      </span>
                    )}
                  </div>
                </div>
              )}


              {currentTheme ? (
                <div key={currentTheme.id} className="mx-auto max-w-3xl space-y-4 animate-themeFadeIn">
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
                        <div key={gi} className={`relative rounded-2xl border shadow-sm overflow-hidden ${groupDone ? 'border-sage-200' : 'border-cream-300'}`}>
                          {/* Water fill background for the whole group */}
                          <div
                            className="pointer-events-none absolute inset-x-0 bottom-0 z-0 transition-[height] duration-1000 ease-out"
                            style={{ height: `${groupProgress}%` }}
                            aria-hidden="true"
                          >
                            <div className={`absolute inset-0 ${groupDone ? 'bg-sage-100/60' : 'bg-sage-50/50'}`} />
                          </div>

                          {/* Content on top */}
                          <div className="relative z-10">
                            {group.focus && (
                              <div className={`border-b px-5 py-2.5 ${groupDone ? 'border-sage-200' : 'border-sage-100'}`}>
                                <div className="flex items-center justify-between">
                                  <AnimatedStrikeText
                                    text={`${groupDone ? '✓ ' : ''}${formatFocusText(group.focus)}`}
                                    done={groupDone}
                                    className={`text-sm font-semibold transition-colors duration-500 ease-out ${groupDone ? 'text-sage-500' : 'text-sage-400'}`}
                                  />
                                </div>
                              </div>
                            )}
                            <div className="space-y-3 p-3">
                              {groupCardStates.map(({ card, status, confidence }, qi) => {
                                const isDone = completedStatuses.has(status)
                                const isActive = status === 'listening' || status === 'probably_sufficient'
                                const itemProgress = isDone ? 100 : status === 'listening' ? 0 : Math.round((confidence ?? 0) * 100)

                                return (
                                  <div key={card.id} className={`rounded-2xl border bg-white p-4 shadow-sm transition-[border-color,background-color,box-shadow,opacity,transform] duration-500 ease-out ${isActive ? 'scale-[1.01] border-yellow-300 bg-yellow-50 shadow-yellow-100' : isDone ? 'border-sage-200 bg-sage-50/60' : 'border-cream-300'}`}>
                                    <div className="mb-3 flex items-center justify-between gap-3">
                                      <div className="flex items-center gap-2">
                                        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-sm font-semibold transition-[background-color,color,transform,opacity] duration-500 ease-out ${
                                          isDone ? 'bg-sage-100 text-sage-500' : isActive ? 'bg-yellow-200 text-yellow-800 animate-pulse' : 'bg-cream-200 text-natural-500'
                                        }`}>
                                          {isDone ? '✓' : qi + 1}
                                        </span>
                                        <span className="rounded-lg bg-cream-200 px-2 py-0.5 text-xs font-semibold tracking-wide text-natural-500">
                                          建議提問
                                        </span>
                                      </div>
                                      {!isDone && card.importance === 'must' && (
                                        <span className="shrink-0 rounded-lg bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">必問</span>
                                      )}
                                    </div>
                                    <AnimatedStrikeText
                                      text={formatQuestionText(card.questionText)}
                                      done={isDone}
                                      className={`text-base font-normal leading-relaxed transition-colors duration-500 ease-out ${isDone ? 'text-natural-300' : 'text-natural-700'}`}
                                    />
                                      <div className={`mt-2 overflow-hidden transition-[max-height,opacity] duration-500 ease-out ${isDone ? 'max-h-0 opacity-0' : 'max-h-4 opacity-100'}`}>
                                        <div className="h-1 w-full overflow-hidden rounded-full bg-cream-300">
                                          <div
                                            className={`h-1 rounded-full transition-[width,background-color,opacity] duration-700 ease-out ${isActive ? 'bg-yellow-400' : 'bg-sage-400'}`}
                                            style={{ width: `${itemProgress}%` }}
                                          />
                                        </div>
                                      </div>
                                      {/* Reason why not 100% + followup suggestion */}
                                      {!isDone && (() => {
                                        const cs = cardStates.find(c => c.questionCard.id === card.id)
                                        const ev = cs?.evidence as Record<string, unknown> | undefined
                                        const judgment = ev?.judgment as Record<string, unknown> | undefined
                                        const reason = judgment?.reason as string | undefined
                                        const followup = judgment?.suggested_followup as string | undefined
                                        if (!reason && !followup) return null
                                        return (
                                          <div className="mt-2 space-y-1">
                                            {reason && (
                                              <p className="text-xs text-natural-400 leading-relaxed">{reason}</p>
                                            )}
                                            {followup && (
                                              <p className="text-xs text-sage-600 leading-relaxed">追問：{followup}</p>
                                            )}
                                          </div>
                                        )
                                      })()}
                                      {/* Manual card actions */}
                                      {!isDone && (
                                        <div className="mt-3 flex gap-2">
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              interviewAPI.manualCompleteCard(sessionId, card.id)
                                              updateCardFromEvent(card.id, 'sufficient', 1.0, undefined, undefined)
                                            }}
                                            className="px-2.5 py-1 text-xs bg-sage-50 text-sage-500 border border-sage-200 rounded-xl hover:bg-sage-100 transition-colors"
                                          >
                                            標記完成
                                          </button>
                                          {activeCardId === card.id ? (
                                            <button
                                              onClick={(e) => {
                                                e.stopPropagation()
                                                interviewAPI.clearActiveCard(sessionId)
                                                setActiveCardId(null)
                                              }}
                                              className="px-2.5 py-1 text-xs bg-wood-100 text-wood-500 border border-wood-200 rounded-xl hover:bg-wood-200 transition-colors"
                                            >
                                              取消目前問題
                                            </button>
                                          ) : (
                                            <button
                                              onClick={(e) => {
                                                e.stopPropagation()
                                                interviewAPI.confirmActiveCard(sessionId, card.id)
                                                setActiveCardId(card.id)
                                              }}
                                              className="px-2.5 py-1 text-xs bg-wood-50 text-wood-500 border border-wood-200 rounded-xl hover:bg-wood-100 transition-colors"
                                            >
                                              設為目前問題
                                            </button>
                                          )}
                                        </div>
                                      )}
                                      {isDone && (
                                        <div className="mt-2">
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              interviewAPI.undoCompleteCard(sessionId, card.id)
                                              updateCardFromEvent(card.id, 'listening', 0, undefined, undefined)
                                            }}
                                            className="px-2.5 py-1 text-xs bg-cream-100 text-natural-400 border border-cream-300 rounded-xl hover:bg-cream-200 transition-colors"
                                          >
                                            復原
                                          </button>
                                        </div>
                                      )}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        </div>
                      )
                    })
                  })()}
                  {/* 底部留白，避免被懸浮追問提示擋住 */}
                  <div className="h-28" />
                </div>
              ) : currentSection ? (
                <div className="mx-auto max-w-3xl">
                  <p className="text-base text-natural-600 whitespace-pre-wrap">{currentSection.extractedText}</p>
                </div>
              ) : null}
            </div>

            {/* 懸浮追問提示（排隊制） */}
            <FollowupPromptPanel prompt={followupPrompt} queueLength={followupQueueLength} onSkip={handleSkipFollowup} />
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
    if (!cardId) return

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
      <div className="flex flex-col items-center justify-center rounded-2xl border border-cream-300 bg-white px-8 py-7 shadow-natural">
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

function getActiveCardId(cardStates: CardState[], activeSectionId?: string) {
  if (!activeSectionId) return null

  const activeCard = cardStates.find((cardState) => {
    const questionCard = cardState.questionCard
    const isInActiveSection =
      questionCard.interviewThemeId === activeSectionId ||
      questionCard.sectionId === activeSectionId
    return isInActiveSection && cardState.status === 'listening'
  })

  return activeCard?.questionCard.id ?? null
}

function findAskedCard(text: string, cardStates: CardState[], activeSectionId?: string): string | null {
  if (!activeSectionId || !text) return null

  const QUESTION_ENDINGS = ['?', '？', '呢', '嗎']
  const isQuestion = QUESTION_ENDINGS.some(e => text.trim().endsWith(e))
  if (!isQuestion) return null

  const sectionCards = cardStates.filter(cs => {
    const qc = cs.questionCard
    return (qc.interviewThemeId === activeSectionId || qc.sectionId === activeSectionId)
      && cs.status !== 'sufficient'
  })

  let bestScore = 0
  let bestId: string | null = null
  const textLower = text.toLowerCase()

  for (const cs of sectionCards) {
    const qc = cs.questionCard
    let score = 0

    // Check overlap with questionText
    if (qc.questionText) {
      const words = qc.questionText.toLowerCase().split('').filter(c => c.trim())
      const overlap = words.filter(w => textLower.includes(w)).length / Math.max(words.length, 1)
      score += overlap * 2
    }

    // Check overlap with focusText
    if (qc.focusText) {
      const focusChars = qc.focusText.toLowerCase()
      for (let i = 0; i < focusChars.length - 1; i++) {
        if (textLower.includes(focusChars.slice(i, i + 2))) score += 0.3
      }
    }

    if (score > bestScore) {
      bestScore = score
      bestId = qc.id
    }
  }

  return bestScore > 1.0 ? bestId : null
}

interface FollowupPrompt {
  cardTitle: string
  missingItems: string[]
  reason?: string
  suggestedFollowup?: string
}

function buildFollowupPrompt(
  cardStates: CardState[],
  activeSectionId?: string,
): FollowupPrompt | null {
  if (!activeSectionId) return null

  const activeCardState = cardStates.find((cardState) => {
    const questionCard = cardState.questionCard
    const isInActiveSection =
      questionCard.interviewThemeId === activeSectionId ||
      questionCard.sectionId === activeSectionId
    return isInActiveSection && (cardState.status === 'listening' || cardState.status === 'probably_sufficient')
  })
  if (!activeCardState) return null

  const evidence = activeCardState.evidence
  if (!evidence || evidence.activeOnly === true) return null

  const reason = getEvidenceReason(evidence)
  const missingItems = getMissingItems(activeCardState)
  const suggestedFollowup = getEvidenceSuggestedFollowup(evidence)

  if (missingItems.length === 0 && !reason && !suggestedFollowup) {
    return null
  }

  return {
    cardTitle: formatFocusText(activeCardState.questionCard.focusText) || formatQuestionText(activeCardState.questionCard.questionText),
    missingItems,
    reason,
    suggestedFollowup,
  }
}

function getEvidenceReason(evidence: Record<string, unknown>) {
  const directReason = evidence.reason
  if (typeof directReason === 'string' && directReason.trim()) return directReason.trim()

  const judgment = evidence.judgment
  if (judgment && typeof judgment === 'object' && 'reason' in judgment) {
    const reason = (judgment as { reason?: unknown }).reason
    if (typeof reason === 'string' && reason.trim()) return reason.trim()
  }

  if (typeof evidence.gptReasoning === 'string' && evidence.gptReasoning.trim()) {
    return evidence.gptReasoning.trim()
  }

  return undefined
}

function getEvidenceSuggestedFollowup(evidence: Record<string, unknown>) {
  const directFollowup = evidence.suggested_followup ?? evidence.suggestedFollowup
  if (typeof directFollowup === 'string' && directFollowup.trim()) return directFollowup.trim()

  const judgment = evidence.judgment
  if (judgment && typeof judgment === 'object') {
    const followup =
      (judgment as { suggested_followup?: unknown }).suggested_followup ??
      (judgment as { suggestedFollowup?: unknown }).suggestedFollowup
    if (typeof followup === 'string' && followup.trim()) return followup.trim()
  }

  return undefined
}

function getMissingItems(cardState: CardState) {
  const evidence = cardState.evidence
  if (!evidence) return []

  const rawMissingIds: unknown[] = Array.isArray(evidence.missingElementIds)
    ? evidence.missingElementIds
    : Array.isArray((evidence.judgment as { missing_element_ids?: unknown } | undefined)?.missing_element_ids)
      ? ((evidence.judgment as { missing_element_ids?: unknown[] }).missing_element_ids ?? [])
      : []

  const missingIds = rawMissingIds
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => item.trim())

  if (missingIds.length === 0) return []

  const coverageRule = cardState.questionCard.coverageRule
  return missingIds
    .map((id) => formatFocusText(resolveCoverageItemText(id, coverageRule)))
    .filter((text): text is string => Boolean(text))
}

function resolveCoverageItemText(
  id: string,
  coverageRule: CardState['questionCard']['coverageRule'],
) {
  const elementMatch = id.match(/^element_(\d+)$/)
  if (elementMatch) {
    const index = Number(elementMatch[1])
    const element = coverageRule.mustMentionElements[index]
    return element?.text || element?.subpoints?.join('、') || id
  }

  const anchorMatch = id.match(/^anchor_(\d+)$/)
  if (anchorMatch) {
    const index = Number(anchorMatch[1])
    return coverageRule.semanticAnchors[index] || id
  }

  return id
}

function AnimatedStrikeText({
  text,
  done,
  className,
}: {
  text: string
  done: boolean
  className: string
}) {
  return (
    <span className={`relative inline-block max-w-full ${className}`}>
      <span className="transition-opacity duration-500 ease-out">{text}</span>
      <span
        className={`pointer-events-none absolute left-0 right-0 top-1/2 h-px origin-left -translate-y-1/2 bg-current transition-transform duration-500 ease-out ${done ? 'scale-x-100' : 'scale-x-0'}`}
        aria-hidden="true"
      />
    </span>
  )
}

function FollowupPromptPanel({ prompt, queueLength, onSkip }: { prompt: FollowupPrompt | null; queueLength: number; onSkip: () => void }) {
  const promptKey = [
    prompt?.cardTitle,
    prompt?.suggestedFollowup,
  ].filter(Boolean).join('::') || 'empty'

  if (!prompt?.suggestedFollowup) return null

  return (
    <section className="absolute bottom-4 left-6 right-6 z-20" aria-live="polite">
      <div className="mx-auto max-w-5xl">
        <div className="min-w-0 rounded-2xl bg-white px-7 py-5 shadow-[0_0_20px_rgba(160,137,104,0.2),0_0_40px_rgba(160,137,104,0.1)]">
          <div className="mb-3 flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="shrink-0 rounded-xl border border-wood-200 bg-wood-50 px-2.5 py-1 text-sm font-bold text-wood-500">仍需追問</span>
              {prompt.cardTitle && (
                <p key={prompt.cardTitle} className="animate-fadeIn truncate text-base font-medium text-natural-500">{prompt.cardTitle}</p>
              )}
              {queueLength > 1 && (
                <span className="shrink-0 text-xs text-natural-400">+{queueLength - 1} 題待問</span>
              )}
            </div>
            <button
              type="button"
              onClick={onSkip}
              className="shrink-0 rounded-lg border border-cream-300 bg-cream-50 px-3 py-1 text-xs font-medium text-natural-500 hover:bg-cream-100 hover:text-natural-700 transition-colors"
            >
              跳過
            </button>
          </div>
          <div key={promptKey} className="animate-fadeIn">
            <p className="text-base leading-relaxed text-natural-700">{prompt.suggestedFollowup}</p>
          </div>
        </div>
      </div>
    </section>
  )
}
