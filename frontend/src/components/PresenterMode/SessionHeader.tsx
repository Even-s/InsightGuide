import { useEffect, useState } from 'react'
import type { PresentationSession } from '@/types/presentation'
import Button from '@/components/common/Button'
import Badge from '@/components/common/Badge'
import { formatElapsedTime } from '@/utils/formatters'

interface SessionHeaderProps {
  session: PresentationSession | null
  deckId: string
  isRecording: boolean
  isPreparingToPresent?: boolean
  onStart: () => void
  onPause: () => void
  onEnd: () => void
}

const statusLabels: Record<string, string> = {
  idle: '待機',
  preparing: '準備中',
  ready: '就緒',
  presenting: '演講中',
  paused: '暫停',
  ended: '已結束',
  failed: '失敗',
}

function parseApiDate(value?: string | null) {
  if (!value) return null
  const normalized = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`
  const time = new Date(normalized).getTime()
  return Number.isFinite(time) ? time : null
}

function calculateActiveElapsedSeconds(session: PresentationSession | null) {
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
  deckId,
  isRecording,
  isPreparingToPresent = false,
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

  // Reset timer when session changes
  useEffect(() => {
    if (!session?.startedAt) {
      setElapsedSeconds(0)
    }
  }, [session?.id, session?.startedAt])

  return (
    <header className="flex h-20 shrink-0 items-center justify-between border-b border-cream-300 bg-cream-50 px-8 py-4">
      <div className="min-w-0">
        <div className="flex items-center gap-4 mb-1">
          <h1 className="text-xl font-medium text-natural-700 tracking-wide leading-relaxed">InsightGuide</h1>
          <Badge tone={session?.status === 'interviewing' ? 'green' : 'blue'}>
            {statusLabels[session?.status ?? 'idle'] ?? session?.status}
          </Badge>
        </div>
        <p className="truncate text-xs text-natural-500 leading-relaxed tracking-wide">
          Deck {deckId} · Session {session?.id ?? '尚未建立'}
        </p>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          <p className="text-xs text-natural-500 mb-1 tracking-wide">Timer</p>
          <p className={`font-mono text-xl font-semibold leading-relaxed ${elapsedSeconds > 3600 ? 'text-wood-500' : 'text-natural-700'}`}>
            {formatElapsedTime(elapsedSeconds)}
          </p>
          {elapsedSeconds > 3600 && (
            <p className="text-xs text-wood-500 mt-1 leading-relaxed">Session running for {Math.floor(elapsedSeconds / 3600)}+ hours</p>
          )}
        </div>

        {/* Control buttons */}
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
