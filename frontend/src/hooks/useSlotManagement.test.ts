import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { StakeholderPlan } from '@/api/projects'
import { useSlotManagement } from './useSlotManagement'

const mockSkipSlot = vi.fn().mockResolvedValue(undefined)
const mockUnskipSlot = vi.fn().mockResolvedValue(undefined)
const mockUpdateSlot = vi.fn().mockResolvedValue(undefined)
const mockCreateSlot = vi.fn().mockResolvedValue(undefined)
const mockDeleteSlot = vi.fn().mockResolvedValue(undefined)
const mockReorderSlots = vi.fn().mockResolvedValue(undefined)
const mockDeleteStakeholder = vi.fn().mockResolvedValue(undefined)
const mockUpdateStakeholderProfileSlots = vi.fn().mockResolvedValue(undefined)

vi.mock('@/api/projects', () => ({
  skipStakeholderSlot: (...args: unknown[]) => mockSkipSlot(...args),
  unskipStakeholderSlot: (...args: unknown[]) => mockUnskipSlot(...args),
  updateStakeholderSlot: (...args: unknown[]) => mockUpdateSlot(...args),
  createStakeholderSlot: (...args: unknown[]) => mockCreateSlot(...args),
  deleteStakeholderSlot: (...args: unknown[]) => mockDeleteSlot(...args),
  reorderStakeholderSlots: (...args: unknown[]) => mockReorderSlots(...args),
  deleteStakeholder: (...args: unknown[]) => mockDeleteStakeholder(...args),
  updateStakeholderProfileSlots: (...args: unknown[]) => mockUpdateStakeholderProfileSlots(...args),
}))

const mockPlan = {
  slots: [
    { id: 'slot-1', roleLabel: 'Engineer', status: 'unassigned', priority: 'required' },
    { id: 'slot-2', roleLabel: 'PM', status: 'assigned', priority: 'recommended' },
    { id: 'slot-3', roleLabel: 'Designer', status: 'completed', priority: 'optional' },
  ],
  profiles: [],
}

describe('useSlotManagement', () => {
  const loadData = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.confirm = vi.fn().mockReturnValue(true)
  })

  it('initializes with default state', () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    expect(result.current.editingSlot).toBeNull()
    expect(result.current.showAddSlot).toBe(false)
    expect(result.current.newSlotLabel).toBe('')
    expect(result.current.newSlotCategory).toBe('business')
    expect(result.current.newSlotPriority).toBe('required')
    expect(result.current.newSlotMinInterviews).toBe(1)
    expect(result.current.newSlotFirstWave).toBe(false)
    expect(result.current.newSlotExpectedContributions).toBe('')
    expect(result.current.newSlotKeyQuestions).toBe('')
  })

  it('handleSkipSlot calls API and reloads', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleSkipSlot('slot-1')
    })

    expect(mockSkipSlot).toHaveBeenCalledWith('slot-1')
    expect(loadData).toHaveBeenCalled()
  })

  it('handleUnskipSlot calls API and reloads', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleUnskipSlot('slot-2')
    })

    expect(mockUnskipSlot).toHaveBeenCalledWith('slot-2')
    expect(loadData).toHaveBeenCalled()
  })

  it('handleMoveSlot swaps slot order and calls reorder API', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleMoveSlot('slot-2', 'up')
    })

    expect(mockReorderSlots).toHaveBeenCalledWith(['slot-2', 'slot-1', 'slot-3'])
    expect(loadData).toHaveBeenCalled()
  })

  it('handleMoveSlot does nothing when moving first slot up', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleMoveSlot('slot-1', 'up')
    })

    expect(mockReorderSlots).not.toHaveBeenCalled()
  })

  it('handleMoveSlot does nothing when moving last slot down', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleMoveSlot('slot-3', 'down')
    })

    expect(mockReorderSlots).not.toHaveBeenCalled()
  })

  it('handleDeleteSlot asks confirmation and calls API', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleDeleteSlot('slot-1')
    })

    expect(globalThis.confirm).toHaveBeenCalled()
    expect(mockDeleteSlot).toHaveBeenCalledWith('slot-1')
    expect(loadData).toHaveBeenCalled()
  })

  it('handleDeleteSlot does nothing when cancelled', async () => {
    vi.mocked(globalThis.confirm).mockReturnValue(false)

    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleDeleteSlot('slot-1')
    })

    expect(mockDeleteSlot).not.toHaveBeenCalled()
  })

  it('handleAddSlot creates slot and resets form', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    act(() => {
      result.current.setNewSlotLabel('QA Lead')
      result.current.setNewSlotCategory('qa')
      result.current.setNewSlotRationale('Need QA perspective')
      result.current.setNewSlotPriority('recommended')
      result.current.setNewSlotMinInterviews(2)
      result.current.setNewSlotFirstWave(true)
      result.current.setNewSlotExpectedContributions('Test strategy, Release risks')
      result.current.setNewSlotKeyQuestions('How do you test?\nWhat blocks release?')
      result.current.setShowAddSlot(true)
    })

    await act(async () => {
      await result.current.handleAddSlot()
    })

    expect(mockCreateSlot).toHaveBeenCalledWith('proj-1', {
      role_category: 'qa',
      role_label: 'QA Lead',
      rationale: 'Need QA perspective',
      expected_contributions: ['Test strategy', 'Release risks'],
      key_questions_to_cover: ['How do you test?', 'What blocks release?'],
      priority: 'recommended',
      min_interviews: 2,
      first_wave: true,
    })
    expect(result.current.showAddSlot).toBe(false)
    expect(result.current.newSlotLabel).toBe('')
    expect(result.current.newSlotPriority).toBe('required')
    expect(result.current.newSlotMinInterviews).toBe(1)
    expect(result.current.newSlotFirstWave).toBe(false)
    expect(result.current.newSlotExpectedContributions).toBe('')
    expect(result.current.newSlotKeyQuestions).toBe('')
    expect(loadData).toHaveBeenCalled()
  })

  it('handleAddSlot does nothing with empty label', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleAddSlot()
    })

    expect(mockCreateSlot).not.toHaveBeenCalled()
  })

  it('handleDeleteProfile asks confirmation and calls API', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleDeleteProfile('profile-1')
    })

    expect(globalThis.confirm).toHaveBeenCalled()
    expect(mockDeleteStakeholder).toHaveBeenCalledWith('profile-1')
    expect(loadData).toHaveBeenCalled()
  })

  it('handleReassignProfile replaces a participant role assignment set', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    await act(async () => {
      await result.current.handleReassignProfile('profile-1', ['slot-2'])
    })
    await act(async () => {
      await result.current.handleReassignProfile('profile-1', [])
    })

    expect(mockUpdateStakeholderProfileSlots).toHaveBeenNthCalledWith(1, 'profile-1', {
      slot_ids: ['slot-2'],
      primary_slot_id: 'slot-2',
    })
    expect(mockUpdateStakeholderProfileSlots).toHaveBeenNthCalledWith(2, 'profile-1', {
      slot_ids: [],
      primary_slot_id: null,
    })
    expect(loadData).toHaveBeenCalledTimes(2)
  })

  it('handleUpdateSlot updates and clears editing state', async () => {
    const { result } = renderHook(() =>
      useSlotManagement({ projectId: 'proj-1', plan: mockPlan as unknown as StakeholderPlan, loadData }),
    )

    act(() => {
      result.current.setEditingSlot('slot-1')
      result.current.setEditForm({
        rationale: 'Updated rationale',
        expectedContributions: 'A, B, C',
        keyQuestions: 'Q1\nQ2',
        priority: 'recommended',
      })
    })

    await act(async () => {
      await result.current.handleUpdateSlot('slot-1')
    })

    expect(mockUpdateSlot).toHaveBeenCalledWith('slot-1', {
      rationale: 'Updated rationale',
      expected_contributions: ['A', 'B', 'C'],
      key_questions_to_cover: ['Q1', 'Q2'],
      priority: 'recommended',
    })
    expect(result.current.editingSlot).toBeNull()
    expect(loadData).toHaveBeenCalled()
  })
})
