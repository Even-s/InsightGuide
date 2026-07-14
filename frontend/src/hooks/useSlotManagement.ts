import { useState } from 'react'
import {
  skipStakeholderSlot,
  unskipStakeholderSlot,
  updateStakeholderSlot,
  createStakeholderSlot,
  deleteStakeholderSlot,
  reorderStakeholderSlots,
  deleteStakeholder,
  type StakeholderPlan,
} from '@/api/projects'

interface UseSlotManagementProps {
  projectId: string | undefined
  plan: StakeholderPlan | null
  loadData: () => void
}

export function useSlotManagement({ projectId, plan, loadData }: UseSlotManagementProps) {
  const [editingSlot, setEditingSlot] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ rationale: '', expectedContributions: '', keyQuestions: '', priority: 'required' })
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

  const handleAddSlot = async () => {
    if (!newSlotLabel.trim() || !projectId) return
    try {
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

  const handleUpdateSlot = async (slotId: string) => {
    try {
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
    }
  }

  return {
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
    handleUpdateSlot,
  }
}
