import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { interviewAPI } from '@/api/interview'
import type { InterviewGuide } from '@/api/projects'
import { useProjectData } from '@/hooks/useProjectData'
import { useSlotManagement } from '@/hooks/useSlotManagement'
import { AddProfileModal } from '@/components/ProjectDetail/AddProfileModal'
import { GuideSettingsModal } from '@/components/ProjectDetail/GuideSettingsModal'
import { StartInterviewModal } from '@/components/ProjectDetail/StartInterviewModal'

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

        <div className="space-y-6">
          {plan.slots.map(slot => {
            const slotProfiles = plan.profiles.filter(p => p.slotId === slot.id)

            return (
              <div key={slot.id}>
                <div className="flex items-start gap-3 mb-3">
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
                            onClick={() => handleUpdateSlot(slot.id)}
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
                        {slot.rationale && (
                          <p className="text-sm text-natural-600 mt-1">{slot.rationale}</p>
                        )}

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
                                        interviewAPI.listSessions({ projectId, limit: 50 })
                                          .then(res => {
                                            const profileSession = res.sessions.find(s => s.stakeholderProfileId === profile.id)
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
                                  onClick={() => setShowGuideSettings(profile.id)}
                                  className="px-2.5 py-1 text-xs bg-sage-50 text-sage-700 rounded-lg hover:bg-sage-100"
                                >
                                  {guide ? '重新生成大綱' : '生成訪談大綱'}
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

                <div className="mt-4 border-b border-cream-200" />
              </div>
            )
          })}

        </div>
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
