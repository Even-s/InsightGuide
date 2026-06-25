import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { InterviewGuide } from '@/api/projects'
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
  { value: 'other', label: '其他' },
]

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { dashboard, plan, loading, guideStatuses, setGuideStatuses, loadData } = useProjectData(projectId)
  const [showAddProfile, setShowAddProfile] = useState<string | null>(null)
  const [showStartInterview, setShowStartInterview] = useState(false)
  const [showGuideSettings, setShowGuideSettings] = useState<string | null>(null)

  const {
    editingSlot,
    setEditingSlot,
    editForm,
    setEditForm,
    showAddSlot,
    setShowAddSlot,
    newSlotLabel,
    setNewSlotLabel,
    newSlotCategory,
    setNewSlotCategory,
    newSlotRationale,
    setNewSlotRationale,
    handleSkipSlot,
    handleUnskipSlot,
    handleMoveSlot,
    handleDeleteSlot,
    handleAddSlot,
    handleDeleteProfile,
    handleUpdateSlot,
  } = useSlotManagement({ projectId, plan, loadData })

  const handleGuideGenerated = (profileId: string, guide: InterviewGuide) => {
    setGuideStatuses(prev => ({ ...prev, [profileId]: guide }))
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
