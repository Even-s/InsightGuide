import { useEffect, useState } from 'react'
import type { InterviewSession } from '@/types/interview'
import Button from '@/components/common/Button'
import { formatElapsedTime } from '@/utils/formatters'

interface SessionHeaderProps {
  session: InterviewSession | null
  documentId: string
  isRecording: boolean
  isPreparingToPresent?: boolean
  currentThemeTitle?: string
  currentThemeIndex?: number
  totalThemes?: number
  onStart: () => void
  onPause: () => void
  onEnd: () => void
}

function parseApiDate(value?: string | null) {
  if (!value) return null
  const normalized = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`
  const time = new Date(normalized).getTime()
  return Number.isFinite(time) ? time : null
}

function calculateActiveElapsedSeconds(session: InterviewSession | null) {
  if (!session?.startedAt) return 0

  const startedAt = parseApiDate(session.startedAt)
  if (!startedAt) return 0

  const pausedDurationMs = Math.max(0, session.pausedDurationSeconds ?? 0) * 1000
  let effectiveEnd = Date.now()

  if (session.status === 'paused') {
    effectiveEnd = parseApiDate(session.pausedAt) ?? effectiveEnd
  } else if (session.status === 'ended') {
    effectiveEnd = parseApiDate(session.endedAt) ?? effectiveEnd
  }

  const elapsedMs = Math.max(0, effectiveEnd - startedAt - pausedDurationMs)
  return Math.floor(elapsedMs / 1000)
}

export default function SessionHeader({
  session,
  isRecording,
  isPreparingToPresent = false,
  currentThemeTitle,
  currentThemeIndex = 0,
  totalThemes = 0,
  onStart,
  onPause,
  onEnd,
}: SessionHeaderProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  useEffect(() => {
    if (!session?.startedAt) {
      setElapsedSeconds(0)
      return
    }

    if (session.status !== 'interviewing') {
      setElapsedSeconds(calculateActiveElapsedSeconds(session))
      return
    }

    const update = () => {
      setElapsedSeconds(calculateActiveElapsedSeconds(session))
    }

    update()
    const intervalId = window.setInterval(update, 1000)
    return () => window.clearInterval(intervalId)
  }, [
    session,
    session?.endedAt,
    session?.pausedAt,
    session?.pausedDurationSeconds,
    session?.startedAt,
    session?.status,
  ])

  useEffect(() => {
    if (!session?.startedAt) {
      setElapsedSeconds(0)
    }
  }, [session?.id, session?.startedAt])

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-cream-300 bg-cream-50 px-4">
      {/* Left: theme title */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm font-medium text-natural-700 truncate">
          {currentThemeTitle || '—'}
        </span>
        <span className="text-xs text-natural-300 shrink-0">
          {currentThemeIndex + 1}/{totalThemes}
        </span>
      </div>

      {/* Right: timer + controls */}
      <div className="flex items-center gap-4">
        <span className={`font-mono text-sm tabular-nums ${elapsedSeconds > 3600 ? 'text-wood-500' : 'text-natural-300'}`}>
          {formatElapsedTime(elapsedSeconds)}
        </span>

        {session?.status === 'idle' || session?.status === 'ready' ? (
          <Button
            variant="primary"
            size="sm"
            onClick={onStart}
            disabled={isRecording || isPreparingToPresent}
          >
            {isPreparingToPresent ? '準備中' : '開始'}
          </Button>
        ) : session?.status === 'interviewing' ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={onPause}
          >
            暫停
          </Button>
        ) : session?.status === 'paused' ? (
          <Button
            variant="primary"
            size="sm"
            onClick={onStart}
            disabled={isPreparingToPresent}
          >
            {isPreparingToPresent ? '準備中' : '繼續'}
          </Button>
        ) : null}

        <Button variant="danger" size="sm" onClick={onEnd} disabled={!session || session.status === 'ended'}>
          停止
        </Button>
      </div>
    </header>
  )
}
