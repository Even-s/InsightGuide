import { useEffect, useRef, useState } from 'react'
import { createStakeholder, voiceToStakeholderProfileDraft } from '@/api/projects'
import { useAnimatedExit } from '@/hooks/useAnimatedExit'

const STAKEHOLDER_TYPES = [
  { value: 'business', label: '業務' },
  { value: 'product', label: '產品' },
  { value: 'engineering', label: '工程' },
  { value: 'management', label: '管理' },
  { value: 'operations', label: '維運' },
  { value: 'customer_support', label: '客服' },
  { value: 'legal', label: '法務' },
  { value: 'finance', label: '財務' },
  { value: 'design', label: '設計' },
  { value: 'qa', label: '品保' },
  { value: 'user', label: '使用者' },
  { value: 'other', label: '其他' },
]

interface AddProfileModalProps {
  slotId: string
  projectId: string
  onClose: () => void
  onAdd: () => void
}

export function AddProfileModal({ slotId, projectId, onClose, onAdd }: AddProfileModalProps) {
  const [profileName, setProfileName] = useState('')
  const [profileRole, setProfileRole] = useState('')
  const [profileType, setProfileType] = useState('business')
  const [profileDept, setProfileDept] = useState('')
  const [profileExpertise, setProfileExpertise] = useState('')
  const [profileBoundaries, setProfileBoundaries] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessingVoice, setIsProcessingVoice] = useState(false)
  const [voiceError, setVoiceError] = useState<string | null>(null)
  const [voiceMessage, setVoiceMessage] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const { isExiting, exit } = useAnimatedExit(onClose)

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

  const applyVoiceDraft = (draft: Awaited<ReturnType<typeof voiceToStakeholderProfileDraft>>['draft']) => {
    setProfileName(draft.name)
    setProfileRole(draft.role_title)
    setProfileDept(draft.department)
    setProfileType(draft.stakeholder_type)
    setProfileExpertise(draft.expertise_tags.join(', '))
    setProfileBoundaries(draft.knowledge_boundaries.join(', '))
  }

  const startVoiceInput = async () => {
    if (isRecording || isProcessingVoice) return
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
          const result = await voiceToStakeholderProfileDraft(projectId, slotId, blob)
          applyVoiceDraft(result.draft)
          const transcript = result.transcript?.trim()
          const preview = transcript && transcript.length > 60
            ? `${transcript.slice(0, 60)}…`
            : transcript
          const nameReminder = result.draft.name ? '' : ' 請補上姓名。'
          setVoiceMessage(
            `${preview ? `已從語音填入：「${preview}」` : '已從語音填入受訪者資料。'}${nameReminder}`,
          )
        } catch (error) {
          console.error('Failed to fill stakeholder profile from voice:', error)
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
      console.error('Failed to start stakeholder profile recording:', error)
      stopRecordingStream()
      setVoiceError('無法使用麥克風，請確認瀏覽器已允許錄音權限。')
    }
  }

  const stopVoiceInput = () => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
  }

  const handleClose = () => {
    if (isProcessingVoice || isExiting) return
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null
      recorder.stop()
    }
    stopRecordingStream()
    exit()
  }

  const handleAddProfile = async () => {
    if (!projectId || !profileName.trim() || isRecording || isProcessingVoice) return
    try {
      await createStakeholder(projectId, {
        slot_ids: slotId ? [slotId] : [],
        primary_slot_id: slotId || null,
        name: profileName.trim(),
        role_title: profileRole.trim() || undefined,
        department: profileDept.trim() || undefined,
        stakeholder_type: profileType,
        expertise_tags: profileExpertise.split(',').map(s => s.trim()).filter(Boolean),
        knowledge_boundaries: profileBoundaries.split(',').map(s => s.trim()).filter(Boolean),
      })
      exit(onAdd)
    } catch (err) {
      console.error('Failed to create stakeholder:', err)
    }
  }

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 ${isExiting ? 'motion-backdrop-out pointer-events-none' : 'motion-backdrop-in'}`} onClick={handleClose}>
      <div className={`max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-natural ${isExiting ? 'motion-modal-out' : 'motion-modal-in'}`} onClick={e => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-natural-800">新增受訪者</h3>
            <p className="mt-1 text-xs text-natural-500">填寫資料，或直接口述讓系統協助整理。</p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={isProcessingVoice}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-natural-400 hover:bg-cream-100 hover:text-natural-700 disabled:opacity-40"
            aria-label="關閉新增受訪者"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <section className="mb-5 border-l-2 border-sage-300 bg-sage-50/60 px-4 py-3" aria-label="語音輸入">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-natural-700">口述受訪者資料</p>
              <p className="mt-1 text-xs leading-5 text-natural-500">
                例如：王小明是門診櫃台組長，熟悉掛號流程，但不熟系統架構。
              </p>
            </div>
            <button
              type="button"
              onClick={isRecording ? stopVoiceInput : startVoiceInput}
              disabled={isProcessingVoice}
              className={`inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                isRecording
                  ? 'bg-red-500 text-white hover:bg-red-600'
                  : 'border border-sage-300 bg-white text-sage-600 hover:bg-sage-100'
              }`}
              aria-label={isRecording ? '停止並填入' : '語音輸入'}
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

        <div className="space-y-3">
          <div>
            <label htmlFor="profile-name" className="mb-1 block text-sm font-medium text-natural-700">姓名 *</label>
            <input
              id="profile-name"
              type="text"
              value={profileName}
              onChange={e => setProfileName(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="受訪者姓名"
            />
          </div>
          <div>
            <label htmlFor="profile-role" className="mb-1 block text-sm font-medium text-natural-700">職稱</label>
            <input
              id="profile-role"
              type="text"
              value={profileRole}
              onChange={e => setProfileRole(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="例：資深業務經理"
            />
          </div>
          <div>
            <label htmlFor="profile-department" className="mb-1 block text-sm font-medium text-natural-700">部門</label>
            <input
              id="profile-department"
              type="text"
              value={profileDept}
              onChange={e => setProfileDept(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="例：業務部"
            />
          </div>
          <div>
            <label htmlFor="profile-type" className="mb-1 block text-sm font-medium text-natural-700">角色類型</label>
            <select
              id="profile-type"
              value={profileType}
              onChange={e => setProfileType(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            >
              {STAKEHOLDER_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="profile-expertise" className="mb-1 block text-sm font-medium text-natural-700">
              專長領域（逗號分隔）
            </label>
            <input
              id="profile-expertise"
              type="text"
              value={profileExpertise}
              onChange={e => setProfileExpertise(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="sales_process, customer_pain_points, pricing"
            />
          </div>
          <div>
            <label htmlFor="profile-boundaries" className="mb-1 block text-sm font-medium text-natural-700">
              不熟悉領域（逗號分隔）
            </label>
            <input
              id="profile-boundaries"
              type="text"
              value={profileBoundaries}
              onChange={e => setProfileBoundaries(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="technical_architecture, database, deployment"
            />
          </div>
        </div>
        <div className="mt-5 flex gap-3">
          <button
            onClick={handleAddProfile}
            disabled={!profileName.trim() || isRecording || isProcessingVoice}
            className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:opacity-50"
          >
            新增
          </button>
          <button
            onClick={handleClose}
            disabled={isProcessingVoice}
            className="px-4 py-2 bg-cream-100 text-natural-700 rounded-lg hover:bg-cream-200 disabled:opacity-50"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
