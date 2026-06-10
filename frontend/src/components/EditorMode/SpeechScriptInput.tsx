import { useRef, useState } from 'react'
import clsx from 'clsx'
import { questionCardsAPI } from '@/api/questionCards'
import { useRealtimeTranscription } from '@/hooks/useRealtimeTranscription'

interface SpeechScriptInputProps {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

function combineScript(baseText: string, spokenText: string) {
  const base = baseText.trim()
  const spoken = spokenText.trim()
  if (!base) return spoken
  if (!spoken) return base
  return `${base}\n${spoken}`
}

export default function SpeechScriptInput({
  value,
  onChange,
  disabled = false,
}: SpeechScriptInputProps) {
  const [spokenText, setSpokenText] = useState('')
  const [isCleaning, setIsCleaning] = useState(false)
  const [cleanupError, setCleanupError] = useState<string | null>(null)
  const baseTextRef = useRef('')
  const spokenTextRef = useRef('')

  const {
    status,
    isRecording,
    isTranscribing,
    error,
    startTranscription,
    stopTranscription,
  } = useRealtimeTranscription({
    onSpeechStarted: () => {
      setCleanupError(null)
    },
    onTranscriptCompleted: ({ transcript }) => {
      const nextSpokenText = combineScript(spokenTextRef.current, transcript)
      spokenTextRef.current = nextSpokenText
      setSpokenText(nextSpokenText)
      onChange(combineScript(baseTextRef.current, nextSpokenText).slice(0, 2000))
    },
  })

  const isActive = status === 'connecting' || status === 'connected' || isRecording || isTranscribing

  async function handleStart() {
    baseTextRef.current = value
    spokenTextRef.current = ''
    setSpokenText('')
    setCleanupError(null)
    await startTranscription()
  }

  async function handleStopAndClean() {
    stopTranscription()

    const rawSpokenText = spokenTextRef.current.trim()
    if (!rawSpokenText) {
      setCleanupError('尚未收到語音轉錄內容')
      return
    }

    setIsCleaning(true)
    setCleanupError(null)
    try {
      const cleanedText = await questionCardsAPI.cleanupFollowup(rawSpokenText)
      onChange(combineScript(baseTextRef.current, cleanedText).slice(0, 2000))
      spokenTextRef.current = cleanedText
      setSpokenText(cleanedText)
    } catch (cleanupErr) {
      setCleanupError(cleanupErr instanceof Error ? cleanupErr.message : '語音內容清理失敗')
    } finally {
      setIsCleaning(false)
    }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={isActive ? handleStopAndClean : handleStart}
          disabled={disabled || isCleaning || status === 'connecting'}
          className={clsx(
            'inline-flex items-center gap-1.5 rounded border px-2.5 py-1.5 text-xs font-medium transition-colors',
            isActive
              ? 'border-wood-300 bg-wood-50 text-wood-700 hover:bg-wood-100'
              : 'border-sage-200 bg-sage-50 text-sage-700 hover:bg-sage-100',
            (disabled || isCleaning || status === 'connecting') && 'cursor-not-allowed opacity-60'
          )}
        >
          {isCleaning || status === 'connecting' ? (
            <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          ) : (
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18.5v2.25m0 0h3m-3 0H9m6.75-9.75A3.75 3.75 0 0112 14.75 3.75 3.75 0 018.25 11V6.75a3.75 3.75 0 117.5 0V11zM6 10.75a6 6 0 0012 0" />
            </svg>
          )}
          {isCleaning
            ? '清理中'
            : isActive
              ? '完成語音輸入'
              : '語音輸入'}
        </button>
        <span className="text-xs text-gray-500">
          {status === 'connecting' && '連接麥克風中'}
          {status === 'connected' && (isTranscribing ? '辨識中' : '聆聽中')}
          {status === 'idle' && spokenText && !isCleaning && '已清理並回填'}
        </span>
      </div>
      {(error || cleanupError) && (
        <p className="text-xs text-red-600">{cleanupError ?? error?.message}</p>
      )}
    </div>
  )
}
