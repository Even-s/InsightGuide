import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { StakeholderSlot } from '@/api/projects'
import { SlotList } from './SlotList'

const slots: StakeholderSlot[] = [
  {
    id: 'slot-user',
    projectId: 'proj-1',
    roleCategory: 'user',
    roleLabel: '掛號櫃台人員',
    rationale: '了解掛號現場的實際流程與操作障礙。',
    expectedContributions: ['實際掛號流程', '常見例外'],
    keyQuestionsToCover: ['上次處理當日掛號時，最花時間的是哪一步？'],
    priority: 'required',
    minInterviews: 2,
    firstWave: true,
    status: 'unassigned',
    orderIndex: 0,
    source: 'ai_suggested',
    profilesCount: 0,
    interviewsDone: 0,
    createdAt: '2026-07-14T00:00:00Z',
    updatedAt: '2026-07-14T00:00:00Z',
  },
  {
    id: 'slot-engineering',
    projectId: 'proj-1',
    roleCategory: 'engineering',
    roleLabel: '掛號系統維運人員',
    rationale: '了解既有系統與資料介接限制。',
    expectedContributions: ['整合限制'],
    keyQuestionsToCover: ['最近一次系統異常發生在哪一段？'],
    priority: 'recommended',
    minInterviews: 1,
    firstWave: false,
    status: 'assigned',
    orderIndex: 1,
    source: 'ai_suggested',
    profilesCount: 1,
    interviewsDone: 0,
    createdAt: '2026-07-14T00:00:00Z',
    updatedAt: '2026-07-14T00:00:00Z',
  },
]

function renderSlotList(overrides: Partial<React.ComponentProps<typeof SlotList>> = {}) {
  const props: React.ComponentProps<typeof SlotList> = {
    slots,
    profiles: [],
    projectId: 'proj-1',
    guideStatuses: {},
    editingSlot: null,
    editForm: { rationale: '', expectedContributions: '', keyQuestions: '', priority: 'required' },
    setEditingSlot: vi.fn(),
    setEditForm: vi.fn(),
    onMoveSlot: vi.fn(),
    onSkipSlot: vi.fn(),
    onUnskipSlot: vi.fn(),
    onDeleteSlot: vi.fn(),
    onUpdateSlot: vi.fn(),
    onAddProfile: vi.fn(),
    onDeleteProfile: vi.fn(),
    onReassignProfile: vi.fn(),
    onShowGuideSettings: vi.fn(),
    ...overrides,
  }

  return {
    ...render(
      <MemoryRouter>
        <SlotList {...props} />
      </MemoryRouter>,
    ),
    props,
  }
}

describe('SlotList', () => {
  it('visually distinguishes role categories and first-wave priority', () => {
    renderSlotList()

    expect(screen.getByRole('article', { name: '掛號櫃台人員' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: '掛號系統維運人員' })).toBeInTheDocument()
    expect(screen.getByText('實際使用者')).toBeInTheDocument()
    expect(screen.getByText('技術工程')).toBeInTheDocument()
    expect(screen.getByText('第一輪優先')).toBeInTheDocument()
    expect(screen.getByText('必要角色')).toBeInTheDocument()
    expect(screen.getByText('建議角色')).toBeInTheDocument()
  })

  it('separates purpose, expected information, questions, and interview progress', () => {
    renderSlotList()

    const collapsedDetails = document.getElementById('slot-details-slot-engineering')
    expect(collapsedDetails).toHaveAttribute('aria-hidden', 'true')
    expect(collapsedDetails).not.toHaveClass('slot-details-collapse--open')
    expect(screen.getByText('實際掛號流程')).toBeInTheDocument()
    expect(screen.getByLabelText('訪談進度 0 / 2')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '展開「掛號系統維運人員」詳情' }))
    expect(collapsedDetails).toHaveAttribute('aria-hidden', 'false')
    expect(collapsedDetails).toHaveClass('slot-details-collapse--open')
    expect(screen.getByText('了解既有系統與資料介接限制。')).toBeInTheDocument()
  })

  it('provides independent editing actions for each content section', () => {
    const setEditingSlot = vi.fn()
    const { props } = renderSlotList({ setEditingSlot })

    expect(screen.getByRole('button', { name: '編輯掛號櫃台人員的重要性' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '編輯掛號櫃台人員的訪談目的' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '編輯掛號櫃台人員的預期資訊' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '編輯掛號櫃台人員的關鍵問題' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '編輯掛號櫃台人員的關鍵問題' }))
    expect(setEditingSlot).toHaveBeenCalledWith('slot-user:questions')
    expect(props.setEditForm).toHaveBeenCalledWith(expect.objectContaining({
      keyQuestions: '上次處理當日掛號時，最花時間的是哪一步？',
    }))
  })

  it('opens only the selected section editor', () => {
    const onUpdateSlot = vi.fn()
    const setEditingSlot = vi.fn()
    renderSlotList({
      editingSlot: 'slot-user:questions',
      onUpdateSlot,
      setEditingSlot,
      editForm: {
        rationale: slots[0].rationale || '',
        expectedContributions: slots[0].expectedContributions.join(', '),
        keyQuestions: slots[0].keyQuestionsToCover.join('\n'),
        priority: slots[0].priority,
      },
    })

    expect(screen.getByLabelText('每行輸入一個問題')).toBeInTheDocument()
    expect(screen.queryByLabelText('編輯訪談目的')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('使用逗號分隔每一項資訊')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    expect(onUpdateSlot).toHaveBeenCalledWith('slot-user')
  })

  it('keeps the primary assignment action beside progress', () => {
    const onAddProfile = vi.fn()
    renderSlotList({ onAddProfile })

    fireEvent.click(screen.getByRole('button', { name: '指派受訪者' }))
    expect(onAddProfile).toHaveBeenCalledWith('slot-user')
    expect(screen.getByRole('button', { name: '新增受訪者' })).toBeInTheDocument()
  })

  it('keeps assigned participants visible while role details are collapsed', () => {
    renderSlotList({
      profiles: [{
        id: 'profile-engineer',
        projectId: 'proj-1',
        slotId: 'slot-engineering',
        name: '王小明',
        roleTitle: '系統維運工程師',
        department: '資訊部',
        stakeholderType: 'internal',
        expertiseTags: [],
        knowledgeBoundaries: [],
        status: 'identified',
        interviewCount: 0,
        createdAt: '2026-07-14T00:00:00Z',
        updatedAt: '2026-07-14T00:00:00Z',
      }],
    })

    expect(screen.getByLabelText('掛號系統維運人員的受訪者')).toBeInTheDocument()
    expect(screen.getByText('王小明')).toBeInTheDocument()
    const details = document.getElementById('slot-details-slot-engineering')
    expect(details).toHaveAttribute('aria-hidden', 'true')
    expect(details).not.toHaveClass('slot-details-collapse--open')

    fireEvent.click(screen.getByRole('button', { name: '展開「掛號系統維運人員」詳情' }))
    fireEvent.click(screen.getByRole('button', { name: '收合「掛號系統維運人員」詳情' }))

    expect(screen.getByText('王小明')).toBeInTheDocument()
    expect(details).toHaveAttribute('aria-hidden', 'true')
    expect(details).not.toHaveClass('slot-details-collapse--open')
  })

  it('shows unassigned participants and allows assigning them to a role', () => {
    const onReassignProfile = vi.fn()
    renderSlotList({
      onReassignProfile,
      profiles: [{
        id: 'profile-unassigned',
        projectId: 'proj-1',
        name: '陳未分配',
        roleTitle: '候補受訪者',
        department: '門診',
        stakeholderType: 'internal',
        expertiseTags: [],
        knowledgeBoundaries: [],
        status: 'identified',
        interviewCount: 0,
        createdAt: '2026-07-14T00:00:00Z',
        updatedAt: '2026-07-14T00:00:00Z',
      }],
    })

    expect(screen.getByText('未隸屬任何角色的受訪者')).toBeInTheDocument()
    expect(screen.getByText('陳未分配')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('調整陳未分配的歸屬角色'), {
      target: { value: 'slot-user' },
    })
    expect(onReassignProfile).toHaveBeenCalledWith('profile-unassigned', 'slot-user')
  })

  it('groups reorder, skip, and delete actions in the more menu', () => {
    const onMoveSlot = vi.fn()
    const onSkipSlot = vi.fn()
    const onDeleteSlot = vi.fn()
    renderSlotList({ onMoveSlot, onSkipSlot, onDeleteSlot })

    const moreButton = screen.getByRole('button', { name: '更多「掛號櫃台人員」操作' })
    fireEvent.click(moreButton)
    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '上移角色' })).toBeDisabled()

    fireEvent.click(screen.getByRole('menuitem', { name: '下移角色' }))
    expect(onMoveSlot).toHaveBeenCalledWith('slot-user', 'down')

    fireEvent.click(moreButton)
    fireEvent.click(screen.getByRole('menuitem', { name: '跳過角色' }))
    expect(onSkipSlot).toHaveBeenCalledWith('slot-user')

    fireEvent.click(moreButton)
    fireEvent.click(screen.getByRole('menuitem', { name: '刪除角色' }))
    expect(onDeleteSlot).toHaveBeenCalledWith('slot-user')
  })
})
