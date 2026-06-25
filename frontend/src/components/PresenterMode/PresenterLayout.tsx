import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient } from '@/api/client'
import { useInterviewSession } from '@/hooks/useInterviewSession'
import { useResponsiveLayout } from '@/hooks/useResponsiveLayout'
import { usePresenterSessionRefs } from '@/hooks/usePresenterSessionRefs'
import { useCardEventHandlers } from '@/hooks/useCardEventHandlers'
import { useTranscriptProcessing } from '@/hooks/useTranscriptProcessing'
import type { CardState } from '@/types/interview'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import SessionHeader from './SessionHeader'
import TranscriptDisplay from './TranscriptDisplay'
import FollowupPromptPanel from './FollowupPromptPanel'
import ThemeCardsList from './ThemeCardsList'
import CandidateSuggestionBar from './CandidateSuggestionBar'
import { formatThemeTitle } from '@/utils/interviewCopy'

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
              <CandidateSuggestionBar
                sessionId={sessionId}
                candidateCards={candidateCards}
                bufferedAnswerCount={bufferedAnswerCount}
                setActiveCardId={setActiveCardId}
                setCandidateCards={setCandidateCards}
                setBufferedAnswerCount={setBufferedAnswerCount}
              />

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
