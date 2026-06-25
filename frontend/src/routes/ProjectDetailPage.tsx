import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '@/api/client'
import {
  getProjectDashboard,
  getStakeholderPlan,
  createStakeholder,
  deleteStakeholder,
  skipStakeholderSlot,
  unskipStakeholderSlot,
  updateStakeholderSlot,
  createStakeholderSlot,
  deleteStakeholderSlot,
  reorderStakeholderSlots,
  generateInterviewGuide,
  getInterviewGuide,
  type ProjectDashboard,
  type StakeholderPlan,
  type InterviewGuide,
  type InterviewGuideOptions,
} from '@/api/projects'

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
  { value: 'other', label: '其他' },
]

function SlotStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    unassigned: { label: '未安排', color: 'bg-red-50 text-red-700' },
    partially_assigned: { label: '部分安排', color: 'bg-yellow-50 text-yellow-700' },
    assigned: { label: '已安排', color: 'bg-blue-50 text-blue-700' },
    interviewing: { label: '訪談中', color: 'bg-sage-50 text-sage-700' },
    completed: { label: '已完成', color: 'bg-green-50 text-green-700' },
    skipped: { label: '已跳過', color: 'bg-cream-100 text-natural-500' },
  }
  const info = map[status] || { label: status, color: 'bg-cream-100 text-natural-700' }
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${info.color}`}>
      {info.label}
    </span>
  )
}

function PriorityBadge({ priority }: { priority: string }) {
  const map: Record<string, { label: string; color: string }> = {
    required: { label: '必要', color: 'bg-red-50 text-red-600' },
    recommended: { label: '建議', color: 'bg-yellow-50 text-yellow-600' },
    optional: { label: '可選', color: 'bg-cream-50 text-natural-500' },
  }
  const info = map[priority] || { label: priority, color: 'bg-cream-50 text-natural-500' }
  return (
    <span className={`px-2 py-0.5 text-xs rounded ${info.color}`}>
      {info.label}
    </span>
  )
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<ProjectDashboard | null>(null)
  const [plan, setPlan] = useState<StakeholderPlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAddProfile, setShowAddProfile] = useState<string | null>(null)
  const [showStartInterview, setShowStartInterview] = useState(false)
  const [loadingPreps, setLoadingPreps] = useState(false)
  const [guideStatuses, setGuideStatuses] = useState<Record<string, InterviewGuide | null>>({})
  const [editingSlot, setEditingSlot] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ rationale: '', expectedContributions: '', keyQuestions: '', priority: 'required' })
  const [generatingGuide, setGeneratingGuide] = useState<string | null>(null)
  const [showGuideSettings, setShowGuideSettings] = useState<string | null>(null)
  const [guideOpts, setGuideOpts] = useState<InterviewGuideOptions>({ duration_minutes: 30 })

  // New profile form
  const [profileName, setProfileName] = useState('')
  const [profileRole, setProfileRole] = useState('')
  const [profileType, setProfileType] = useState('business')
  const [profileDept, setProfileDept] = useState('')
  const [profileExpertise, setProfileExpertise] = useState('')
  const [profileBoundaries, setProfileBoundaries] = useState('')

  const loadData = useCallback(async () => {
    if (!projectId) return
    try {
      setLoading(true)
      const [dashData, planData] = await Promise.all([
        getProjectDashboard(projectId),
        getStakeholderPlan(projectId),
      ])
      setDashboard(dashData)
      setPlan(planData)

      // Load interview guide statuses for all profiles
      const statuses: Record<string, InterviewGuide | null> = {}
      for (const profile of planData.profiles) {
        try {
          const guide = await getInterviewGuide(projectId, profile.id)
          statuses[profile.id] = guide
        } catch {
          statuses[profile.id] = null
        }
      }
      setGuideStatuses(statuses)
    } catch (err) {
      console.error('Failed to load project:', err)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { loadData() }, [loadData])

  const handleAddProfile = async (slotId?: string) => {
    if (!projectId || !profileName.trim()) return
    try {
      await createStakeholder(projectId, {
        slot_id: slotId || undefined,
        name: profileName.trim(),
        role_title: profileRole.trim() || undefined,
        department: profileDept.trim() || undefined,
        stakeholder_type: profileType,
        expertise_tags: profileExpertise.split(',').map(s => s.trim()).filter(Boolean),
        knowledge_boundaries: profileBoundaries.split(',').map(s => s.trim()).filter(Boolean),
      })
      setShowAddProfile(null)
      setProfileName('')
      setProfileRole('')
      setProfileType('business')
      setProfileDept('')
      setProfileExpertise('')
      setProfileBoundaries('')
      loadData()
    } catch (err) {
      console.error('Failed to create stakeholder:', err)
    }
  }

  const handleSkipSlot = async (slotId: string) => {
    try {
      await skipStakeholderSlot(slotId)
      loadData()
    } catch (err) {
      console.error('Failed to skip slot:', err)
    }
  }

  const handleUnskipSlot = async (slotId: string) => {
    try {
      await unskipStakeholderSlot(slotId)
      loadData()
    } catch (err) {
      console.error('Failed to unskip slot:', err)
    }
  }

  const handleMoveSlot = async (slotId: string, direction: 'up' | 'down') => {
    if (!plan) return
    const ids = plan.slots.map(s => s.id)
    const idx = ids.indexOf(slotId)
    if (idx < 0) return
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1
    if (targetIdx < 0 || targetIdx >= ids.length) return
    ;[ids[idx], ids[targetIdx]] = [ids[targetIdx], ids[idx]]
    try {
      await reorderStakeholderSlots(ids)
      loadData()
    } catch (err) {
      console.error('Failed to reorder slots:', err)
    }
  }

  const handleDeleteSlot = async (slotId: string) => {
    if (!confirm('確定要刪除此角色？')) return
    try {
      await deleteStakeholderSlot(slotId)
      loadData()
    } catch (err) {
      console.error('Failed to delete slot:', err)
    }
  }

  const [showAddSlot, setShowAddSlot] = useState(false)
  const [newSlotLabel, setNewSlotLabel] = useState('')
  const [newSlotCategory, setNewSlotCategory] = useState('business')
  const [newSlotRationale, setNewSlotRationale] = useState('')

  const handleAddSlot = async () => {
    if (!newSlotLabel.trim() || !projectId) return
    try {
      await createStakeholderSlot(projectId, {
        role_category: newSlotCategory,
        role_label: newSlotLabel.trim(),
        rationale: newSlotRationale.trim() || undefined,
        priority: 'required',
      })
      setShowAddSlot(false)
      setNewSlotLabel('')
      setNewSlotCategory('business')
      setNewSlotRationale('')
      loadData()
    } catch (err) {
      console.error('Failed to add slot:', err)
    }
  }

  const handleDeleteProfile = async (profileId: string) => {
    if (!confirm('確定要移除此受訪者？')) return
    try {
      await deleteStakeholder(profileId)
      loadData()
    } catch (err) {
      console.error('Failed to delete stakeholder:', err)
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
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <button onClick={() => navigate('/projects')} className="text-natural-400 hover:text-natural-600">
          &larr;
        </button>
        <h1 className="text-2xl font-bold text-natural-800">{project.title}</h1>
      </div>
      {project.description && (
        <p className="text-natural-500 text-sm mb-6 ml-8 line-clamp-1">{project.description}</p>
      )}

      {/* Progress Overview */}
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

      {/* Next Action Suggestion */}
      {nextAction && (
        <div className="mb-8 p-4 bg-amber-50 border border-amber-200 rounded-xl shadow-natural">
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

      {/* Stakeholder Plan — Hierarchical View */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-natural-800">訪談計劃</h2>
          <button
            onClick={() => setShowAddSlot(true)}
            className="px-3 py-1.5 text-xs text-sage-600 border border-sage-200 rounded-lg hover:bg-sage-50"
          >
            + 新增角色
          </button>
        </div>

        {/* Add slot form */}
        {showAddSlot && (
          <div className="mb-4 p-4 bg-cream-50 rounded-xl border border-cream-200 space-y-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs text-natural-500">角色名稱</label>
                <input
                  type="text"
                  value={newSlotLabel}
                  onChange={e => setNewSlotLabel(e.target.value)}
                  placeholder="例：工程主管"
                  className="w-full mt-0.5 px-3 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                />
              </div>
              <div className="w-32">
                <label className="text-xs text-natural-500">類別</label>
                <select
                  value={newSlotCategory}
                  onChange={e => setNewSlotCategory(e.target.value)}
                  className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                >
                  {STAKEHOLDER_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-natural-500">訪談目標（選填）</label>
              <input
                type="text"
                value={newSlotRationale}
                onChange={e => setNewSlotRationale(e.target.value)}
                placeholder="為什麼需要訪談這個角色？"
                className="w-full mt-0.5 px-3 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAddSlot}
                disabled={!newSlotLabel.trim()}
                className="px-4 py-1.5 text-xs bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:bg-cream-300 disabled:cursor-not-allowed"
              >
                新增
              </button>
              <button
                onClick={() => setShowAddSlot(false)}
                className="px-4 py-1.5 text-xs text-natural-500 bg-cream-100 rounded-lg hover:bg-cream-200"
              >
                取消
              </button>
            </div>
          </div>
        )}

        <div className="space-y-6">
          {plan.slots.map(slot => {
            const slotProfiles = plan.profiles.filter(p => p.slotId === slot.id)

            return (
              <div key={slot.id}>
                {/* Slot Header — Role Section */}
                <div className="flex items-start gap-3 mb-3">
                  {/* Order controls + indicator */}
                  <div className="flex flex-col items-center gap-0.5 flex-shrink-0 mt-0.5">
                    <button
                      onClick={() => handleMoveSlot(slot.id, 'up')}
                      disabled={plan.slots.indexOf(slot) === 0}
                      className="text-natural-400 hover:text-natural-600 disabled:opacity-20 disabled:cursor-not-allowed p-0"
                      title="上移"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                      </svg>
                    </button>
                    <span className="text-[10px] text-natural-400 leading-none">{plan.slots.indexOf(slot) + 1}</span>
                    <button
                      onClick={() => handleMoveSlot(slot.id, 'down')}
                      disabled={plan.slots.indexOf(slot) === plan.slots.length - 1}
                      className="text-natural-400 hover:text-natural-600 disabled:opacity-20 disabled:cursor-not-allowed p-0"
                      title="下移"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                  </div>
                  <div className={`mt-2.5 w-2 h-2 rounded-full flex-shrink-0 ${
                    slot.status === 'completed' ? 'bg-green-500' :
                    slot.status === 'skipped' ? 'bg-cream-300' :
                    slot.status === 'unassigned' ? 'bg-red-400' :
                    'bg-sage-400'
                  }`} />

                  <div className="flex-1 min-w-0">
                    {/* Role name + badges */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-base font-semibold text-natural-800">{slot.roleLabel}</h3>
                      <PriorityBadge priority={slot.priority} />
                      <SlotStatusBadge status={slot.status} />
                      <span className="text-xs text-natural-400">
                        {slot.interviewsDone}/{slot.minInterviews} 場訪談
                      </span>
                      {editingSlot !== slot.id && (
                        <span className="inline-flex items-center gap-1 ml-1">
                          <button
                            onClick={() => {
                              setEditingSlot(slot.id)
                              setEditForm({
                                rationale: slot.rationale || '',
                                expectedContributions: slot.expectedContributions.join(', '),
                                keyQuestions: slot.keyQuestionsToCover.join('\n'),
                                priority: slot.priority,
                              })
                            }}
                            className="text-natural-400 hover:text-sage-500 p-0.5"
                            title="編輯"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                          </button>
                          {slot.status === 'skipped' ? (
                            <button
                              onClick={() => handleUnskipSlot(slot.id)}
                              className="text-natural-400 hover:text-green-500 p-0.5"
                              title="復原此角色"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a5 5 0 015 5v2M3 10l4-4M3 10l4 4" />
                              </svg>
                            </button>
                          ) : slot.status !== 'completed' && (
                            <button
                              onClick={() => handleSkipSlot(slot.id)}
                              className="text-natural-400 hover:text-amber-500 p-0.5"
                              title="跳過此角色"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                              </svg>
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteSlot(slot.id)}
                            className="text-natural-400 hover:text-red-500 p-0.5"
                            title="刪除角色"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </span>
                      )}
                    </div>

                    {editingSlot === slot.id ? (
                      /* Inline edit form */
                      <div className="mt-2 space-y-2 p-3 bg-cream-50 rounded-lg">
                        <div className="flex gap-3">
                          <div className="flex-1">
                            <label className="text-xs text-natural-500">訪談目標</label>
                            <input
                              type="text"
                              value={editForm.rationale}
                              onChange={e => setEditForm(f => ({ ...f, rationale: e.target.value }))}
                              className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                            />
                          </div>
                          <div className="w-28">
                            <label className="text-xs text-natural-500">重要性</label>
                            <select
                              value={editForm.priority}
                              onChange={e => setEditForm(f => ({ ...f, priority: e.target.value }))}
                              className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                            >
                              <option value="required">必要</option>
                              <option value="recommended">建議</option>
                              <option value="optional">可選</option>
                            </select>
                          </div>
                        </div>
                        <div>
                          <label className="text-xs text-natural-500">預期提供（逗號分隔）</label>
                          <input
                            type="text"
                            value={editForm.expectedContributions}
                            onChange={e => setEditForm(f => ({ ...f, expectedContributions: e.target.value }))}
                            className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-natural-500">關鍵問題（每行一個）</label>
                          <textarea
                            value={editForm.keyQuestions}
                            onChange={e => setEditForm(f => ({ ...f, keyQuestions: e.target.value }))}
                            rows={3}
                            className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={async () => {
                              try {
                                await updateStakeholderSlot(slot.id, {
                                  rationale: editForm.rationale || undefined,
                                  expected_contributions: editForm.expectedContributions.split(',').map(s => s.trim()).filter(Boolean),
                                  key_questions_to_cover: editForm.keyQuestions.split('\n').map(s => s.trim()).filter(Boolean),
                                  priority: editForm.priority,
                                })
                                setEditingSlot(null)
                                loadData()
                              } catch (err) {
                                console.error('Failed to update slot:', err)
                              }
                            }}
                            className="px-3 py-1 text-xs bg-sage-400 text-white rounded-lg hover:bg-sage-500"
                          >
                            儲存
                          </button>
                          <button
                            onClick={() => setEditingSlot(null)}
                            className="px-3 py-1 text-xs text-natural-500 bg-cream-100 rounded-lg hover:bg-cream-200"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        {/* Rationale — interview objective */}
                        {slot.rationale && (
                          <p className="text-sm text-natural-600 mt-1">{slot.rationale}</p>
                        )}

                        {/* Expected contributions */}
                        {slot.expectedContributions.length > 0 && (
                          <div className="mt-2">
                            <span className="text-xs text-natural-400">預期提供：</span>
                            <div className="flex flex-wrap gap-1.5 mt-1">
                              {slot.expectedContributions.map((c, i) => (
                                <span key={i} className="px-2 py-0.5 text-xs bg-sage-50 text-sage-600 rounded">
                                  {c}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Key questions */}
                        {slot.keyQuestionsToCover.length > 0 && (
                          <div className="mt-2">
                            <span className="text-xs text-natural-400">關鍵問題：</span>
                            <ul className="mt-1 space-y-0.5">
                              {slot.keyQuestionsToCover.map((q, i) => (
                                <li key={i} className="text-xs text-natural-600 flex items-start gap-1.5">
                                  <span className="text-cream-400 mt-0.5">•</span>
                                  {q}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    )}

                    {/* Action buttons for the slot */}
                    {editingSlot !== slot.id && slot.status !== 'completed' && slot.status !== 'skipped' && (
                      <div className="flex gap-2 mt-3">
                        <button
                          onClick={() => setShowAddProfile(slot.id)}
                          className="px-2.5 py-1 text-xs bg-sage-50 text-sage-700 rounded-lg hover:bg-sage-100"
                        >
                          + 指派受訪者
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Profile Cards — nested under the slot */}
                {slotProfiles.length > 0 && (
                  <div className="ml-5 pl-4 border-l-2 border-cream-200 space-y-2">
                    {slotProfiles.map(profile => {
                      const guide = guideStatuses[profile.id]
                      const guideReady = guide && guide.card_count > 0
                      return (
                        <div key={profile.id} className="p-3 bg-white rounded-xl border border-cream-200 hover:border-cream-300 shadow-natural transition-colors">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                                profile.status === 'interviewed' ? 'bg-green-50 text-green-700' :
                                'bg-cream-100 text-natural-600'
                              }`}>
                                {profile.name.charAt(0)}
                              </div>
                              <div>
                                <span className="text-sm font-medium text-natural-700">{profile.name}</span>
                                {profile.roleTitle && (
                                  <span className="text-xs text-natural-400 ml-2">{profile.roleTitle}</span>
                                )}
                              </div>
                              <span className={`px-1.5 py-0.5 text-xs rounded ${
                                profile.status === 'interviewed' ? 'bg-green-50 text-green-700' :
                                profile.status === 'unavailable' ? 'bg-red-50 text-red-600' :
                                'bg-cream-100 text-natural-500'
                              }`}>
                                {profile.status === 'interviewed' ? '已訪' :
                                 profile.status === 'unavailable' ? '無法' : '待訪'}
                              </span>
                              {guideReady && (
                                <span className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-600 rounded">
                                  {guide.card_count} 張卡片
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-1.5">
                              {guideReady ? (
                                <>
                                  <button
                                    onClick={() => navigate(`/editor/${guide.document_id}`)}
                                    className="px-2 py-1 text-xs text-blue-700 hover:bg-blue-50 rounded"
                                  >
                                    編輯大綱
                                  </button>
                                  {profile.interviewCount > 0 && (
                                    <button
                                      onClick={() => {
                                        // Find the latest session for this profile and navigate to its memo
                                        apiClient.get('/api/interview-sessions/', { params: { projectId, limit: 50 } })
                                          .then(res => {
                                            const sessions = res.data.sessions || []
                                            const profileSession = sessions.find((s: Record<string, unknown>) => s.stakeholderProfileId === profile.id)
                                            if (profileSession) navigate(`/sessions/${profileSession.id}/insight-memo`)
                                          })
                                      }}
                                      className="px-2 py-1 text-xs text-natural-600 hover:bg-cream-100 rounded"
                                    >
                                      訪談紀錄
                                    </button>
                                  )}
                                  <button
                                    onClick={() => navigate(`/interview/${guide.document_id}?projectId=${projectId}&stakeholderId=${profile.id}`)}
                                    className="px-2.5 py-1 text-xs bg-sage-400 text-white rounded-lg hover:bg-sage-500"
                                  >
                                    開始訪談
                                  </button>
                                </>
                              ) : (
                                <button
                                  onClick={() => {
                                    setShowGuideSettings(profile.id)
                                    setGuideOpts({ duration_minutes: 30 })
                                  }}
                                  disabled={generatingGuide === profile.id}
                                  className="px-2.5 py-1 text-xs bg-sage-50 text-sage-700 rounded-lg hover:bg-sage-100 disabled:opacity-50"
                                >
                                  {generatingGuide === profile.id ? '生成中...' : guide ? '重新生成大綱' : '生成訪談大綱'}
                                </button>
                              )}
                              <button
                                onClick={() => handleDeleteProfile(profile.id)}
                                className="p-1 text-natural-400 hover:text-red-400"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                          </div>
                          {profile.department && (
                            <div className="text-xs text-natural-400 mt-1 ml-8">{profile.department}</div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}

                {/* Divider between slots */}
                <div className="mt-4 border-b border-cream-200" />
              </div>
            )
          })}

        </div>
      </div>

      {/* Add Profile Form Modal */}
      {showAddProfile && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowAddProfile(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-natural" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-natural-800 mb-4">新增受訪者</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">姓名 *</label>
                <input
                  type="text"
                  value={profileName}
                  onChange={e => setProfileName(e.target.value)}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                  placeholder="受訪者姓名"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">職稱</label>
                <input
                  type="text"
                  value={profileRole}
                  onChange={e => setProfileRole(e.target.value)}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                  placeholder="例：資深業務經理"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">部門</label>
                <input
                  type="text"
                  value={profileDept}
                  onChange={e => setProfileDept(e.target.value)}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                  placeholder="例：業務部"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">角色類型</label>
                <select
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
                <label className="block text-sm font-medium text-natural-700 mb-1">
                  專長領域（逗號分隔）
                </label>
                <input
                  type="text"
                  value={profileExpertise}
                  onChange={e => setProfileExpertise(e.target.value)}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                  placeholder="sales_process, customer_pain_points, pricing"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">
                  不熟悉領域（逗號分隔）
                </label>
                <input
                  type="text"
                  value={profileBoundaries}
                  onChange={e => setProfileBoundaries(e.target.value)}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                  placeholder="technical_architecture, database, deployment"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button
                onClick={() => handleAddProfile(showAddProfile!)}
                disabled={!profileName.trim()}
                className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:opacity-50"
              >
                新增
              </button>
              <button
                onClick={() => setShowAddProfile(null)}
                className="px-4 py-2 bg-cream-100 text-natural-700 rounded-lg hover:bg-cream-200"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Start Interview Modal */}
      {showStartInterview && plan && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowStartInterview(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-natural" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-natural-800 mb-2">開始新訪談</h3>
            <p className="text-sm text-natural-500 mb-4">選擇受訪者後開始訪談。若尚未產生訪談大綱，將先自動產生。</p>

            {/* Step 1: Select stakeholder */}
            {plan.profiles.filter(p => p.status !== 'unavailable').length === 0 ? (
              <div className="text-sm text-natural-500 py-4 text-center">
                尚無可用受訪者，請先新增受訪者。
              </div>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {plan.profiles.filter(p => p.status !== 'unavailable').map(profile => {
                  const guide = guideStatuses[profile.id]
                  return (
                    <button
                      key={profile.id}
                      onClick={async () => {
                        try {
                          setLoadingPreps(true)
                          let finalGuide = guide
                          // If no guide exists, generate it first
                          if (!finalGuide) {
                            finalGuide = await generateInterviewGuide(projectId!, profile.id)
                            setGuideStatuses(prev => ({ ...prev, [profile.id]: finalGuide! }))
                          }
                          setShowStartInterview(false)
                          navigate(`/interview/${finalGuide.document_id}?projectId=${projectId}&stakeholderId=${profile.id}`)
                        } catch (err) {
                          console.error('Failed to start interview:', err)
                          alert('訪談大綱產生失敗，請稍後再試')
                        } finally {
                          setLoadingPreps(false)
                        }
                      }}
                      disabled={loadingPreps}
                      className="w-full p-3 text-left bg-cream-50 rounded-xl hover:bg-sage-50 hover:border-sage-200 border border-cream-200 transition-colors disabled:opacity-50"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-sm font-medium text-natural-700">{profile.name}</span>
                          {profile.roleTitle && (
                            <span className="text-xs text-natural-400 ml-2">{profile.roleTitle}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 text-xs rounded ${
                            profile.status === 'interviewed' ? 'bg-green-50 text-green-700' : 'bg-cream-100 text-natural-600'
                          }`}>
                            {profile.status === 'interviewed' ? '已訪' : '待訪'}
                          </span>
                          {guide && (
                            <span className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-700 rounded">
                              {guide.card_count} 卡
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-xs text-natural-400 mt-0.5">
                        {profile.stakeholderType} {profile.department ? `· ${profile.department}` : ''}
                        {!guide && <span className="text-amber-500 ml-2">(將自動產生大綱)</span>}
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setShowStartInterview(false)}
                className="px-3 py-2 text-sm text-natural-500 bg-cream-100 rounded-lg hover:bg-cream-200 ml-auto"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Guide Generation Settings Modal */}
      {showGuideSettings && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowGuideSettings(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-natural" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-natural-800 mb-1">訪談大綱設定</h3>
            <p className="text-sm text-natural-500 mb-4">調整後按「生成」，AI 會根據設定產生訪談問題卡片</p>

            <div className="space-y-4">
              {/* Duration */}
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">預計訪談時長</label>
                <div className="flex gap-2">
                  {[15, 30, 45, 60].map(min => (
                    <button
                      key={min}
                      onClick={() => setGuideOpts(o => ({ ...o, duration_minutes: min }))}
                      className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                        guideOpts.duration_minutes === min
                          ? 'bg-sage-50 border-sage-300 text-sage-700'
                          : 'border-cream-200 text-natural-600 hover:bg-cream-50'
                      }`}
                    >
                      {min} 分鐘
                    </button>
                  ))}
                </div>
              </div>

              {/* Interview Purpose */}
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">這次訪談目的</label>
                <input
                  type="text"
                  value={guideOpts.interview_purpose || ''}
                  onChange={e => setGuideOpts(o => ({ ...o, interview_purpose: e.target.value }))}
                  placeholder="例：了解現有銷售流程的痛點"
                  className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                />
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {['初次探索', '深入追問', '驗證需求', '確認設計', '了解現況'].map(tag => (
                    <button
                      key={tag}
                      onClick={() => setGuideOpts(o => ({ ...o, interview_purpose: tag }))}
                      className="px-2 py-0.5 text-xs bg-cream-100 text-natural-600 rounded hover:bg-sage-50 hover:text-sage-600"
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>

              {/* Focus Topics */}
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">聚焦主題</label>
                <input
                  type="text"
                  value={guideOpts.focus_topics || ''}
                  onChange={e => setGuideOpts(o => ({ ...o, focus_topics: e.target.value }))}
                  placeholder="例：庫存管理流程、客訴處理"
                  className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                />
              </div>

              {/* Exclude Topics */}
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">排除主題（不要問）</label>
                <input
                  type="text"
                  value={guideOpts.exclude_topics || ''}
                  onChange={e => setGuideOpts(o => ({ ...o, exclude_topics: e.target.value }))}
                  placeholder="例：技術架構、資料庫設計"
                  className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
                />
              </div>

              {/* Interview Style */}
              <div>
                <label className="block text-sm font-medium text-natural-700 mb-1">訪談風格</label>
                <div className="flex gap-2">
                  {[
                    { value: 'exploratory', label: '探索型', desc: '開放、廣泛' },
                    { value: 'structured', label: '結構化', desc: '精確、逐項' },
                    { value: 'validation', label: '驗證型', desc: '確認假設' },
                  ].map(style => (
                    <button
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
            </div>

            {/* Actions */}
            <div className="flex gap-3 mt-6">
              <button
                onClick={async () => {
                  const profileId = showGuideSettings
                  setShowGuideSettings(null)
                  try {
                    setGeneratingGuide(profileId)
                    const cleanOpts: InterviewGuideOptions = { duration_minutes: guideOpts.duration_minutes }
                    if (guideOpts.interview_purpose) cleanOpts.interview_purpose = guideOpts.interview_purpose
                    if (guideOpts.focus_topics) cleanOpts.focus_topics = guideOpts.focus_topics
                    if (guideOpts.exclude_topics) cleanOpts.exclude_topics = guideOpts.exclude_topics
                    if (guideOpts.interview_style) cleanOpts.interview_style = guideOpts.interview_style
                    const result = await generateInterviewGuide(projectId!, profileId, cleanOpts)
                    setGuideStatuses(prev => ({ ...prev, [profileId]: result }))
                  } catch (err) {
                    console.error('Failed to generate guide:', err)
                    alert('生成失敗，請稍後再試')
                  } finally {
                    setGeneratingGuide(null)
                  }
                }}
                className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 text-sm font-medium"
              >
                生成訪談大綱
              </button>
              <button
                onClick={() => setShowGuideSettings(null)}
                className="px-4 py-2 bg-cream-100 text-natural-700 rounded-lg hover:bg-cream-200 text-sm"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
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
