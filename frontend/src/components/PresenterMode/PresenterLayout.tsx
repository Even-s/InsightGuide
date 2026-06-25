import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient } from '@/api/client'
import { interviewAPI } from '@/api/interview'
import { useInterviewSession } from '@/hooks/useInterviewSession'
import { useResponsiveLayout } from '@/hooks/useResponsiveLayout'
import { usePresenterSessionRefs } from '@/hooks/usePresenterSessionRefs'
import { useCardEventHandlers } from '@/hooks/useCardEventHandlers'
import { useTranscriptProcessing } from '@/hooks/useTranscriptProcessing'
import type { CardState } from '@/types/interview'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import SessionHeader from './SessionHeader'
import TranscriptDisplay from './TranscriptDisplay'
import AnimatedStrikeText from './AnimatedStrikeText'
import FollowupPromptPanel from './FollowupPromptPanel'
import { formatFocusText, formatQuestionText, formatThemeTitle } from '@/utils/interviewCopy'

interface PresenterLayoutProps {
  sessionId: string
  documentId: string
}

export default function PresenterLayout({ sessionId, documentId }: PresenterLayoutProps) {
  const [slideOrientation] = useState<'landscape' | 'portrait' | 'unknown'>('unknown')
  const { layoutConfig } = useResponsiveLayout(slideOrientation)
  const hasRequestedInitialPreparationRef = useRef(false)

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

  const refs = usePresenterSessionRefs(
    [] as CardState[], // initial, will sync via cardStates effect below
    currentTheme,
    currentSection,
    session?.status,
  )

  const {
    cardStates,
    candidateCards,
    activeCardId,
    bufferedAnswerCount,
    followupPrompt,
    followupQueueLength,
    setActiveCardId,
    setCandidateCards,
    setBufferedAnswerCount,
    handleSkipFollowup,
    updateCardFromEvent,
  } = useCardEventHandlers({
    sessionId,
    documentId,
    currentThemeId: currentTheme?.id,
    currentSectionId: currentSection?.id,
  })

  // Keep cardStatesRef in sync
  useEffect(() => {
    refs.cardStatesRef.current = cardStates
  }, [cardStates, refs.cardStatesRef])

  const {
    transcriptHistory,
    pendingTranscript,
    transcriptionError,
    isPreparingToPresent,
    isDiarizing,
    realtimeStatus,
    isRecording,
    isTranscribing,
    realtimeError,
    recordingStartedAtRef,
    finalRecordingBlobRef,
    setIsDiarizing,
    setTranscriptionError,
    setIsPreparingToPresent,
    startTranscription,
    stopTranscription,
    stopRecording,
  } = useTranscriptProcessing({
    sessionId,
    refs,
    candidateCards,
    onBufferedAnswer: () => setBufferedAnswerCount(prev => prev + 1),
  })

  const scriptReadiness = { isReady: true, isPreparing: false, error: null as string | null }
  const hasConfirmedScriptPreview = true

  const handleStartRequested = useCallback(async () => {
    if (session?.status === 'interviewing') return
    setTranscriptionError(null)
    setIsPreparingToPresent(true)

    try {
      await startPresenting()
      if (realtimeStatus === 'idle' || realtimeStatus === 'error') {
        startTranscription()
      }
    } catch (err) {
      console.error('Failed to start interview:', err)
      setTranscriptionError(err instanceof Error ? err.message : 'Failed to start')
    } finally {
      setIsPreparingToPresent(false)
    }
  }, [realtimeStatus, session?.status, startPresenting, startTranscription, setTranscriptionError, setIsPreparingToPresent])

  useEffect(() => {
    if (hasRequestedInitialPreparationRef.current) return
    if (!session || !currentSection) return

    if (session.status === 'idle' || session.status === 'ready') {
      hasRequestedInitialPreparationRef.current = true
      return
    }

    setIsPreparingToPresent(false)
  }, [currentSection, session, setIsPreparingToPresent])

  useEffect(() => {
    if (session?.status === 'interviewing' && realtimeStatus === 'idle') {
      startTranscription()
    }

    if (session?.status !== 'interviewing' && !isPreparingToPresent && realtimeStatus !== 'idle') {
      stopTranscription()
    }

    if (session?.status === 'ended' && realtimeStatus !== 'idle') {
      setTranscriptionError('Session has ended. Please start a new session to continue.')
    }
  }, [isPreparingToPresent, realtimeStatus, session?.status, startTranscription, stopTranscription, setTranscriptionError])

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
    setIsPreparingToPresent,
    setTranscriptionError,
  ])

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

            <div className="min-h-0 flex-1 overflow-y-auto bg-cream-100 px-14 py-5">
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
                        {bufferedAnswerCount} 句回答已暫存，選擇問題卡後將自動記錄
                      </span>
                    )}
                  </div>
                </div>
              )}

              {currentTheme ? (
                <ThemeCardsList
                  currentTheme={currentTheme}
                  cardStates={cardStates}
                  activeCardId={activeCardId}
                  sessionId={sessionId}
                  setActiveCardId={setActiveCardId}
                  updateCardFromEvent={updateCardFromEvent}
                />
              ) : currentSection ? (
                <div className="mx-auto max-w-3xl">
                  <p className="text-base text-natural-600 whitespace-pre-wrap">{currentSection.extractedText}</p>
                </div>
              ) : null}
            </div>

            <FollowupPromptPanel prompt={followupPrompt} queueLength={followupQueueLength} onSkip={handleSkipFollowup} />
          </main>

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
}

interface ThemeCardsListProps {
  currentTheme: { id: string; cards: Array<{ id: string; focusText?: string; questionText: string; importance?: string }> }
  cardStates: CardState[]
  activeCardId: string | null
  sessionId: string
  setActiveCardId: (id: string | null) => void
  updateCardFromEvent: (cardId: string | undefined, status: CardState['status'], confidence?: number, evidence?: unknown, evidenceTranscript?: string) => void
}

function ThemeCardsList({ currentTheme, cardStates, activeCardId, sessionId, setActiveCardId, updateCardFromEvent }: ThemeCardsListProps) {
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

  return (
    <div key={currentTheme.id} className="mx-auto max-w-3xl space-y-4 animate-themeFadeIn">
      {groups.map((group, gi) => {
        const groupCardStates = group.cards.map(c => {
          const cs = cardStates.find(s => s.questionCard.id === c.id)
          return { card: c, status: cardStateMap.get(c.id) ?? 'pending', confidence: cs?.confidence ?? 0 }
        })
        const groupDone = groupCardStates.every(c => completedStatuses.has(c.status))
        const groupConfidenceSum = groupCardStates.reduce((sum, c) => sum + (completedStatuses.has(c.status) ? 1 : (c.confidence ?? 0)), 0)
        const groupProgress = groupCardStates.length > 0 ? Math.round((groupConfidenceSum / groupCardStates.length) * 100) : 0

        return (
          <div key={gi} className={`relative rounded-2xl border shadow-sm overflow-hidden ${groupDone ? 'border-sage-200' : 'border-cream-300'}`}>
            <div
              className="pointer-events-none absolute inset-x-0 bottom-0 z-0 transition-[height] duration-1000 ease-out"
              style={{ height: `${groupProgress}%` }}
              aria-hidden="true"
            >
              <div className={`absolute inset-0 ${groupDone ? 'bg-sage-100/60' : 'bg-sage-50/50'}`} />
            </div>

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
      })}
      <div className="h-28" />
    </div>
  )
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
