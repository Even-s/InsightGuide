import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StakeholdersPage from './StakeholdersPage'

const mockLoadData = vi.fn()
const mockUseProjectData = vi.fn()
const mockUpdateStakeholderProfileSlots = vi.fn()

vi.mock('@/hooks/useProjectData', () => ({
  useProjectData: (...args: unknown[]) => mockUseProjectData(...args),
}))

vi.mock('@/api/projects', () => ({
  updateStakeholderProfileSlots: (...args: unknown[]) => mockUpdateStakeholderProfileSlots(...args),
}))

const dashboard = {
  project: {
    id: 'proj-1',
    title: '網上預約掛號系統',
  },
}

const basePlan = {
  slots: [
    {
      id: 'slot-frontline',
      roleLabel: '掛號櫃台人員',
      roleCategory: 'use',
      status: 'assigned',
    },
    {
      id: 'slot-manager',
      roleLabel: '掛號業務主管',
      roleCategory: 'manage',
      status: 'assigned',
    },
  ],
  profiles: [
    {
      id: 'profile-1',
      name: '王小明',
      roleTitle: '門診櫃台組長',
      department: '門診櫃檯',
      stakeholderType: 'operations',
      expertiseTags: ['掛號流程'],
      knowledgeBoundaries: [],
      status: 'pending',
      interviewCount: 0,
      assignedSlotIds: ['slot-frontline'],
      primarySlotId: 'slot-frontline',
    },
    {
      id: 'profile-2',
      name: '陳小美',
      roleTitle: '護理師',
      department: '門診',
      stakeholderType: 'frontline',
      expertiseTags: [],
      knowledgeBoundaries: [],
      status: 'pending',
      interviewCount: 0,
      assignedSlotIds: [],
      primarySlotId: null,
    },
  ],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/projects/proj-1/stakeholders']}>
      <Routes>
        <Route path="/projects/:projectId/stakeholders" element={<StakeholdersPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('StakeholdersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseProjectData.mockReturnValue({
      dashboard,
      plan: basePlan,
      loading: false,
      loadData: mockLoadData,
    })
  })

  it('shows profiles from a person-centric view and highlights unassigned profiles', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: '受訪者管理' })).toBeInTheDocument()
    expect(screen.getByText('網上預約掛號系統 · 2 位受訪者 · 1 位未隸屬角色')).toBeInTheDocument()
    expect(screen.getByText('王小明')).toBeInTheDocument()
    expect(screen.getByText('陳小美')).toBeInTheDocument()
    expect(screen.getByText('未隸屬任何角色')).toBeInTheDocument()
  })

  it('updates role membership through the profile-slot bridge endpoint', async () => {
    const user = userEvent.setup()
    mockUpdateStakeholderProfileSlots.mockResolvedValue(undefined)

    renderPage()

    await user.click(screen.getAllByRole('button', { name: '+ 掛號業務主管' })[0])

    await waitFor(() => {
      expect(mockUpdateStakeholderProfileSlots).toHaveBeenCalledWith('profile-1', {
        slot_ids: ['slot-frontline', 'slot-manager'],
        primary_slot_id: 'slot-frontline',
      })
    })
    expect(mockLoadData).toHaveBeenCalled()
  })
})
