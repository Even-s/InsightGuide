import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { refineStakeholderSlotDraft, voiceToStakeholderSlotDraft } from '@/api/projects'
import { useProjectData } from '@/hooks/useProjectData'
import { useSlotManagement } from '@/hooks/useSlotManagement'
import ProjectDetailPage from './ProjectDetailPage'

vi.mock('@/api/projects', async () => {
  const actual = await vi.importActual<typeof import('@/api/projects')>('@/api/projects')
  return {
    ...actual,
    refineStakeholderSlotDraft: vi.fn(),
    voiceToStakeholderSlotDraft: vi.fn(),
  }
})
vi.mock('@/hooks/useProjectData', () => ({ useProjectData: vi.fn() }))
vi.mock('@/hooks/useSlotManagement', () => ({ useSlotManagement: vi.fn() }))

describe('ProjectDetailPage add-role form', () => {
  let slotManagementResult: ReturnType<typeof useSlotManagement>

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  beforeEach(() => {
    vi.mocked(useProjectData).mockReturnValue({
      dashboard: {
        project: {
          id: 'proj-1',
          userId: 'user-1',
          title: '測試專案',
          description: '測試說明',
          status: 'active',
          createdAt: '2026-07-14T00:00:00Z',
          updatedAt: '2026-07-14T00:00:00Z',
        },
        stakeholderPlan: {
          total_slots: 0,
          completed_slots: 0,
          progress_percentage: 0,
          first_wave_total: 0,
          first_wave_completed: 0,
          generation_source: 'user_created',
          slots: [],
        },
        interviewProgress: {
          total_sessions: 0,
          completed_sessions: 0,
          total_profiles: 0,
          interviewed_profiles: 0,
        },
      },
      plan: {
        slots: [],
        profiles: [],
        summary: {
          total_slots: 0,
          completed_slots: 0,
          progress_percentage: 0,
          first_wave_total: 0,
          first_wave_completed: 0,
          generation_source: 'user_created',
          slots: [],
        },
      },
      loading: false,
      guideStatuses: {},
      setGuideStatuses: vi.fn(),
      loadData: vi.fn(),
    })

    slotManagementResult = {
      editingSlot: null,
      setEditingSlot: vi.fn(),
      editForm: { rationale: '', expectedContributions: '', keyQuestions: '', priority: 'required' },
      setEditForm: vi.fn(),
      slotActionError: null,
      setSlotActionError: vi.fn(),
      showAddSlot: true,
      setShowAddSlot: vi.fn(),
      newSlotLabel: '',
      setNewSlotLabel: vi.fn(),
      newSlotCategory: 'business',
      setNewSlotCategory: vi.fn(),
      newSlotRationale: '',
      setNewSlotRationale: vi.fn(),
      newSlotPriority: 'required',
      setNewSlotPriority: vi.fn(),
      newSlotMinInterviews: 1,
      setNewSlotMinInterviews: vi.fn(),
      newSlotFirstWave: false,
      setNewSlotFirstWave: vi.fn(),
      newSlotExpectedContributions: '',
      setNewSlotExpectedContributions: vi.fn(),
      newSlotKeyQuestions: '',
      setNewSlotKeyQuestions: vi.fn(),
      handleSkipSlot: vi.fn(),
      handleUnskipSlot: vi.fn(),
      handleMoveSlot: vi.fn(),
      handleDeleteSlot: vi.fn(),
      handleAddSlot: vi.fn(),
      handleDeleteProfile: vi.fn(),
      handleReassignProfile: vi.fn(),
      handleUpdateSlot: vi.fn(),
    }
    vi.mocked(useSlotManagement).mockReturnValue(slotManagementResult)
  })

  it('shows the same planning fields used by stakeholder cards', () => {
    render(
      <MemoryRouter initialEntries={['/projects/proj-1']}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByLabelText('角色名稱')).toBeInTheDocument()
    expect(screen.getByLabelText('角色類型')).toBeInTheDocument()
    expect(screen.getByLabelText('重要性')).toBeInTheDocument()
    expect(screen.getByLabelText('最低訪談場次')).toBeInTheDocument()
    expect(screen.getByText('第一輪優先')).toBeInTheDocument()
    expect(screen.getByLabelText('訪談目的')).toBeInTheDocument()
    expect(screen.getByLabelText('預期取得的資訊')).toBeInTheDocument()
    expect(screen.getByLabelText('關鍵問題')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '口說填入' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'AI 補充／優化' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '新增角色' })).toBeDisabled()
  })

  it('applies the AI-refined draft to every add-role field without creating it', async () => {
    const draft = {
      role_category: 'operations',
      role_label: '門診掛號櫃台人員',
      rationale: '了解每日掛號流程、常見例外與現場限制。',
      expected_contributions: ['每日掛號流程', '常見例外', '現場限制'],
      key_questions_to_cover: [
        '最近一次遇到掛號尖峰時，哪個步驟最容易塞車？',
        '上次處理重複掛號時，你怎麼確認資料？',
      ],
      priority: 'recommended',
      min_interviews: 2,
      first_wave: true,
    }
    vi.mocked(refineStakeholderSlotDraft).mockResolvedValue({ draft })
    vi.mocked(useSlotManagement).mockReturnValue({
      ...slotManagementResult,
      newSlotLabel: '櫃台人員',
      newSlotCategory: 'operations',
      newSlotPriority: 'recommended',
      newSlotMinInterviews: 2,
      newSlotFirstWave: true,
    })

    render(
      <MemoryRouter initialEntries={['/projects/proj-1']}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'AI 補充／優化' }))

    await waitFor(() => {
      expect(refineStakeholderSlotDraft).toHaveBeenCalledWith('proj-1', {
        role_category: 'operations',
        role_label: '櫃台人員',
        rationale: '',
        expected_contributions: [],
        key_questions_to_cover: [],
        priority: 'recommended',
        min_interviews: 2,
        first_wave: true,
      })
    })
    expect(slotManagementResult.setNewSlotLabel).toHaveBeenCalledWith(draft.role_label)
    expect(slotManagementResult.setNewSlotRationale).toHaveBeenCalledWith(draft.rationale)
    expect(slotManagementResult.setNewSlotExpectedContributions).toHaveBeenCalledWith(
      '每日掛號流程, 常見例外, 現場限制',
    )
    expect(slotManagementResult.setNewSlotKeyQuestions).toHaveBeenCalledWith(
      draft.key_questions_to_cover.join('\n'),
    )
    expect(slotManagementResult.handleAddSlot).not.toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('AI 已補充並優化內容，請確認後再新增。')
  })

  it('records a spoken description and applies the parsed role draft', async () => {
    const draft = {
      role_category: 'user',
      role_label: '病患或代掛號家屬',
      rationale: '了解線上預約的實際操作經驗與障礙。',
      expected_contributions: ['預約流程', '操作困難', '通知需求'],
      key_questions_to_cover: ['最近一次線上掛號時，你從哪裡開始操作？'],
      priority: 'required',
      min_interviews: 3,
      first_wave: true,
    }
    vi.mocked(voiceToStakeholderSlotDraft).mockResolvedValue({
      transcript: '加入病患與幫家人掛號的人，了解線上操作會卡在哪裡。',
      draft,
    })

    const stopTrack = vi.fn()
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }),
      },
    })

    class MockMediaRecorder {
      static isTypeSupported = vi.fn(() => true)
      state = 'inactive'
      mimeType = 'audio/webm'
      ondataavailable: ((event: { data: Blob }) => void) | null = null
      onerror: (() => void) | null = null
      onstop: (() => void) | null = null

      start() {
        this.state = 'recording'
      }

      stop() {
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob([new Uint8Array(1500)]) })
        this.onstop?.()
      }
    }
    vi.stubGlobal('MediaRecorder', MockMediaRecorder)

    render(
      <MemoryRouter initialEntries={['/projects/proj-1']}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: '口說填入' }))
    const stopButton = await screen.findByRole('button', { name: '停止並填入' })
    fireEvent.click(stopButton)

    await waitFor(() => expect(voiceToStakeholderSlotDraft).toHaveBeenCalled())
    expect(slotManagementResult.setNewSlotLabel).toHaveBeenCalledWith(draft.role_label)
    expect(slotManagementResult.setNewSlotCategory).toHaveBeenCalledWith('user')
    expect(slotManagementResult.setNewSlotMinInterviews).toHaveBeenCalledWith(3)
    expect(stopTrack).toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('已從語音填入草稿')
  })
})
