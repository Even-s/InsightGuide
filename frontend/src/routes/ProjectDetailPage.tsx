import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  refineStakeholderSlotDraft,
  regenerateStakeholderPlan,
  voiceToStakeholderSlotDraft,
  type InterviewGuide,
  type StakeholderSlotDraft,
} from '@/api/projects'
import { useProjectData } from '@/hooks/useProjectData'
import { useSlotManagement } from '@/hooks/useSlotManagement'
import { AddProfileModal } from '@/components/ProjectDetail/AddProfileModal'
import { GuideSettingsModal } from '@/components/ProjectDetail/GuideSettingsModal'
import { StartInterviewModal } from '@/components/ProjectDetail/StartInterviewModal'
import { SlotList } from '@/components/ProjectDetail/SlotList'

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

function getApiErrorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { detail?: unknown } } })?.response
  return typeof response?.data?.detail === 'string' ? response.data.detail : fallback
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { dashboard, plan, loading, guideStatuses, setGuideStatuses, loadData } = useProjectData(projectId)
  const [showAddProfile, setShowAddProfile] = useState<string | null>(null)
  const [showStartInterview, setShowStartInterview] = useState(false)
  const [showGuideSettings, setShowGuideSettings] = useState<string | null>(null)
  const [regeneratingPlan, setRegeneratingPlan] = useState(false)
  const [regenerateError, setRegenerateError] = useState<string | null>(null)
  const [isRecordingSlot, setIsRecordingSlot] = useState(false)
  const [isProcessingSlotVoice, setIsProcessingSlotVoice] = useState(false)
  const [isRefiningSlot, setIsRefiningSlot] = useState(false)
  const [slotAssistError, setSlotAssistError] = useState<string | null>(null)
  const [slotAssistMessage, setSlotAssistMessage] = useState<string | null>(null)
  const slotRecorderRef = useRef<MediaRecorder | null>(null)
  const slotRecordingStreamRef = useRef<MediaStream | null>(null)
  const slotRecordingChunksRef = useRef<Blob[]>([])

  const {
    editingSlot,
    setEditingSlot,
    editForm,
    setEditForm,
    slotActionError,
    showAddSlot,
    setShowAddSlot,
    newSlotLabel,
    setNewSlotLabel,
    newSlotCategory,
    setNewSlotCategory,
    newSlotRationale,
    setNewSlotRationale,
    newSlotPriority,
    setNewSlotPriority,
    newSlotMinInterviews,
    setNewSlotMinInterviews,
    newSlotFirstWave,
    setNewSlotFirstWave,
    newSlotExpectedContributions,
    setNewSlotExpectedContributions,
    newSlotKeyQuestions,
    setNewSlotKeyQuestions,
    handleSkipSlot,
    handleUnskipSlot,
    handleMoveSlot,
    handleDeleteSlot,
    handleAddSlot,
    handleDeleteProfile,
    handleReassignProfile,
    handleUpdateSlot,
  } = useSlotManagement({ projectId, plan, loadData })

  useEffect(() => {
    return () => {
      const recorder = slotRecorderRef.current
      if (recorder && recorder.state !== 'inactive') {
        recorder.onstop = null
        recorder.stop()
      }
      slotRecordingStreamRef.current?.getTracks().forEach(track => track.stop())
    }
  }, [])

  useEffect(() => {
    if (!showAddSlot) {
      setSlotAssistError(null)
      setSlotAssistMessage(null)
    }
  }, [showAddSlot])

  const getCurrentSlotDraft = (): StakeholderSlotDraft => ({
    role_category: newSlotCategory,
    role_label: newSlotLabel.trim(),
    rationale: newSlotRationale.trim(),
    expected_contributions: newSlotExpectedContributions
      .split(/[,，\n]/)
      .map(item => item.trim())
      .filter(Boolean),
    key_questions_to_cover: newSlotKeyQuestions
      .split('\n')
      .map(item => item.trim())
      .filter(Boolean),
    priority: newSlotPriority,
    min_interviews: newSlotMinInterviews,
    first_wave: newSlotFirstWave,
  })

  const applySlotDraft = (draft: StakeholderSlotDraft) => {
    setNewSlotLabel(draft.role_label)
    setNewSlotCategory(draft.role_category)
    setNewSlotRationale(draft.rationale)
    setNewSlotPriority(draft.priority)
    setNewSlotMinInterviews(draft.min_interviews)
    setNewSlotFirstWave(draft.first_wave)
    setNewSlotExpectedContributions(draft.expected_contributions.join(', '))
    setNewSlotKeyQuestions(draft.key_questions_to_cover.join('\n'))
  }

  const stopSlotRecordingStream = () => {
    slotRecordingStreamRef.current?.getTracks().forEach(track => track.stop())
    slotRecordingStreamRef.current = null
  }

  const startSlotRecording = async () => {
    if (!projectId || isRecordingSlot || isProcessingSlotVoice || isRefiningSlot) return
    setSlotAssistError(null)
    setSlotAssistMessage(null)

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setSlotAssistError('目前的瀏覽器不支援錄音，請改用文字輸入。')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      slotRecordingStreamRef.current = stream
      slotRecordingChunksRef.current = []

      const preferredMimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
      const mimeType = preferredMimeTypes.find(type => MediaRecorder.isTypeSupported(type))
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)
      slotRecorderRef.current = recorder

      recorder.ondataavailable = event => {
        if (event.data.size > 0) slotRecordingChunksRef.current.push(event.data)
      }
      recorder.onerror = () => {
        setSlotAssistError('錄音發生錯誤，請重新嘗試。')
        setIsRecordingSlot(false)
        stopSlotRecordingStream()
      }
      recorder.onstop = async () => {
        setIsRecordingSlot(false)
        stopSlotRecordingStream()
        const blob = new Blob(slotRecordingChunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        })
        slotRecordingChunksRef.current = []
        if (blob.size < 1000) {
          setSlotAssistError('錄音太短，請再說明一次。')
          return
        }

        setIsProcessingSlotVoice(true)
        try {
          const result = await voiceToStakeholderSlotDraft(projectId, blob)
          applySlotDraft(result.draft)
          const transcript = result.transcript?.trim()
          const preview = transcript && transcript.length > 70
            ? `${transcript.slice(0, 70)}…`
            : transcript
          setSlotAssistMessage(preview ? `已從語音填入草稿：「${preview}」` : '已從語音填入草稿。')
        } catch (error) {
          console.error('Failed to fill stakeholder role from voice:', error)
          setSlotAssistError(getApiErrorMessage(error, '語音填入失敗，請稍後再試。'))
        } finally {
          setIsProcessingSlotVoice(false)
          slotRecorderRef.current = null
        }
      }

      recorder.start()
      setIsRecordingSlot(true)
    } catch (error) {
      console.error('Failed to start stakeholder role recording:', error)
      stopSlotRecordingStream()
      setSlotAssistError('無法使用麥克風，請確認瀏覽器已允許錄音權限。')
    }
  }

  const stopSlotRecording = () => {
    const recorder = slotRecorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
  }

  const closeAddSlotForm = () => {
    const recorder = slotRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null
      recorder.stop()
    }
    stopSlotRecordingStream()
    slotRecorderRef.current = null
    setIsRecordingSlot(false)
    setSlotAssistError(null)
    setSlotAssistMessage(null)
    setShowAddSlot(false)
  }

  const handleRefineSlotDraft = async () => {
    if (!projectId || !newSlotLabel.trim() || isRefiningSlot || isProcessingSlotVoice) return
    setIsRefiningSlot(true)
    setSlotAssistError(null)
    setSlotAssistMessage(null)
    try {
      const result = await refineStakeholderSlotDraft(projectId, getCurrentSlotDraft())
      applySlotDraft(result.draft)
      setSlotAssistMessage('AI 已補充並優化內容，請確認後再新增。')
    } catch (error) {
      console.error('Failed to refine stakeholder role draft:', error)
      setSlotAssistError(getApiErrorMessage(error, 'AI 優化失敗，請稍後再試。'))
    } finally {
      setIsRefiningSlot(false)
    }
  }

  const handleGuideGenerated = (profileId: string, guide: InterviewGuide) => {
    setGuideStatuses(prev => ({ ...prev, [profileId]: guide }))
  }

  const handleRegeneratePlan = async () => {
    if (!projectId || regeneratingPlan) return
    setRegeneratingPlan(true)
    setRegenerateError(null)
    try {
      await regenerateStakeholderPlan(projectId)
      await loadData()
    } catch (error) {
      console.error('Failed to regenerate stakeholder plan:', error)
      setRegenerateError('重新生成失敗，請查看後端 log 後再試一次。')
    } finally {
      setRegeneratingPlan(false)
    }
  }

  if (loading) {
    return <div className="max-w-5xl mx-auto px-6 py-8 text-center text-natural-500">載入中...</div>
  }

  if (!dashboard || !plan) {
    return <div className="max-w-5xl mx-auto px-6 py-8 text-center text-red-500">無法載入專案</div>
  }

  const { project, stakeholderPlan, interviewProgress, nextAction } = dashboard

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-center gap-3 mb-2">
        <button onClick={() => navigate('/projects')} className="text-natural-400 hover:text-natural-600">
          &larr;
        </button>
        <h1 className="text-2xl font-bold text-natural-800">{project.title}</h1>
      </div>
      {project.description && (
        <p className="text-natural-500 text-sm mb-6 ml-8 line-clamp-1">{project.description}</p>
      )}

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="p-4 bg-white rounded-xl border border-cream-200 shadow-natural">
          <div className="text-2xl font-bold text-sage-600">
            {Math.round(stakeholderPlan.progress_percentage)}%
          </div>
          <div className="text-sm text-natural-500">訪談計劃進度</div>
          <div className="mt-2 h-2 bg-cream-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-sage-400 rounded-full transition-all"
              style={{ width: `${stakeholderPlan.progress_percentage}%` }}
            />
          </div>
        </div>
        <div className="p-4 bg-white rounded-xl border border-cream-200 shadow-natural">
          <div className="text-2xl font-bold text-emerald-600">
            {interviewProgress.completed_sessions}
          </div>
          <div className="text-sm text-natural-500">已完成訪談</div>
          <div className="text-xs text-natural-400 mt-1">
            共 {interviewProgress.total_profiles} 位受訪者
          </div>
        </div>
        <div className="p-4 bg-white rounded-xl border border-cream-200 shadow-natural">
          <div className="text-2xl font-bold text-amber-600">
            {stakeholderPlan.completed_slots}/{stakeholderPlan.total_slots}
          </div>
          <div className="text-sm text-natural-500">角色覆蓋</div>
          <div className="text-xs text-natural-400 mt-1">
            必要角色完成數
          </div>
        </div>
      </div>

      {nextAction && (
        <div className="motion-reveal-in mb-8 p-4 bg-amber-50 border border-amber-200 rounded-xl shadow-natural">
          <div className="flex items-center gap-2">
            <span className="text-amber-600 font-medium">建議下一步</span>
          </div>
          <p className="text-natural-700 mt-1">{nextAction.reason}</p>
          <button
            onClick={() => setShowAddProfile(nextAction.role_category)}
            className="mt-2 px-3 py-1 text-sm bg-amber-100 text-amber-800 rounded hover:bg-amber-200 transition-colors"
          >
            安排「{nextAction.target_role}」訪談
          </button>
        </div>
      )}

      {stakeholderPlan.generation_source === 'fallback' && (
        <div className="motion-reveal-in mb-8 p-4 bg-amber-50 border border-amber-200 rounded-xl shadow-natural">
          <div className="font-medium text-amber-800">目前顯示暫用訪談角色</div>
          <p className="text-sm text-natural-700 mt-1">
            AI 訪談計畫未通過格式驗證，系統並未將通用角色標示為 AI 建議。
          </p>
          <button
            onClick={handleRegeneratePlan}
            disabled={regeneratingPlan}
            className="mt-2 px-3 py-1.5 text-sm bg-amber-100 text-amber-800 rounded hover:bg-amber-200 disabled:opacity-50"
          >
            {regeneratingPlan ? '重新生成中...' : '重新生成訪談計畫'}
          </button>
          {regenerateError && <p className="motion-status-in text-sm text-red-600 mt-2">{regenerateError}</p>}
        </div>
      )}

      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-natural-800">訪談計劃</h2>
            <p className="text-xs text-natural-400 mt-0.5">
              完整覆蓋 {stakeholderPlan.total_slots} 個角色，第一輪優先 {stakeholderPlan.first_wave_total} 個
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/projects/${projectId}/stakeholders`)}
              className="px-3 py-1.5 text-xs text-natural-600 border border-cream-300 rounded-lg bg-white hover:border-sage-200 hover:bg-sage-50 hover:text-sage-700"
            >
              管理受訪者
            </button>
            <button
              onClick={() => setShowAddSlot(true)}
              className="px-3 py-1.5 text-xs text-sage-600 border border-sage-200 rounded-lg hover:bg-sage-50"
            >
              + 新增角色
            </button>
          </div>
        </div>

        {slotActionError && (
          <div role="alert" className="motion-status-in mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            {slotActionError}
          </div>
        )}

        {showAddSlot && (
          <div className="motion-reveal-in mb-5 space-y-4 rounded-xl border border-cream-300 bg-cream-50 p-5 shadow-natural">
            <div className="flex items-start justify-between gap-4 border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-natural-800">新增訪談角色</h3>
                <p className="mt-0.5 text-xs text-natural-400">建立後會以相同欄位顯示在訪談計劃中</p>
              </div>
              <button
                type="button"
                onClick={closeAddSlotForm}
                className="rounded-lg p-1 text-natural-400 hover:bg-cream-100 hover:text-natural-600"
                aria-label="關閉新增角色表單"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex flex-col gap-3 rounded-xl border border-cream-200 bg-cream-100/60 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-xs font-medium text-natural-600">智慧填寫</div>
                <p className="mt-0.5 text-[11px] text-natural-400">可直接口述完整內容，或先填角色名稱再請 AI 優化</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={isRecordingSlot ? stopSlotRecording : startSlotRecording}
                  disabled={isProcessingSlotVoice || isRefiningSlot}
                  className={`inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg border px-3.5 text-xs font-medium transition-all sm:flex-none ${
                    isRecordingSlot
                      ? 'border-wood-200 bg-wood-50 text-wood-500 hover:bg-wood-100'
                      : 'border-cream-300 bg-white text-natural-600 hover:border-sage-200 hover:bg-sage-50 hover:text-sage-600'
                  } disabled:cursor-not-allowed disabled:border-cream-200 disabled:bg-cream-100 disabled:text-natural-400`}
                >
                  {isProcessingSlotVoice ? (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cream-300 border-t-sage-400" aria-hidden="true" />
                  ) : isRecordingSlot ? (
                    <span className="h-2 w-2 animate-pulse rounded-sm bg-wood-400" aria-hidden="true" />
                  ) : (
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18.5a6.5 6.5 0 006.5-6.5m-13 0a6.5 6.5 0 006.5 6.5m0 0V22m-4 0h8M12 15a3 3 0 003-3V5a3 3 0 00-6 0v7a3 3 0 003 3z" />
                    </svg>
                  )}
                  {isProcessingSlotVoice
                    ? '語音分析中…'
                    : isRecordingSlot
                      ? '停止並填入'
                      : '口說填入'}
                </button>
                <button
                  type="button"
                  onClick={handleRefineSlotDraft}
                  disabled={!newSlotLabel.trim() || isRecordingSlot || isProcessingSlotVoice || isRefiningSlot}
                  className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg bg-sage-400 px-3.5 text-xs font-medium text-white shadow-natural transition-colors hover:bg-sage-500 disabled:cursor-not-allowed disabled:bg-cream-300 disabled:text-natural-400 disabled:shadow-none sm:flex-none"
                >
                  {isRefiningSlot ? (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden="true" />
                  ) : (
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3l1.2 3.3L16.5 7.5l-3.3 1.2L12 12l-1.2-3.3-3.3-1.2 3.3-1.2L12 3zm6 9l.9 2.1L21 15l-2.1.9L18 18l-.9-2.1L15 15l2.1-.9L18 12zM6 13l.9 2.1L9 16l-2.1.9L6 19l-.9-2.1L3 16l2.1-.9L6 13z" />
                    </svg>
                  )}
                  {isRefiningSlot ? 'AI 優化中…' : 'AI 補充／優化'}
                </button>
              </div>
            </div>

            {(slotAssistError || slotAssistMessage) && (
              <div
                role={slotAssistError ? 'alert' : 'status'}
                aria-live="polite"
                className={`motion-status-in rounded-lg border px-3 py-2 text-xs ${
                  slotAssistError
                    ? 'border-red-200 bg-red-50 text-red-600'
                    : 'border-sage-200 bg-sage-50 text-sage-700'
                }`}
              >
                {slotAssistError || slotAssistMessage}
              </div>
            )}

            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_12rem]">
              <div>
                <label htmlFor="new-slot-label" className="text-xs font-medium text-natural-600">角色名稱</label>
                <input
                  id="new-slot-label"
                  type="text"
                  value={newSlotLabel}
                  onChange={e => setNewSlotLabel(e.target.value)}
                  placeholder="例：掛號櫃台人員"
                  className="mt-1 w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
                />
              </div>
              <div>
                <label htmlFor="new-slot-category" className="text-xs font-medium text-natural-600">角色類型</label>
                <select
                  id="new-slot-category"
                  value={newSlotCategory}
                  onChange={e => setNewSlotCategory(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
                >
                  {STAKEHOLDER_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_10rem_minmax(0,1fr)]">
              <div>
                <label htmlFor="new-slot-priority" className="text-xs font-medium text-natural-600">重要性</label>
                <select
                  id="new-slot-priority"
                  value={newSlotPriority}
                  onChange={e => setNewSlotPriority(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
                >
                  <option value="required">必要角色</option>
                  <option value="recommended">建議角色</option>
                  <option value="optional">可選角色</option>
                </select>
              </div>
              <div>
                <label htmlFor="new-slot-min-interviews" className="text-xs font-medium text-natural-600">最低訪談場次</label>
                <input
                  id="new-slot-min-interviews"
                  type="number"
                  min={1}
                  max={20}
                  value={newSlotMinInterviews}
                  onChange={e => setNewSlotMinInterviews(Math.max(1, Number(e.target.value) || 1))}
                  className="mt-1 w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
                />
              </div>
              <label className="mt-5 flex cursor-pointer items-center gap-3 rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm text-natural-600 hover:bg-cream-100 sm:col-span-2 lg:col-span-1">
                <input
                  type="checkbox"
                  checked={newSlotFirstWave}
                  onChange={e => setNewSlotFirstWave(e.target.checked)}
                  className="h-4 w-4 rounded border-cream-400 text-sage-500 focus:ring-sage-300"
                />
                <span>
                  <span className="block font-medium">第一輪優先</span>
                  <span className="block text-[11px] text-natural-400">列入首輪訪談</span>
                </span>
              </label>
            </div>

            <div>
              <label htmlFor="new-slot-rationale" className="text-xs font-medium text-natural-600">訪談目的</label>
              <textarea
                id="new-slot-rationale"
                value={newSlotRationale}
                onChange={e => setNewSlotRationale(e.target.value)}
                rows={2}
                placeholder="說明為什麼需要訪談這個角色，以及預期補足哪些資訊缺口"
                className="mt-1 w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm leading-6 focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
              />
            </div>

            <div>
              <label htmlFor="new-slot-contributions" className="text-xs font-medium text-natural-600">預期取得的資訊</label>
              <textarea
                id="new-slot-contributions"
                value={newSlotExpectedContributions}
                onChange={e => setNewSlotExpectedContributions(e.target.value)}
                rows={2}
                placeholder="例：實際作業流程, 常見例外, 操作限制（使用逗號分隔）"
                className="mt-1 w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm leading-6 focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
              />
            </div>

            <div>
              <label htmlFor="new-slot-questions" className="text-xs font-medium text-natural-600">關鍵問題</label>
              <textarea
                id="new-slot-questions"
                value={newSlotKeyQuestions}
                onChange={e => setNewSlotKeyQuestions(e.target.value)}
                rows={4}
                placeholder={'每行輸入一個問題\n例：上次處理這件事時，最花時間的是哪一步？'}
                className="mt-1 w-full rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm leading-6 focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
              />
            </div>

            <div className="flex justify-end gap-2 border-t border-cream-200 pt-4">
              <button
                type="button"
                onClick={closeAddSlotForm}
                className="rounded-lg border border-cream-300 bg-white px-4 py-2 text-xs font-medium text-natural-500 hover:bg-cream-100"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleAddSlot}
                disabled={!newSlotLabel.trim() || isRecordingSlot || isProcessingSlotVoice || isRefiningSlot}
                className="rounded-lg bg-sage-400 px-4 py-2 text-xs font-medium text-white hover:bg-sage-500 disabled:cursor-not-allowed disabled:bg-cream-300"
              >
                新增角色
              </button>
            </div>
          </div>
        )}

        <SlotList
          slots={plan.slots}
          profiles={plan.profiles}
          projectId={projectId!}
          guideStatuses={guideStatuses}
          editingSlot={editingSlot}
          editForm={editForm}
          setEditingSlot={setEditingSlot}
          setEditForm={setEditForm}
          onMoveSlot={handleMoveSlot}
          onSkipSlot={handleSkipSlot}
          onUnskipSlot={handleUnskipSlot}
          onDeleteSlot={handleDeleteSlot}
          onUpdateSlot={handleUpdateSlot}
          onAddProfile={(slotId) => setShowAddProfile(slotId)}
          onDeleteProfile={handleDeleteProfile}
          onReassignProfile={handleReassignProfile}
          onShowGuideSettings={(profileId) => setShowGuideSettings(profileId)}
        />
      </div>

      {showAddProfile && projectId && (
        <AddProfileModal
          slotId={showAddProfile}
          projectId={projectId}
          onClose={() => setShowAddProfile(null)}
          onAdd={() => {
            setShowAddProfile(null)
            loadData()
          }}
        />
      )}

      {showStartInterview && plan && projectId && (
        <StartInterviewModal
          plan={plan}
          projectId={projectId}
          guideStatuses={guideStatuses}
          onClose={() => setShowStartInterview(false)}
          onGuideGenerated={handleGuideGenerated}
        />
      )}

      {showGuideSettings && projectId && (
        <GuideSettingsModal
          profileId={showGuideSettings}
          projectId={projectId}
          onClose={() => setShowGuideSettings(null)}
          onGenerated={handleGuideGenerated}
        />
      )}

      <div className="mb-8">
        <h2 className="text-lg font-semibold text-natural-800 mb-4">快速操作</h2>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => navigate(`/projects/${projectId}/evidence-matrix`)}
            className="p-4 bg-white rounded-xl border border-cream-200 hover:border-sage-300 hover:shadow-natural transition-all text-left"
          >
            <div className="text-sm font-medium text-natural-800">需求證據矩陣</div>
            <div className="text-xs text-natural-500 mt-1">查看跨訪談需求整合結果</div>
          </button>
          <button
            onClick={() => navigate(`/projects/${projectId}/readiness`)}
            className="p-4 bg-white rounded-xl border border-cream-200 hover:border-sage-300 hover:shadow-natural transition-all text-left"
          >
            <div className="text-sm font-medium text-natural-800">BRD 準備度檢查</div>
            <div className="text-xs text-natural-500 mt-1">評估是否可以生成 BRD</div>
          </button>
        </div>
      </div>
    </div>
  )
}
