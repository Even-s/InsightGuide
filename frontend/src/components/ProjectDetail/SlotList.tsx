import { useEffect, useRef, useState } from 'react'
import type { InterviewGuide, StakeholderProfile, StakeholderSlot } from '@/api/projects'
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
  onReassignProfile: (profileId: string, slotId: string | null) => void
  onShowGuideSettings: (profileId: string) => void
}

interface RoleStyle {
  label: string
  shortLabel: string
  accent: string
  border: string
  icon: string
}

type EditSection = 'priority' | 'rationale' | 'contributions' | 'questions'

const ROLE_STYLES: Record<string, RoleStyle> = {
  user: {
    label: '實際使用者', shortLabel: '使用', accent: 'bg-sage-400', border: 'border-sage-200',
    icon: 'bg-sage-100 text-sage-500',
  },
  business: {
    label: '業務流程', shortLabel: '業務', accent: 'bg-wood-400', border: 'border-wood-200',
    icon: 'bg-wood-100 text-wood-500',
  },
  product: {
    label: '產品規劃', shortLabel: '產品', accent: 'bg-sage-300', border: 'border-sage-200',
    icon: 'bg-sage-100 text-sage-500',
  },
  engineering: {
    label: '技術工程', shortLabel: '工程', accent: 'bg-natural-500', border: 'border-natural-300',
    icon: 'bg-natural-100 text-natural-600',
  },
  management: {
    label: '管理決策', shortLabel: '管理', accent: 'bg-wood-500', border: 'border-wood-200',
    icon: 'bg-wood-100 text-wood-500',
  },
  operations: {
    label: '營運執行', shortLabel: '營運', accent: 'bg-sage-500', border: 'border-sage-200',
    icon: 'bg-sage-100 text-sage-500',
  },
  customer_support: {
    label: '客戶支援', shortLabel: '客服', accent: 'bg-sage-300', border: 'border-sage-200',
    icon: 'bg-sage-50 text-sage-500',
  },
  legal: {
    label: '法遵風險', shortLabel: '法遵', accent: 'bg-wood-500', border: 'border-wood-200',
    icon: 'bg-wood-100 text-wood-500',
  },
  finance: {
    label: '財務預算', shortLabel: '財務', accent: 'bg-wood-300', border: 'border-wood-200',
    icon: 'bg-wood-100 text-wood-500',
  },
  design: {
    label: '體驗設計', shortLabel: '設計', accent: 'bg-sage-300', border: 'border-sage-200',
    icon: 'bg-sage-100 text-sage-500',
  },
  qa: {
    label: '品質驗證', shortLabel: '測試', accent: 'bg-natural-400', border: 'border-natural-300',
    icon: 'bg-natural-100 text-natural-600',
  },
  other: {
    label: '其他角色', shortLabel: '其他', accent: 'bg-cream-500', border: 'border-cream-300',
    icon: 'bg-cream-200 text-natural-600',
  },
}

const DEFAULT_ROLE_STYLE = ROLE_STYLES.other

function SlotStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string; dot: string }> = {
    unassigned: { label: '未安排', color: 'text-wood-500', dot: 'bg-wood-400' },
    partially_assigned: { label: '部分安排', color: 'text-natural-600', dot: 'bg-wood-300' },
    assigned: { label: '已安排', color: 'text-sage-500', dot: 'bg-sage-300' },
    interviewing: { label: '訪談中', color: 'text-sage-600', dot: 'bg-sage-400' },
    completed: { label: '已完成', color: 'text-sage-600', dot: 'bg-sage-500' },
    skipped: { label: '已跳過', color: 'text-natural-500', dot: 'bg-natural-400' },
  }
  const info = map[status] || { label: status, color: 'text-natural-700', dot: 'bg-natural-400' }
  return (
    <span className={`inline-flex items-center gap-2 text-xs font-semibold ${info.color}`}>
      <span className={`h-2 w-2 rounded-full ${info.dot}`} aria-hidden="true" />
      {info.label}
    </span>
  )
}

function PriorityBadge({
  priority,
  editLabel,
  onEdit,
  editDisabled,
}: {
  priority: string
  editLabel: string
  onEdit: () => void
  editDisabled: boolean
}) {
  const map: Record<string, { label: string; color: string }> = {
    required: { label: '必要角色', color: 'text-wood-500' },
    recommended: { label: '建議角色', color: 'text-sage-600' },
    optional: { label: '可選角色', color: 'text-natural-600' },
  }
  const info = map[priority] || { label: priority, color: 'text-natural-600' }
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${info.color}`}>
      <span className="h-3 w-0.5 bg-current opacity-50" aria-hidden="true" />
      <span>{info.label}</span>
      <button
        type="button"
        onClick={onEdit}
        disabled={editDisabled}
        className="inline-flex h-6 w-6 items-center justify-center rounded-sm text-natural-400 transition-colors hover:bg-cream-100 hover:text-natural-700 disabled:cursor-not-allowed disabled:opacity-35"
        aria-label={editLabel}
        title={editLabel}
      >
        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
      </button>
    </span>
  )
}

function SectionEditButton({
  label,
  onClick,
  disabled,
}: {
  label: string
  onClick: () => void
  disabled: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-natural-500 transition-colors hover:bg-white hover:text-sage-700 disabled:cursor-not-allowed disabled:opacity-35"
      aria-label={label}
      title={label}
    >
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
      </svg>
    </button>
  )
}

function InlineEditActions({
  onSave,
  onCancel,
  compact = false,
}: {
  onSave: () => void
  onCancel: () => void
  compact?: boolean
}) {
  return (
    <div className={`flex gap-2 ${compact ? '' : 'mt-3'}`}>
      <button
        type="button"
        onClick={onSave}
        className="rounded-md bg-sage-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sage-600"
      >
        儲存
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="rounded-md border border-cream-300 bg-white px-3 py-1.5 text-xs font-medium text-natural-600 hover:bg-cream-50"
      >
        取消
      </button>
    </div>
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
  onReassignProfile,
  onShowGuideSettings,
}: SlotListProps) {
  const [expandedSlots, setExpandedSlots] = useState<Set<string>>(new Set())
  const [openMenuSlot, setOpenMenuSlot] = useState<string | null>(null)
  const initializedExpansion = useRef(false)
  const slotIds = new Set(slots.map(slot => slot.id))
  const unassignedProfiles = profiles.filter(profile => !profile.slotId || !slotIds.has(profile.slotId))

  useEffect(() => {
    if (initializedExpansion.current || slots.length === 0) return
    const nextSlot = slots.find(slot => (
      slot.priority === 'required'
      && !['completed', 'skipped'].includes(slot.status)
    )) || slots.find(slot => slot.firstWave && slot.status !== 'completed') || slots[0]
    setExpandedSlots(new Set([nextSlot.id]))
    initializedExpansion.current = true
  }, [slots])

  useEffect(() => {
    if (!editingSlot) return
    const slotId = editingSlot.split(':')[0]
    setExpandedSlots(current => {
      if (current.has(slotId)) return current
      const next = new Set(current)
      next.add(slotId)
      return next
    })
  }, [editingSlot])

  const toggleSlot = (slotId: string) => {
    setExpandedSlots(current => {
      const next = new Set(current)
      if (next.has(slotId)) next.delete(slotId)
      else next.add(slotId)
      return next
    })
  }

  return (
    <div className="space-y-5">
      {slots.map((slot, slotIndex) => {
        const slotProfiles = profiles.filter(profile => profile.slotId === slot.id)
        const roleStyle = ROLE_STYLES[slot.roleCategory] || DEFAULT_ROLE_STYLE
        const progress = Math.min(100, Math.round((slot.interviewsDone / Math.max(slot.minInterviews, 1)) * 100))
        const isSkipped = slot.status === 'skipped'
        const isExpanded = expandedSlots.has(slot.id)
        const titleId = `slot-title-${slot.id}`
        const editingKey = (section: EditSection) => `${slot.id}:${section}`
        const isEditing = (section: EditSection) => editingSlot === editingKey(section)
        const editingLocked = editingSlot !== null
        const beginEditing = (section: EditSection) => {
          setEditForm({
            rationale: slot.rationale || '',
            expectedContributions: slot.expectedContributions.join(', '),
            keyQuestions: slot.keyQuestionsToCover.join('\n'),
            priority: slot.priority,
          })
          setEditingSlot(editingKey(section))
        }

        return (
          <article
            key={slot.id}
            aria-labelledby={titleId}
            className={`motion-surface-in relative rounded-lg border bg-white shadow-natural transition-shadow hover:shadow-md ${openMenuSlot === slot.id ? 'z-20' : 'z-0'} ${roleStyle.border} ${isSkipped ? 'opacity-60' : ''}`}
            style={{ animationDelay: `${Math.min(slotIndex * 45, 225)}ms` }}
          >
            <div className={`absolute inset-y-0 left-0 w-1 rounded-l-[7px] ${isSkipped ? 'bg-cream-300' : roleStyle.accent}`} aria-hidden="true" />

            <div className="p-5 pl-6 sm:p-6 sm:pl-7">
              <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(180px,220px)_auto] lg:items-center">
                <div className="flex min-w-0 items-start gap-4">
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="w-6 text-right text-xs font-semibold tabular-nums text-natural-400">
                      {String(slotIndex + 1).padStart(2, '0')}
                    </span>
                    <div className={`flex h-12 w-12 items-center justify-center rounded-sm text-[11px] font-bold tracking-wide ${roleStyle.icon}`} aria-hidden="true">
                      {roleStyle.shortLabel}
                    </div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-natural-500">
                      <span>{roleStyle.label}</span>
                      {slot.firstWave && (
                        <span className="inline-flex items-center gap-1 text-sage-600">
                          <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                            <path d="M10.894 2.553a1 1 0 00-1.788 0l-2 4.053-4.472.65a1 1 0 00-.554 1.706l3.236 3.154-.764 4.454a1 1 0 001.451 1.054L10 15.523l3.999 2.101a1 1 0 001.45-1.054l-.763-4.454 3.236-3.154a1 1 0 00-.555-1.706l-4.472-.65-2-4.053z" />
                          </svg>
                          第一輪優先
                        </span>
                      )}
                    </div>
                    <h3 id={titleId} className="break-words text-xl font-semibold leading-snug text-natural-800">
                      {slot.roleLabel}
                    </h3>
                    <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-natural-500">
                      {isEditing('priority') ? (
                        <div className="motion-reveal-in flex flex-wrap items-center gap-2 border-l-2 border-sage-300 bg-sage-50/60 px-3 py-2">
                          <label htmlFor={`priority-${slot.id}`} className="sr-only">編輯重要性</label>
                          <select
                            id={`priority-${slot.id}`}
                            value={editForm.priority}
                            onChange={event => setEditForm({ ...editForm, priority: event.target.value })}
                            className="rounded-md border border-cream-300 bg-white px-2.5 py-1.5 text-xs focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
                          >
                            <option value="required">必要角色</option>
                            <option value="recommended">建議角色</option>
                            <option value="optional">可選角色</option>
                          </select>
                          <InlineEditActions
                            onSave={() => onUpdateSlot(slot.id)}
                            onCancel={() => setEditingSlot(null)}
                            compact
                          />
                        </div>
                      ) : (
                        <PriorityBadge
                          priority={slot.priority}
                          editLabel={`編輯${slot.roleLabel}的重要性`}
                          onEdit={() => beginEditing('priority')}
                          editDisabled={editingLocked}
                        />
                      )}
                      <span className="h-3 w-px bg-cream-300" aria-hidden="true" />
                      <span className="tabular-nums">
                        <strong className="font-semibold text-natural-700">{slot.keyQuestionsToCover.length}</strong> 個問題
                      </span>
                      {slot.source === 'fallback' && (
                        <span className="border-l border-cream-300 pl-3 font-medium text-wood-500" title="AI 生成失敗後建立的暫用角色">
                          暫用建議
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="border-t border-cream-200 pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0" aria-label={`訪談進度 ${slot.interviewsDone} / ${slot.minInterviews}`}>
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-natural-400">訪談進度</span>
                    <SlotStatusBadge status={slot.status} />
                  </div>
                  <div className="flex items-end justify-between gap-3">
                    <div className="text-2xl font-semibold leading-none tabular-nums text-natural-800">
                      {slot.interviewsDone}
                      <span className="ml-1 text-sm font-normal text-natural-400">/ {slot.minInterviews} 場</span>
                    </div>
                    <span className="text-xs font-semibold tabular-nums text-natural-400">{progress}%</span>
                  </div>
                  <div className="mt-3 h-1 overflow-hidden bg-cream-200">
                    <div className={`h-full transition-all ${slot.status === 'completed' ? 'bg-sage-500' : roleStyle.accent}`} style={{ width: `${progress}%` }} />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-1 border-t border-cream-200 pt-4 lg:justify-end lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
                  {!isSkipped && slot.status !== 'completed' && (
                    <button
                      type="button"
                      onClick={() => onAddProfile(slot.id)}
                      className="inline-flex h-10 items-center gap-2 rounded-md bg-sage-400 px-4 text-sm font-semibold text-white transition-colors hover:bg-sage-500"
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      {slot.profilesCount > 0 ? '新增受訪者' : '指派受訪者'}
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => onDeleteSlot(slot.id)}
                    className="inline-flex h-10 w-10 items-center justify-center rounded-md text-natural-400 transition-colors hover:bg-red-50 hover:text-red-500"
                    aria-label={`刪除「${slot.roleLabel}」角色`}
                    title={`刪除「${slot.roleLabel}」角色`}
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3m-9 0h12" />
                    </svg>
                  </button>

                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setOpenMenuSlot(current => current === slot.id ? null : slot.id)}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-md text-natural-500 transition-colors hover:bg-cream-100 hover:text-natural-700"
                      aria-label={`更多「${slot.roleLabel}」操作`}
                      aria-expanded={openMenuSlot === slot.id}
                      aria-haspopup="menu"
                    >
                      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                        <circle cx="4" cy="10" r="1.5" />
                        <circle cx="10" cy="10" r="1.5" />
                        <circle cx="16" cy="10" r="1.5" />
                      </svg>
                    </button>
                    {openMenuSlot === slot.id && (
                      <div className="motion-popover-in absolute right-0 z-20 mt-2 w-40 overflow-hidden rounded-md border border-cream-200 bg-white py-1 shadow-lg" role="menu">
                        <button
                          type="button"
                          onClick={() => { onMoveSlot(slot.id, 'up'); setOpenMenuSlot(null) }}
                          disabled={slotIndex === 0}
                          className="flex w-full items-center px-3 py-2 text-left text-xs text-natural-600 hover:bg-cream-50 disabled:cursor-not-allowed disabled:opacity-35"
                          role="menuitem"
                        >
                          上移角色
                        </button>
                        <button
                          type="button"
                          onClick={() => { onMoveSlot(slot.id, 'down'); setOpenMenuSlot(null) }}
                          disabled={slotIndex === slots.length - 1}
                          className="flex w-full items-center px-3 py-2 text-left text-xs text-natural-600 hover:bg-cream-50 disabled:cursor-not-allowed disabled:opacity-35"
                          role="menuitem"
                        >
                          下移角色
                        </button>
                        <div className="my-1 border-t border-cream-100" />
                        <button
                          type="button"
                          onClick={() => {
                            if (isSkipped) onUnskipSlot(slot.id)
                            else onSkipSlot(slot.id)
                            setOpenMenuSlot(null)
                          }}
                          disabled={!isSkipped && slot.status === 'completed'}
                          className="flex w-full items-center px-3 py-2 text-left text-xs text-natural-600 hover:bg-cream-50 disabled:cursor-not-allowed disabled:opacity-35"
                          role="menuitem"
                        >
                          {isSkipped ? '恢復角色' : '跳過角色'}
                        </button>
                        <button
                          type="button"
                          onClick={() => { onDeleteSlot(slot.id); setOpenMenuSlot(null) }}
                          className="flex w-full items-center px-3 py-2 text-left text-xs text-red-500 hover:bg-red-50"
                          role="menuitem"
                        >
                          刪除角色
                        </button>
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => toggleSlot(slot.id)}
                    className="inline-flex h-10 items-center gap-1.5 border-b border-transparent px-2 text-sm font-semibold text-natural-600 transition-colors hover:border-sage-400 hover:text-sage-600"
                    aria-expanded={isExpanded}
                    aria-controls={`slot-details-${slot.id}`}
                    aria-label={`${isExpanded ? '收合' : '展開'}「${slot.roleLabel}」詳情`}
                  >
                    {isExpanded ? '收合' : '詳情'}
                    <svg className={`h-3.5 w-3.5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>
              </div>

              <div
                id={`slot-details-${slot.id}`}
                className={`slot-details-collapse ${isExpanded ? 'slot-details-collapse--open' : ''}`}
                aria-hidden={!isExpanded}
              >
                <div className="min-h-0 overflow-hidden">
                  <div className="mt-6 grid border-t border-cream-200 pt-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                  <div className="divide-y divide-cream-200 xl:pr-6">
                    <section className="border-l-2 border-sage-300 bg-sage-50/30 px-4 py-3">
                        <div className="mb-2 flex items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wider text-natural-500">
                          <div className="flex items-center gap-2">
                          <svg className="h-4 w-4 text-sage-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                          </svg>
                          訪談目的
                          </div>
                          {!isEditing('rationale') && (
                            <SectionEditButton
                              label={`編輯${slot.roleLabel}的訪談目的`}
                              onClick={() => beginEditing('rationale')}
                              disabled={editingLocked}
                            />
                          )}
                        </div>
                        {isEditing('rationale') ? (
                          <div className="motion-reveal-in">
                            <label htmlFor={`rationale-${slot.id}`} className="sr-only">編輯訪談目的</label>
                            <textarea
                              id={`rationale-${slot.id}`}
                              value={editForm.rationale}
                              onChange={event => setEditForm({ ...editForm, rationale: event.target.value })}
                              rows={3}
                              className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-sm leading-6 focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
                            />
                            <InlineEditActions onSave={() => onUpdateSlot(slot.id)} onCancel={() => setEditingSlot(null)} />
                          </div>
                        ) : (
                          <p className={`text-sm leading-6 ${slot.rationale ? 'text-natural-700' : 'italic text-natural-400'}`}>
                            {slot.rationale || '尚未設定訪談目的'}
                          </p>
                        )}
                      </section>

                      <section className="py-4">
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-natural-500">預期取得的資訊</h4>
                          {!isEditing('contributions') && (
                            <SectionEditButton
                              label={`編輯${slot.roleLabel}的預期資訊`}
                              onClick={() => beginEditing('contributions')}
                              disabled={editingLocked}
                            />
                          )}
                        </div>
                        {isEditing('contributions') ? (
                          <div className="motion-reveal-in border-l-2 border-sage-300 bg-sage-50/40 p-3">
                            <label htmlFor={`contributions-${slot.id}`} className="mb-1 block text-xs text-natural-500">使用逗號分隔每一項資訊</label>
                            <textarea
                              id={`contributions-${slot.id}`}
                              value={editForm.expectedContributions}
                              onChange={event => setEditForm({ ...editForm, expectedContributions: event.target.value })}
                              rows={3}
                              className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-sm focus:border-sage-400 focus:outline-none focus:ring-2 focus:ring-sage-100"
                            />
                            <InlineEditActions onSave={() => onUpdateSlot(slot.id)} onCancel={() => setEditingSlot(null)} />
                          </div>
                        ) : slot.expectedContributions.length > 0 ? (
                          <ul className="grid gap-x-5 sm:grid-cols-2 xl:grid-cols-1">
                          {slot.expectedContributions.map((contribution, index) => (
                            <li key={index} className="flex items-start gap-2 border-b border-cream-200 py-2 text-sm text-natural-700 last:border-b-0">
                              <span className={`mt-2 h-1.5 w-1.5 shrink-0 ${roleStyle.accent}`} aria-hidden="true" />
                              <span>{contribution}</span>
                            </li>
                          ))}
                          </ul>
                        ) : (
                          <p className="text-sm italic text-natural-400">尚未設定預期資訊</p>
                        )}
                      </section>
                  </div>

                    <section className="mt-5 border-t border-cream-200 pt-5 xl:mt-0 xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-natural-500">關鍵問題</h4>
                        <div className="flex items-center gap-1">
                          <span className="text-[11px] font-semibold tabular-nums text-natural-400">
                            共 {slot.keyQuestionsToCover.length} 題
                          </span>
                          {!isEditing('questions') && (
                            <SectionEditButton
                              label={`編輯${slot.roleLabel}的關鍵問題`}
                              onClick={() => beginEditing('questions')}
                              disabled={editingLocked}
                            />
                          )}
                        </div>
                      </div>
                      {isEditing('questions') ? (
                        <div className="motion-reveal-in">
                          <label htmlFor={`questions-${slot.id}`} className="mb-1 block text-xs text-natural-500">每行輸入一個問題</label>
                          <textarea
                            id={`questions-${slot.id}`}
                            value={editForm.keyQuestions}
                            onChange={event => setEditForm({ ...editForm, keyQuestions: event.target.value })}
                            rows={Math.max(5, slot.keyQuestionsToCover.length + 1)}
                            className="w-full rounded-md border border-cream-300 bg-cream-50/50 px-3 py-2 text-sm leading-6 focus:border-sage-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sage-100"
                          />
                          <InlineEditActions onSave={() => onUpdateSlot(slot.id)} onCancel={() => setEditingSlot(null)} />
                        </div>
                      ) : slot.keyQuestionsToCover.length > 0 ? (
                        <ol className="divide-y divide-cream-200 border-y border-cream-200">
                        {slot.keyQuestionsToCover.map((question, index) => (
                          <li key={index} className="flex items-start gap-3 py-3 text-sm leading-5 text-natural-700">
                            <span className="w-6 shrink-0 border-r border-cream-300 pr-2 text-right text-xs font-bold tabular-nums text-sage-500">
                              {String(index + 1).padStart(2, '0')}
                            </span>
                            <span>{question}</span>
                          </li>
                        ))}
                        </ol>
                      ) : (
                        <p className="text-sm italic text-natural-400">尚未設定關鍵問題</p>
                      )}
                    </section>
                  </div>
                </div>
              </div>
            </div>

            {slotProfiles.length > 0 && (
              <section className="motion-reveal-in border-t border-cream-200 bg-cream-50 px-5 py-4 sm:px-7" aria-label={`${slot.roleLabel}的受訪者`}>
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-natural-500">已指派受訪者</h4>
                  <span className="text-xs font-medium text-natural-500">{slotProfiles.length} 人</span>
                </div>
                <div className="space-y-2">
                  {slotProfiles.map(profile => (
                    <ProfileCard
                      key={profile.id}
                      profile={profile}
                      projectId={projectId}
                      guide={guideStatuses[profile.id] ?? null}
                      slots={slots}
                      onDelete={onDeleteProfile}
                      onReassign={onReassignProfile}
                      onShowGuideSettings={onShowGuideSettings}
                    />
                  ))}
                </div>
              </section>
            )}
          </article>
        )
      })}

      {unassignedProfiles.length > 0 && (
        <section className="motion-surface-in rounded-lg border border-dashed border-wood-200 bg-wood-50/40 p-5 shadow-natural">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-wood-600">
                未隸屬任何角色的受訪者
              </h3>
              <p className="mt-1 text-xs text-natural-500">
                這些受訪者目前不屬於任何訪談角色，可用卡片中的「歸屬角色」重新指派。
              </p>
            </div>
            <span className="shrink-0 text-xs font-medium text-natural-500">{unassignedProfiles.length} 人</span>
          </div>
          <div className="space-y-2">
            {unassignedProfiles.map(profile => (
              <ProfileCard
                key={profile.id}
                profile={profile}
                projectId={projectId}
                guide={guideStatuses[profile.id] ?? null}
                slots={slots}
                onDelete={onDeleteProfile}
                onReassign={onReassignProfile}
                onShowGuideSettings={onShowGuideSettings}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
