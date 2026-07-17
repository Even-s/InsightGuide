import { useCallback, useRef, useState } from 'react'
import { interviewAPI } from '@/api/interview'
import { useRealtimeTranscription } from '@/hooks/useRealtimeTranscription'
import type { PresenterSessionRefs } from './usePresenterSessionRefs'
import { simplifiedToTraditional } from '@/utils/chineseConverter'
import { findAskedCards } from '@/components/PresenterMode/presenterUtils'
import type {
  AudioDiagnosticsSnapshot,
  AudioProcessingProfile,
} from '@/hooks/useAudioDiagnostics'

interface UseTranscriptProcessingOptions {
  sessionId: string
  refs: PresenterSessionRefs
  candidateCards: Array<{ cardId: string; questionText: string; focusText: string; score: number }>
  onBufferedAnswer: () => void
  onPreviewDetectedCards?: (cardIds: string[]) => void
  onClearPreviewDetectedCards?: () => void
  diagnosticsEnabled?: boolean
  audioProcessingProfile?: AudioProcessingProfile
}

export interface TranscriptProcessingResult {
  transcriptHistory: string[]
  pendingTranscript: string
  transcriptionError: string | null
  isPreparingToPresent: boolean
  realtimeStatus: string
  isRecording: boolean
  isTranscribing: boolean
  realtimeError: Error | null
  audioDiagnostics: AudioDiagnosticsSnapshot
  setTranscriptionError: (v: string | null) => void
  setIsPreparingToPresent: (v: boolean) => void
  handleStartRequested: () => Promise<void>
  startTranscription: () => void
  stopTranscription: () => void
  flushTranscriptSaves: () => Promise<void>
  resetAudioDiagnostics: () => void
}

function selectCompletedTranscript(
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
  onPreviewDetectedCards,
  onClearPreviewDetectedCards,
  diagnosticsEnabled = false,
  audioProcessingProfile = 'standard',
}: UseTranscriptProcessingOptions): TranscriptProcessingResult {
  const [transcriptHistory, setTranscriptHistory] = useState<string[]>([])
  const [pendingTranscript, setPendingTranscript] = useState('')
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const [isPreparingToPresent, setIsPreparingToPresent] = useState(false)

  const partialTranscriptRef = useRef('')
  const lastPreviewTextRef = useRef('')
  const pendingSavePromisesRef = useRef(new Set<Promise<unknown>>())

  const previewQuestionCardsFromPartial = useCallback((text: string) => {
    const activeTheme = refs.currentThemeRef.current
    const activeId = activeTheme?.id
    const trimmed = text.trim()

    if (!activeId || !refs.isPresentingRef.current || trimmed.length < 15) return
    if (trimmed === lastPreviewTextRef.current) return
    if (trimmed.length - lastPreviewTextRef.current.length < 8) return

    const askedCards = findAskedCards(
      trimmed,
      refs.cardStatesRef.current,
      activeId,
      2,
      {
        requireQuestionEnding: false,
        minScore: 1.4,
        includeListening: false,
      },
    )

    if (askedCards.length > 0) {
      lastPreviewTextRef.current = trimmed
      onPreviewDetectedCards?.(askedCards)
    }
  }, [onPreviewDetectedCards, refs])

  const handleTranscriptCompleted = useCallback((payload: {
    transcript: string
    itemId?: string
    startedAt?: string
    endedAt?: string
  }) => {
    let text = selectCompletedTranscript(payload.transcript, partialTranscriptRef.current)
    const activeTheme = refs.currentThemeRef.current
    const activeId = activeTheme?.id

    partialTranscriptRef.current = ''
    lastPreviewTextRef.current = ''

    if (!text || !refs.isPresentingRef.current) {
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

    const askedCards = activeId
      ? findAskedCards(text, refs.cardStatesRef.current, activeId)
      : []

    if (askedCards.length > 0) {
      onPreviewDetectedCards?.(askedCards.slice(0, 2))
    } else {
      onClearPreviewDetectedCards?.()
    }

    const savePromise = interviewAPI.createUtterance(
      sessionId,
      text,
      activeId ?? undefined,
      payload.itemId,
      payload.startedAt,
      payload.endedAt,
      askedCards.length > 0 ? askedCards : undefined,
    )
      .then(() => {
        if (candidateCards.length > 0 && askedCards.length === 0) {
          onBufferedAnswer()
        }
      })
      .catch((err) => {
        console.error('Failed to save utterance:', err)
        setTranscriptionError(err instanceof Error ? err.message : 'Failed to save transcript')
      })
      .finally(() => {
        pendingSavePromisesRef.current.delete(savePromise)
      })
    pendingSavePromisesRef.current.add(savePromise)
  }, [sessionId, refs, candidateCards.length, onBufferedAnswer, onPreviewDetectedCards, onClearPreviewDetectedCards])

  const flushTranscriptSaves = useCallback(async () => {
    await Promise.allSettled(Array.from(pendingSavePromisesRef.current))
  }, [])

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
    onSpeechStarted: () => {
      setTranscriptionError(null)
      setPendingTranscript('正在聽取...')
      partialTranscriptRef.current = ''
      lastPreviewTextRef.current = ''
      onClearPreviewDetectedCards?.()
    },
    onTranscriptDelta: (delta) => {
      const convertedDelta = simplifiedToTraditional(delta)
      setPendingTranscript((previous) => {
        const nextTranscript =
          !previous || previous === '正在聽取...' || previous === '轉錄中...'
            ? convertedDelta
            : `${previous}${convertedDelta}`

        partialTranscriptRef.current = nextTranscript
        previewQuestionCardsFromPartial(nextTranscript)
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
    realtimeStatus,
    isRecording,
    isTranscribing,
    realtimeError,
    audioDiagnostics,
    setTranscriptionError,
    setIsPreparingToPresent,
    handleStartRequested,
    startTranscription,
    stopTranscription,
    flushTranscriptSaves,
    resetAudioDiagnostics,
  }
}
