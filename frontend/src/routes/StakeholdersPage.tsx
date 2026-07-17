import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { updateStakeholderProfileSlots, type StakeholderProfile } from '@/api/projects'
import { useProjectData } from '@/hooks/useProjectData'

export default function StakeholdersPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { dashboard, plan, loading, loadData } = useProjectData(projectId)
  const [savingProfileId, setSavingProfileId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (loading) {
    return <div className="mx-auto max-w-5xl px-6 py-8 text-center text-natural-500">載入中...</div>
  }

  if (!projectId || !dashboard || !plan) {
    return <div className="mx-auto max-w-5xl px-6 py-8 text-center text-red-500">無法載入受訪者</div>
  }

  const toggleSlot = async (profile: StakeholderProfile, slotId: string) => {
    const current = profile.assignedSlotIds || []
    const next = current.includes(slotId)
      ? current.filter(id => id !== slotId)
      : [...current, slotId]

    setSavingProfileId(profile.id)
    setError(null)
    try {
      await updateStakeholderProfileSlots(profile.id, {
        slot_ids: next,
        primary_slot_id: next[0] || null,
      })
      await loadData()
    } catch (err) {
      console.error('Failed to update stakeholder roles:', err)
      setError('更新受訪者角色失敗，請稍後再試。')
    } finally {
      setSavingProfileId(null)
    }
  }

  const profiles = [...plan.profiles].sort((a, b) => a.name.localeCompare(b.name, 'zh-Hant'))
  const unassignedCount = profiles.filter(profile => (profile.assignedSlotIds || []).length === 0).length

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => navigate(`/projects/${projectId}`)}
            className="mt-1 text-natural-400 hover:text-natural-600"
            aria-label="回到專案"
          >
            &larr;
          </button>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sage-500">
              Stakeholders
            </p>
            <h1 className="mt-1 text-2xl font-bold text-natural-800">受訪者管理</h1>
            <p className="mt-1 text-sm text-natural-500">
              {dashboard.project.title} · {profiles.length} 位受訪者 · {unassignedCount} 位未隸屬角色
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => navigate(`/projects/${projectId}`)}
          className="rounded-xl border border-cream-300 bg-white px-4 py-2 text-sm font-medium text-natural-600 shadow-natural hover:border-sage-200 hover:bg-sage-50 hover:text-sage-700"
        >
          回訪談計劃
        </button>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="space-y-4">
        {profiles.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-cream-300 bg-white p-8 text-center text-natural-400">
            目前還沒有受訪者。回到訪談計劃後可從任一角色新增。
          </div>
        ) : profiles.map(profile => {
          const assignedSlotIds = profile.assignedSlotIds || []
          return (
            <article
              key={profile.id}
              className="rounded-2xl border border-cream-200 bg-white p-5 shadow-natural"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cream-100 text-sm font-semibold text-natural-700">
                    {profile.name.charAt(0)}
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-natural-800">{profile.name}</h2>
                    <p className="mt-0.5 text-sm text-natural-500">
                      {[profile.roleTitle, profile.department].filter(Boolean).join(' · ') || '未設定職稱與部門'}
                    </p>
                    <p className="mt-1 text-xs text-natural-400">
                      {profile.interviewCount} 場訪談 · {profile.status === 'interviewed' ? '已訪' : '待訪'}
                    </p>
                  </div>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs ${
                  assignedSlotIds.length
                    ? 'bg-sage-50 text-sage-700'
                    : 'bg-amber-50 text-amber-700'
                }`}>
                  {assignedSlotIds.length ? `${assignedSlotIds.length} 個角色` : '未隸屬任何角色'}
                </span>
              </div>

              {(profile.expertiseTags.length > 0 || profile.knowledgeBoundaries.length > 0) && (
                <div className="mt-4 grid gap-3 border-t border-cream-100 pt-4 md:grid-cols-2">
                  <TagGroup title="熟悉領域" tags={profile.expertiseTags} />
                  <TagGroup title="不熟悉領域" tags={profile.knowledgeBoundaries} muted />
                </div>
              )}

              <div className="mt-4 border-t border-cream-100 pt-4">
                <div className="mb-2 text-xs font-semibold text-natural-500">適用角色</div>
                <div className="flex flex-wrap gap-2">
                  {plan.slots.map(slot => {
                    const checked = assignedSlotIds.includes(slot.id)
                    const disabled = savingProfileId === profile.id
                    return (
                      <button
                        key={slot.id}
                        type="button"
                        disabled={disabled}
                        onClick={() => toggleSlot(profile, slot.id)}
                        className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-60 ${
                          checked
                            ? 'border-sage-300 bg-sage-50 text-sage-700'
                            : 'border-cream-200 bg-white text-natural-400 hover:border-sage-200 hover:text-sage-600'
                        }`}
                        aria-pressed={checked}
                      >
                        {checked ? '✓ ' : '+ '}
                        {slot.roleLabel}
                      </button>
                    )
                  })}
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}

function TagGroup({ title, tags, muted = false }: { title: string; tags: string[]; muted?: boolean }) {
  if (!tags.length) return null
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium text-natural-400">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {tags.map(tag => (
          <span
            key={tag}
            className={`rounded-full border px-2 py-1 text-[11px] ${
              muted
                ? 'border-cream-200 bg-cream-50 text-natural-400'
                : 'border-sage-100 bg-sage-50 text-sage-700'
            }`}
          >
            {tag}
          </span>
        ))}
      </div>
    </div>
  )
}
