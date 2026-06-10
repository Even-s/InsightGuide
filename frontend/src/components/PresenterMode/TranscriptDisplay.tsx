import { useEffect, useMemo, useRef, useState } from 'react'

interface TranscriptDisplayProps {
  transcriptHistory: string[] // 最近 3 句轉錄
  pendingTranscript?: string
  isRecording: boolean
  isTranscribing?: boolean
  error?: string | null
}

export default function TranscriptDisplay({
  pendingTranscript,
  isRecording,
  isTranscribing,
  error
}: TranscriptDisplayProps) {
  const activeTranscript = useMemo(
    () => pendingTranscript
      ? getActiveTranscriptSentence(pendingTranscript)
      : { sentence: '', sentenceKey: '' },
    [pendingTranscript],
  )
  const [displayedTranscript, setDisplayedTranscript] = useState(activeTranscript)
  const [outgoingTranscript, setOutgoingTranscript] = useState<typeof activeTranscript | null>(null)
  const displayedTranscriptRef = useRef(displayedTranscript)
  const previousSentenceKeyRef = useRef(activeTranscript.sentenceKey)
  const idleTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    displayedTranscriptRef.current = displayedTranscript
  }, [displayedTranscript])

  useEffect(() => {
    return () => {
      if (idleTimeoutRef.current) {
        window.clearTimeout(idleTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!activeTranscript.sentence) {
      setOutgoingTranscript(null)

      if (idleTimeoutRef.current) {
        window.clearTimeout(idleTimeoutRef.current)
      }

      idleTimeoutRef.current = window.setTimeout(() => {
        setDisplayedTranscript(activeTranscript)
        previousSentenceKeyRef.current = activeTranscript.sentenceKey
        idleTimeoutRef.current = null
      }, 30000)

      return
    }

    if (idleTimeoutRef.current) {
      window.clearTimeout(idleTimeoutRef.current)
      idleTimeoutRef.current = null
    }

    if (activeTranscript.sentenceKey === previousSentenceKeyRef.current) {
      setDisplayedTranscript(activeTranscript)
      return
    }

    const previousTranscript = displayedTranscriptRef.current
    setOutgoingTranscript(previousTranscript.sentence ? previousTranscript : null)
    setDisplayedTranscript(activeTranscript)
    previousSentenceKeyRef.current = activeTranscript.sentenceKey

    const timeoutId = window.setTimeout(() => {
      setOutgoingTranscript(null)
    }, 180)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [activeTranscript])

  const getStatusText = () => {
    if (error) return '錯誤'
    if (isTranscribing) return '轉錄中...'
    if (isRecording) return '正在聽取'
    return '未錄音'
  }

  const getStatusColor = () => {
    if (error) return 'bg-wood-400'
    if (isTranscribing) return 'animate-pulse bg-wood-300'
    if (isRecording) return 'animate-pulse bg-sage-400'
    return 'bg-natural-300'
  }

  return (
    <section className="flex h-16 shrink-0 bg-wood-100 border-t border-cream-300">
      {/* Status indicator on left */}
      <div className="flex items-center px-4 py-2 border-r border-cream-300">
        <div className="flex items-center gap-2">
          {/* Pulsing dot indicator */}
          <div className="relative flex h-3 w-3">
            {(isRecording || isTranscribing) && (
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                error ? 'bg-wood-400' : isTranscribing ? 'bg-wood-300' : 'bg-sage-400'
              }`} />
            )}
            <span className={`relative inline-flex rounded-full h-3 w-3 ${getStatusColor()}`} />
          </div>
          <span className="text-xs font-medium text-natural-600 whitespace-nowrap tracking-wide">
            {getStatusText()}
          </span>
        </div>
      </div>

      {/* Transcript content on right - sentence-by-sentence list + streaming */}
      <div
        className="min-w-0 flex-1 overflow-hidden px-6 py-2"
      >
        {error ? (
          <div className="flex h-full items-center gap-2 text-wood-500">
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <p className="text-sm">{error}</p>
          </div>
        ) : !displayedTranscript.sentence ? (
          <div className="flex h-full items-center gap-2 text-natural-400">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
            <span className="text-sm tracking-wide">等待語音輸入...</span>
          </div>
        ) : (
          <div className="relative h-full min-w-0">
            {outgoingTranscript?.sentence && (
              <TranscriptLine
                key={`out-${outgoingTranscript.sentenceKey}`}
                sentence={outgoingTranscript.sentence}
                className="absolute inset-0 animate-fadeOut text-natural-500"
                showCursor={false}
              />
            )}
            <TranscriptLine
              key={displayedTranscript.sentenceKey}
              sentence={displayedTranscript.sentence}
              className="animate-fadeIn text-sage-600"
              showCursor
            />
          </div>
        )}
      </div>
    </section>
  )
}

function TranscriptLine({
  sentence,
  className,
  showCursor,
}: {
  sentence: string
  className?: string
  showCursor: boolean
}) {
  return (
    <div className={`flex h-full min-w-0 items-center gap-2 ${className ?? ''}`}>
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-sage-400" />
      <p className="min-w-0 truncate text-base font-normal leading-relaxed tracking-wide">
        <span>{sentence}</span>
        {showCursor && (
          <span className="ml-1 inline-block h-4 w-0.5 bg-sage-500 animate-blink align-middle" />
        )}
      </p>
    </div>
  )
}

function getActiveTranscriptSentence(text: string) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (!normalized || normalized === '正在聽取...' || normalized === '轉錄中...') {
    return { sentence: '', sentenceKey: '' }
  }

  const sentences = normalized
    .split(/(?<=[。！？!?])\s*/)
    .map((sentence) => sentence.trim())
    .filter(Boolean)

  return {
    sentence: sentences[sentences.length - 1] ?? '',
    sentenceKey: String(Math.max(sentences.length - 1, 0)),
  }
}
