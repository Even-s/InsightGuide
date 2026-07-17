import { useState } from 'react'
import {
  skipStakeholderSlot,
  unskipStakeholderSlot,
  updateStakeholderSlot,
  createStakeholderSlot,
  deleteStakeholderSlot,
  reorderStakeholderSlots,
  deleteStakeholder,
  updateStakeholder,
  type StakeholderPlan,
} from '@/api/projects'

function getApiErrorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { detail?: unknown } } })?.response
  return typeof response?.data?.detail === 'string' ? response.data.detail : fallback
}

interface UseSlotManagementProps {
  projectId: string | undefined
  plan: StakeholderPlan | null
  loadData: () => void
}

export function useSlotManagement({ projectId, plan, loadData }: UseSlotManagementProps) {
  const [editingSlot, setEditingSlot] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ rationale: '', expectedContributions: '', keyQuestions: '', priority: 'required' })
  const [slotActionError, setSlotActionError] = useState<string | null>(null)
  const [showAddSlot, setShowAddSlot] = useState(false)
  const [newSlotLabel, setNewSlotLabel] = useState('')
  const [newSlotCategory, setNewSlotCategory] = useState('business')
  const [newSlotRationale, setNewSlotRationale] = useState('')
  const [newSlotPriority, setNewSlotPriority] = useState('required')
  const [newSlotMinInterviews, setNewSlotMinInterviews] = useState(1)
  const [newSlotFirstWave, setNewSlotFirstWave] = useState(false)
  const [newSlotExpectedContributions, setNewSlotExpectedContributions] = useState('')
  const [newSlotKeyQuestions, setNewSlotKeyQuestions] = useState('')

  const handleSkipSlot = async (slotId: string) => {
    try {
      setSlotActionError(null)
      await skipStakeholderSlot(slotId)
      loadData()
    } catch (err) {
      console.error('Failed to skip slot:', err)
      setSlotActionError(getApiErrorMessage(err, '跳過角色失敗，請稍後再試。'))
    }
  }

  const handleUnskipSlot = async (slotId: string) => {
    try {
      setSlotActionError(null)
      await unskipStakeholderSlot(slotId)
      loadData()
    } catch (err) {
      console.error('Failed to unskip slot:', err)
      setSlotActionError(getApiErrorMessage(err, '恢復角色失敗，請稍後再試。'))
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
      setSlotActionError(null)
      await reorderStakeholderSlots(ids)
      loadData()
    } catch (err) {
      console.error('Failed to reorder slots:', err)
      setSlotActionError(getApiErrorMessage(err, '調整角色順序失敗，請稍後再試。'))
    }
  }

  const handleDeleteSlot = async (slotId: string) => {
    const slot = plan?.slots.find(s => s.id === slotId)
    const roleName = slot?.roleLabel ? `「${slot.roleLabel}」` : '此角色'
    if (!confirm(`確定要刪除${roleName}？若角色底下仍有受訪者，需要先移除受訪者。`)) return
    try {
      setSlotActionError(null)
      await deleteStakeholderSlot(slotId)
      loadData()
    } catch (err) {
      console.error('Failed to delete slot:', err)
      const message = getApiErrorMessage(err, '刪除角色失敗，請稍後再試。')
      setSlotActionError(message)
      window.alert(message)
    }
  }

  const handleAddSlot = async () => {
    if (!newSlotLabel.trim() || !projectId) return
    try {
      setSlotActionError(null)
      await createStakeholderSlot(projectId, {
        role_category: newSlotCategory,
        role_label: newSlotLabel.trim(),
        rationale: newSlotRationale.trim() || undefined,
        expected_contributions: newSlotExpectedContributions.split(',').map(s => s.trim()).filter(Boolean),
        key_questions_to_cover: newSlotKeyQuestions.split('\n').map(s => s.trim()).filter(Boolean),
        priority: newSlotPriority,
        min_interviews: newSlotMinInterviews,
        first_wave: newSlotFirstWave,
      })
      setShowAddSlot(false)
      setNewSlotLabel('')
      setNewSlotCategory('business')
      setNewSlotRationale('')
      setNewSlotPriority('required')
      setNewSlotMinInterviews(1)
      setNewSlotFirstWave(false)
      setNewSlotExpectedContributions('')
      setNewSlotKeyQuestions('')
      loadData()
    } catch (err) {
      console.error('Failed to add slot:', err)
      setSlotActionError(getApiErrorMessage(err, '新增角色失敗，請稍後再試。'))
    }
  }

  const handleDeleteProfile = async (profileId: string) => {
    if (!confirm('確定要移除此受訪者？')) return
    try {
      setSlotActionError(null)
      await deleteStakeholder(profileId)
      loadData()
    } catch (err) {
      console.error('Failed to delete stakeholder:', err)
      setSlotActionError(getApiErrorMessage(err, '移除受訪者失敗，請稍後再試。'))
    }
  }

  const handleReassignProfile = async (profileId: string, slotId: string | null) => {
    try {
      setSlotActionError(null)
      await updateStakeholder(profileId, { slot_id: slotId })
      loadData()
    } catch (err) {
      console.error('Failed to reassign stakeholder:', err)
      setSlotActionError(getApiErrorMessage(err, '調整受訪者角色失敗，請稍後再試。'))
    }
  }

  const handleUpdateSlot = async (slotId: string) => {
    try {
      setSlotActionError(null)
      await updateStakeholderSlot(slotId, {
        rationale: editForm.rationale,
        expected_contributions: editForm.expectedContributions.split(',').map(s => s.trim()).filter(Boolean),
        key_questions_to_cover: editForm.keyQuestions.split('\n').map(s => s.trim()).filter(Boolean),
        priority: editForm.priority,
      })
      setEditingSlot(null)
      loadData()
    } catch (err) {
      console.error('Failed to update slot:', err)
      setSlotActionError(getApiErrorMessage(err, '更新角色失敗，請稍後再試。'))
    }
  }

  return {
    editingSlot,
    setEditingSlot,
    editForm,
    setEditForm,
    slotActionError,
    setSlotActionError,
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
  }
}
