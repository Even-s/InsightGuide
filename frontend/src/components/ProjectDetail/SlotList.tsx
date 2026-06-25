import type { StakeholderSlot, StakeholderProfile, InterviewGuide } from '@/api/projects'
import { ProfileCard } from './ProfileCard'

interface SlotListProps {
  slots: StakeholderSlot[]
  profiles: StakeholderProfile[]
  projectId: string
  guideStatuses: Record<string, InterviewGuide | null>
  editingSlot: string | null
  editForm: { rationale: string; expectedContributions: string; keyQuestions: string; priority: string }
  setEditingSlot: (id: string | null) => void
  setEditForm: (f: { rationale: string; expectedContributions: string; keyQuestions: string; priority: string }) => void
  onMoveSlot: (slotId: string, direction: 'up' | 'down') => void
  onSkipSlot: (slotId: string) => void
  onUnskipSlot: (slotId: string) => void
  onDeleteSlot: (slotId: string) => void
  onUpdateSlot: (slotId: string) => void
  onAddProfile: (slotId: string) => void
  onDeleteProfile: (profileId: string) => void
  onShowGuideSettings: (profileId: string) => void
}

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

export function SlotList({
  slots,
  profiles,
  projectId,
  guideStatuses,
  editingSlot,
  editForm,
  setEditingSlot,
  setEditForm,
  onMoveSlot,
  onSkipSlot,
  onUnskipSlot,
  onDeleteSlot,
  onUpdateSlot,
  onAddProfile,
  onDeleteProfile,
  onShowGuideSettings,
}: SlotListProps) {
  return (
    <div className="space-y-6">
      {slots.map((slot, slotIndex) => {
        const slotProfiles = profiles.filter(p => p.slotId === slot.id)

        return (
          <div key={slot.id}>
            <div className="flex items-start gap-3 mb-3">
              <div className="flex flex-col items-center gap-0.5 flex-shrink-0 mt-0.5">
                <button
                  onClick={() => onMoveSlot(slot.id, 'up')}
                  disabled={slotIndex === 0}
                  className="text-natural-400 hover:text-natural-600 disabled:opacity-20 disabled:cursor-not-allowed p-0"
                  title="上移"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                  </svg>
                </button>
                <span className="text-[10px] text-natural-400 leading-none">{slotIndex + 1}</span>
                <button
                  onClick={() => onMoveSlot(slot.id, 'down')}
                  disabled={slotIndex === slots.length - 1}
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
                          onClick={() => onUnskipSlot(slot.id)}
                          className="text-natural-400 hover:text-green-500 p-0.5"
                          title="復原此角色"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a5 5 0 015 5v2M3 10l4-4M3 10l4 4" />
                          </svg>
                        </button>
                      ) : slot.status !== 'completed' && (
                        <button
                          onClick={() => onSkipSlot(slot.id)}
                          className="text-natural-400 hover:text-amber-500 p-0.5"
                          title="跳過此角色"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                          </svg>
                        </button>
                      )}
                      <button
                        onClick={() => onDeleteSlot(slot.id)}
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
                          onChange={e => setEditForm({ ...editForm, rationale: e.target.value })}
                          className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                        />
                      </div>
                      <div className="w-28">
                        <label className="text-xs text-natural-500">重要性</label>
                        <select
                          value={editForm.priority}
                          onChange={e => setEditForm({ ...editForm, priority: e.target.value })}
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
                        onChange={e => setEditForm({ ...editForm, expectedContributions: e.target.value })}
                        className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-natural-500">關鍵問題（每行一個）</label>
                      <textarea
                        value={editForm.keyQuestions}
                        onChange={e => setEditForm({ ...editForm, keyQuestions: e.target.value })}
                        rows={3}
                        className="w-full mt-0.5 px-2 py-1.5 text-sm border border-cream-200 rounded-lg focus:ring-1 focus:ring-sage-400"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => onUpdateSlot(slot.id)}
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
                      onClick={() => onAddProfile(slot.id)}
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
                {slotProfiles.map(profile => (
                  <ProfileCard
                    key={profile.id}
                    profile={profile}
                    projectId={projectId}
                    guide={guideStatuses[profile.id] ?? null}
                    onDelete={onDeleteProfile}
                    onShowGuideSettings={onShowGuideSettings}
                  />
                ))}
              </div>
            )}

            <div className="mt-4 border-b border-cream-200" />
          </div>
        )
      })}
    </div>
  )
}
