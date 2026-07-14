import { useEffect, useRef, useState } from 'react'
import {
  generateInterviewGuide,
  voiceToInterviewGuideDraft,
  type InterviewGuide,
  type InterviewGuideDraft,
  type InterviewGuideOptions,
} from '@/api/projects'
import { useAnimatedExit } from '@/hooks/useAnimatedExit'

interface GuideSettingsModalProps {
  profileId: string
  projectId: string
  onClose: () => void
  onGenerated: (profileId: string, guide: InterviewGuide) => void
}

export function GuideSettingsModal({ profileId, projectId, onClose, onGenerated }: GuideSettingsModalProps) {
  const [guideOpts, setGuideOpts] = useState<InterviewGuideOptions>({ duration_minutes: 30 })
  const [generating, setGenerating] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessingVoice, setIsProcessingVoice] = useState(false)
  const [voiceError, setVoiceError] = useState<string | null>(null)
  const [voiceMessage, setVoiceMessage] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const guideOptsRef = useRef(guideOpts)
  const { isExiting, exit } = useAnimatedExit(onClose)

  useEffect(() => {
    guideOptsRef.current = guideOpts
  }, [guideOpts])

  const currentGuideDraft = (): InterviewGuideDraft => ({
    duration_minutes: guideOptsRef.current.duration_minutes ?? 30,
    interview_purpose: guideOptsRef.current.interview_purpose ?? '',
    focus_topics: guideOptsRef.current.focus_topics ?? '',
    exclude_topics: guideOptsRef.current.exclude_topics ?? '',
    interview_style: guideOptsRef.current.interview_style ?? '',
  })

  const stopRecordingStream = () => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
  }

  useEffect(() => {
    return () => {
      const recorder = recorderRef.current
      if (recorder && recorder.state !== 'inactive') {
        recorder.onstop = null
        recorder.stop()
      }
      streamRef.current?.getTracks().forEach(track => track.stop())
    }
  }, [])

  const startVoiceInput = async () => {
    if (isRecording || isProcessingVoice || generating) return
    setVoiceError(null)
    setVoiceMessage(null)

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setVoiceError('目前的瀏覽器不支援錄音，請改用文字輸入。')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []

      const preferredMimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
      const mimeType = typeof MediaRecorder.isTypeSupported === 'function'
        ? preferredMimeTypes.find(type => MediaRecorder.isTypeSupported(type))
        : undefined
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)
      recorderRef.current = recorder

      recorder.ondataavailable = event => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onerror = () => {
        setVoiceError('錄音發生錯誤，請重新嘗試。')
        setIsRecording(false)
        stopRecordingStream()
      }
      recorder.onstop = async () => {
        setIsRecording(false)
        stopRecordingStream()
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        })
        chunksRef.current = []
        if (blob.size < 1000) {
          setVoiceError('錄音太短，請再說明一次。')
          return
        }

        setIsProcessingVoice(true)
        try {
          const result = await voiceToInterviewGuideDraft(
            projectId,
            profileId,
            blob,
            currentGuideDraft(),
          )
          setGuideOpts(options => ({ ...options, ...result.draft }))
          const transcript = result.transcript?.trim()
          const preview = transcript && transcript.length > 70
            ? `${transcript.slice(0, 70)}…`
            : transcript
          setVoiceMessage(
            preview ? `已從語音更新設定：「${preview}」` : '已從語音更新訪談大綱設定。',
          )
        } catch (error) {
          console.error('Failed to fill interview guide settings from voice:', error)
          const response = (error as { response?: { data?: { detail?: unknown } } })?.response
          setVoiceError(
            typeof response?.data?.detail === 'string'
              ? response.data.detail
              : '語音填入失敗，請稍後再試。',
          )
        } finally {
          setIsProcessingVoice(false)
          recorderRef.current = null
        }
      }

      recorder.start()
      setIsRecording(true)
    } catch (error) {
      console.error('Failed to start interview guide recording:', error)
      stopRecordingStream()
      setVoiceError('無法使用麥克風，請確認瀏覽器已允許錄音權限。')
    }
  }

  const stopVoiceInput = () => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
  }

  const handleClose = () => {
    if (generating || isProcessingVoice || isExiting) return
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null
      recorder.stop()
    }
    stopRecordingStream()
    exit()
  }

  const handleGenerate = async () => {
    try {
      setGenerating(true)
      const cleanOpts: InterviewGuideOptions = { duration_minutes: guideOpts.duration_minutes }
      if (guideOpts.interview_purpose) cleanOpts.interview_purpose = guideOpts.interview_purpose
      if (guideOpts.focus_topics) cleanOpts.focus_topics = guideOpts.focus_topics
      if (guideOpts.exclude_topics) cleanOpts.exclude_topics = guideOpts.exclude_topics
      if (guideOpts.interview_style) cleanOpts.interview_style = guideOpts.interview_style
      const result = await generateInterviewGuide(projectId, profileId, cleanOpts)
      onGenerated(profileId, result)
      exit()
    } catch (err) {
      console.error('Failed to generate guide:', err)
      alert('生成失敗，請稍後再試')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 ${isExiting ? 'motion-backdrop-out pointer-events-none' : 'motion-backdrop-in'}`} onClick={handleClose}>
      <div className={`max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-natural ${isExiting ? 'motion-modal-out' : 'motion-modal-in'}`} onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-natural-800 mb-1">訪談大綱設定</h3>
        <p className="text-sm text-natural-500 mb-4">調整後按「生成」，AI 會根據設定產生訪談問題卡片</p>

        <section className="mb-5 border-l-2 border-sage-300 bg-sage-50/60 px-4 py-3" aria-label="訪談大綱語音輸入">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-natural-700">口述大綱設定</p>
              <p className="mt-1 text-xs leading-5 text-natural-500">
                例如：訪談 45 分鐘，聚焦掛號尖峰與例外流程，不問系統架構，採探索型訪談。
              </p>
            </div>
            <button
              type="button"
              onClick={isRecording ? stopVoiceInput : startVoiceInput}
              disabled={isProcessingVoice || generating}
              className={`inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                isRecording
                  ? 'bg-red-500 text-white hover:bg-red-600'
                  : 'border border-sage-300 bg-white text-sage-600 hover:bg-sage-100'
              }`}
              aria-label={isRecording ? '停止並填入大綱設定' : '語音輸入大綱設定'}
            >
              {isProcessingVoice ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-sage-200 border-t-sage-500" aria-hidden="true" />
              ) : isRecording ? (
                <span className="h-3 w-3 bg-white" aria-hidden="true" />
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3zM5 10v2a7 7 0 0014 0v-2M12 19v3m-4 0h8" />
                </svg>
              )}
              {isProcessingVoice ? '語音分析中…' : isRecording ? '停止並填入' : '語音輸入'}
            </button>
          </div>
          {isRecording && (
            <p className="motion-status-in mt-3 flex items-center gap-2 text-xs font-medium text-red-600" role="status">
              <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" aria-hidden="true" />
              錄音中，說完後請按「停止並填入」。
            </p>
          )}
          {voiceMessage && !isRecording && (
            <p className="motion-status-in mt-3 text-xs leading-5 text-sage-700" role="status">{voiceMessage}</p>
          )}
          {voiceError && (
            <p className="motion-status-in mt-3 text-xs leading-5 text-red-600" role="alert">{voiceError}</p>
          )}
        </section>

        <fieldset disabled={isRecording || isProcessingVoice || generating} className="space-y-4 disabled:opacity-60">
          <div>
            <label htmlFor="guide-duration" className="block text-sm font-medium text-natural-700 mb-1">預計訪談時長</label>
            <div className="flex items-center gap-3">
              <input
                id="guide-duration"
                type="range"
                min={10}
                max={90}
                step={5}
                value={guideOpts.duration_minutes ?? 30}
                onChange={e => setGuideOpts(o => ({ ...o, duration_minutes: Number(e.target.value) }))}
                className="flex-1 h-2 bg-cream-200 rounded-lg appearance-none cursor-pointer accent-sage-400"
              />
              <span className="w-16 text-center text-sm font-medium text-natural-700 tabular-nums">
                {guideOpts.duration_minutes ?? 30} 分鐘
              </span>
            </div>
            <div className="flex justify-between mt-1 text-xs text-natural-400 px-0.5">
              <span>10 min</span>
              <span>90 min</span>
            </div>
          </div>

          <div>
            <label htmlFor="guide-purpose" className="block text-sm font-medium text-natural-700 mb-1">這次訪談目的</label>
            <input
              id="guide-purpose"
              type="text"
              value={guideOpts.interview_purpose || ''}
              onChange={e => setGuideOpts(o => ({ ...o, interview_purpose: e.target.value }))}
              placeholder="例：了解現有銷售流程的痛點"
              className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            />
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {['初次探索', '深入追問', '驗證需求', '確認設計', '了解現況'].map(tag => (
                <button
                  type="button"
                  key={tag}
                  onClick={() => setGuideOpts(o => ({ ...o, interview_purpose: tag }))}
                  className="px-2 py-0.5 text-xs bg-cream-100 text-natural-600 rounded hover:bg-sage-50 hover:text-sage-600"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="guide-focus-topics" className="block text-sm font-medium text-natural-700 mb-1">聚焦主題</label>
            <input
              id="guide-focus-topics"
              type="text"
              value={guideOpts.focus_topics || ''}
              onChange={e => setGuideOpts(o => ({ ...o, focus_topics: e.target.value }))}
              placeholder="例：庫存管理流程、客訴處理"
              className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            />
          </div>

          <div>
            <label htmlFor="guide-exclude-topics" className="block text-sm font-medium text-natural-700 mb-1">排除主題（不要問）</label>
            <input
              id="guide-exclude-topics"
              type="text"
              value={guideOpts.exclude_topics || ''}
              onChange={e => setGuideOpts(o => ({ ...o, exclude_topics: e.target.value }))}
              placeholder="例：技術架構、資料庫設計"
              className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">訪談風格</label>
            <div className="flex gap-2">
              {[
                { value: 'exploratory', label: '探索型', desc: '開放、廣泛' },
                { value: 'structured', label: '結構化', desc: '精確、逐項' },
                { value: 'validation', label: '驗證型', desc: '確認假設' },
              ].map(style => (
                <button
                  type="button"
                  key={style.value}
                  onClick={() => setGuideOpts(o => ({ ...o, interview_style: style.value }))}
                  className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors text-center ${
                    guideOpts.interview_style === style.value
                      ? 'bg-sage-50 border-sage-300 text-sage-700'
                      : 'border-cream-200 text-natural-600 hover:bg-cream-50'
                  }`}
                >
                  <div className="font-medium">{style.label}</div>
                  <div className="text-xs text-natural-400">{style.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </fieldset>

        <div className="flex gap-3 mt-6">
          <button
            onClick={handleGenerate}
            disabled={generating || isRecording || isProcessingVoice || isExiting}
            className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 text-sm font-medium disabled:opacity-50"
          >
            {generating ? '生成中...' : '生成訪談大綱'}
          </button>
          <button
            onClick={handleClose}
            disabled={generating || isProcessingVoice || isExiting}
            className="px-4 py-2 bg-cream-100 text-natural-700 rounded-lg hover:bg-cream-200 text-sm disabled:opacity-50"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
