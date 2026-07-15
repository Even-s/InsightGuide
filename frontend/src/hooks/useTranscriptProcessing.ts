import { useCallback, useEffect, useRef, useState } from 'react'
import { interviewAPI } from '@/api/interview'
import { useRealtimeTranscription } from '@/hooks/useRealtimeTranscription'
import { useMediaRecorder } from '@/hooks/useMediaRecorder'
import type { PresenterSessionRefs } from './usePresenterSessionRefs'
import { simplifiedToTraditional } from '@/utils/chineseConverter'
import { findAskedCard, getActiveCardId } from '@/components/PresenterMode/presenterUtils'
import type {
  AudioDiagnosticsSnapshot,
  AudioProcessingProfile,
} from '@/hooks/useAudioDiagnostics'

interface UseTranscriptProcessingOptions {
  sessionId: string
  refs: PresenterSessionRefs
  candidateCards: Array<{ cardId: string; questionText: string; focusText: string; score: number }>
  onBufferedAnswer: () => void
  diagnosticsEnabled?: boolean
  audioProcessingProfile?: AudioProcessingProfile
}

export interface TranscriptProcessingResult {
  transcriptHistory: string[]
  pendingTranscript: string
  transcriptionError: string | null
  isPreparingToPresent: boolean
  isDiarizing: boolean
  realtimeStatus: string
  isRecording: boolean
  isTranscribing: boolean
  realtimeError: Error | null
  audioDiagnostics: AudioDiagnosticsSnapshot
  recordingStartedAtRef: React.MutableRefObject<string | null>
  finalRecordingBlobRef: React.MutableRefObject<Blob | null>
  setIsDiarizing: (v: boolean) => void
  setTranscriptionError: (v: string | null) => void
  setIsPreparingToPresent: (v: boolean) => void
  handleStartRequested: () => Promise<void>
  startTranscription: () => void
  stopTranscription: () => void
  stopRecording: () => Promise<Blob | null>
  resetAudioDiagnostics: () => void
}

export function selectCompletedTranscript(
  completedTranscript: string,
  streamedTranscript: string,
) {
  const completed = completedTranscript.trim()
  const streamed = streamedTranscript.trim()

  if (!streamed) return completed
  if (!completed) return streamed

  const additionalLength = streamed.length - completed.length
  const substantiallyRicher =
    additionalLength >= Math.max(8, Math.ceil(completed.length * 0.5))
  const streamedLooksLikeQuestion = /[？?嗎呢]\s*$/.test(streamed)
  const completedLooksLikeQuestion = /[？?嗎呢]\s*$/.test(completed)

  if (
    substantiallyRicher ||
    (streamedLooksLikeQuestion && !completedLooksLikeQuestion && additionalLength > 0)
  ) {
    return streamed
  }

  return completed
}

export function useTranscriptProcessing({
  sessionId,
  refs,
  candidateCards,
  onBufferedAnswer,
  diagnosticsEnabled = false,
  audioProcessingProfile = 'standard',
}: UseTranscriptProcessingOptions): TranscriptProcessingResult {
  const [transcriptHistory, setTranscriptHistory] = useState<string[]>([])
  const [pendingTranscript, setPendingTranscript] = useState('')
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const [isDiarizing, setIsDiarizing] = useState(false)
  const [isPreparingToPresent, setIsPreparingToPresent] = useState(false)

  const { start: startRecording, stop: stopRecording } = useMediaRecorder()
  const recordingStartedAtRef = useRef<string | null>(null)
  const finalRecordingBlobRef = useRef<Blob | null>(null)

  const partialTranscriptRef = useRef('')
  const partialMatchTimeoutRef = useRef<number | null>(null)
  const partialMatchInFlightRef = useRef(false)
  const pendingPartialMatchRef = useRef<string | null>(null)
  const lastPartialMatchTextRef = useRef('')

  useEffect(() => {
    return () => {
      if (partialMatchTimeoutRef.current) {
        clearTimeout(partialMatchTimeoutRef.current)
      }
    }
  }, [])

  const sendPartialTranscriptMatch = useCallback((text: string, itemId?: string) => {
    const activeTheme = refs.currentThemeRef.current
    const activeSlide = refs.currentSectionRef.current
    const activeId = activeTheme?.id ?? activeSlide?.id
    const trimmed = text.trim()
    const currentActiveCardId = getActiveCardId(refs.cardStatesRef.current, activeId)

    if (!activeId || !currentActiveCardId || !refs.isPresentingRef.current || trimmed.length < 12) return
    if (trimmed === lastPartialMatchTextRef.current) return
    if (trimmed.length - lastPartialMatchTextRef.current.length < 8) return

    if (partialMatchInFlightRef.current) {
      pendingPartialMatchRef.current = trimmed
      return
    }

    partialMatchInFlightRef.current = true
    lastPartialMatchTextRef.current = trimmed

    interviewAPI.matchPartialTranscript(sessionId, trimmed, activeId, currentActiveCardId, itemId)
      .catch((err) => {
        console.warn('[useTranscriptProcessing] Partial transcript matching failed:', err)
      })
      .finally(() => {
        partialMatchInFlightRef.current = false
        const pending = pendingPartialMatchRef.current
        pendingPartialMatchRef.current = null
        if (pending && pending !== lastPartialMatchTextRef.current) {
          sendPartialTranscriptMatch(pending, itemId)
        }
      })
  }, [sessionId, refs])

  const schedulePartialTranscriptMatch = useCallback((text: string, itemId?: string) => {
    if (partialMatchTimeoutRef.current) {
      clearTimeout(partialMatchTimeoutRef.current)
    }

    partialMatchTimeoutRef.current = window.setTimeout(() => {
      sendPartialTranscriptMatch(text, itemId)
    }, 800)
  }, [sendPartialTranscriptMatch])

  const handleTranscriptCompleted = useCallback((payload: {
    transcript: string
    itemId?: string
    startedAt?: string
    endedAt?: string
  }) => {
    let text = selectCompletedTranscript(payload.transcript, partialTranscriptRef.current)
    const activeTheme = refs.currentThemeRef.current
    const activeSlide = refs.currentSectionRef.current
    const activeId = activeTheme?.id ?? activeSlide?.id

    partialTranscriptRef.current = ''
    lastPartialMatchTextRef.current = ''
    pendingPartialMatchRef.current = null
    if (partialMatchTimeoutRef.current) {
      clearTimeout(partialMatchTimeoutRef.current)
      partialMatchTimeoutRef.current = null
    }

    if (!text || !activeId || !refs.isPresentingRef.current) {
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

    const askedCard = findAskedCard(text, refs.cardStatesRef.current, activeId)

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
        if (candidateCards.length > 0 && !askedCard) {
          onBufferedAnswer()
        }
      })
      .catch((err) => {
        console.error('Failed to save utterance:', err)
        setTranscriptionError(err instanceof Error ? err.message : 'Failed to save transcript')
      })
  }, [sessionId, refs, candidateCards.length, onBufferedAnswer])

  const {
    status: realtimeStatus,
    isRecording,
    isTranscribing,
    startTranscription,
    stopTranscription,
    error: realtimeError,
    diagnostics: audioDiagnostics,
    resetDiagnostics: resetAudioDiagnostics,
  } = useRealtimeTranscription({
    diagnosticsEnabled,
    audioProcessingProfile,
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
    setTranscriptionError(null)
    setIsPreparingToPresent(true)

    try {
      if (realtimeStatus === 'idle' || realtimeStatus === 'error') {
        startTranscription()
      }
    } catch (err) {
      console.error('Failed to start transcription:', err)
      setTranscriptionError(err instanceof Error ? err.message : 'Failed to start')
      setIsPreparingToPresent(false)
    }
  }, [realtimeStatus, startTranscription])

  return {
    transcriptHistory,
    pendingTranscript,
    transcriptionError,
    isPreparingToPresent,
    isDiarizing,
    realtimeStatus,
    isRecording,
    isTranscribing,
    realtimeError,
    audioDiagnostics,
    recordingStartedAtRef,
    finalRecordingBlobRef,
    setIsDiarizing,
    setTranscriptionError,
    setIsPreparingToPresent,
    handleStartRequested,
    startTranscription,
    stopTranscription,
    stopRecording,
    resetAudioDiagnostics,
  }
}
