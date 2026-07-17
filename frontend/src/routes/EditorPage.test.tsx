import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { DocumentStatus } from '@/api/documents'
import type { Document } from '@/types/document'
import EditorPage from './EditorPage'

vi.mock('@/api/documents', () => ({
  documentsAPI: {
    getDocument: vi.fn().mockResolvedValue({ id: 'doc-1', project_id: 'proj-1' }),
    getDocumentStatus: vi.fn().mockResolvedValue({ id: 'doc-1', status: 'analyzed', costUsd: 0, aiUsage: {} }),
  },
}))

vi.mock('@/api/questionCards', () => ({
  questionCardsAPI: {
    getDocumentCards: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('@/api/interviewRounds', () => ({
  interviewRoundsAPI: {
    getRound: vi.fn(),
    listRounds: vi.fn(),
    listSeries: vi.fn(),
    createSeries: vi.fn(),
    createRound: vi.fn(),
    generateGuide: vi.fn(),
    continueSession: vi.fn(),
  },
}))

vi.mock('@/api/projects', () => ({
  listStakeholders: vi.fn(),
}))

vi.mock('@/api/interview', () => ({
  interviewAPI: {
    getSession: vi.fn(),
    listSessions: vi.fn(),
  },
}))

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: {
        documentId: 'doc-1',
        status: 'ready',
        interviewObjective: 'Test objective',
        priorityOrder: [1, 2],
        priorityReasoning: null,
        themes: [
          {
            id: 'theme-1',
            themeNumber: 1,
            title: '訪談開場',
            rationale: 'Test rationale',
            brdMapping: [],
            priority: 1,
            estimatedMinutes: 5,
            orderIndex: 0,
            isRequired: true,
            isEnabled: true,
            userNotes: null,
            cards: [
              { id: 'card-1', focusText: 'Focus 1', questionText: 'Question 1', questionType: 'clarification', importance: 'must', suggestedFollowup: '', expectedAnswerElements: [], brdMapping: [], estimatedSeconds: 60, orderIndex: 0, status: 'pending', confidence: null, createdBy: 'ai' },
            ],
          },
        ],
        totalCards: 1,
      },
    }),
  },
}))

function renderEditorPage(documentId = 'doc-1') {
  return render(
    <MemoryRouter initialEntries={[`/editor/${documentId}`]}>
      <Routes>
        <Route path="/editor/:documentId" element={<EditorPage />} />
        <Route path="/interview/session/:sessionId" element={<p>已恢復訪談</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('EditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading spinner initially', () => {
    renderEditorPage()
    expect(screen.getByText(/載入/)).toBeInTheDocument()
  })

  it('renders theme sidebar after loading', async () => {
    renderEditorPage()
    await waitFor(() => {
      expect(screen.getByText('訪談開場')).toBeInTheDocument()
    })
  })

  it('shows document analysis error when status is failed', async () => {
    const { documentsAPI } = await import('@/api/documents')
    vi.mocked(documentsAPI.getDocumentStatus).mockResolvedValueOnce({
      id: 'doc-1',
      status: 'failed',
      message: 'Analysis failed due to invalid format',
      costUsd: 0,
      aiUsage: {},
    } as DocumentStatus)

    renderEditorPage()
    await waitFor(() => {
      expect(screen.getByText(/Analysis failed/)).toBeInTheDocument()
    })
  })

  it('shows analysis progress when document is processing', async () => {
    const { documentsAPI } = await import('@/api/documents')
    vi.mocked(documentsAPI.getDocumentStatus).mockResolvedValueOnce({
      id: 'doc-1',
      status: 'analyzing',
      costUsd: 0,
      aiUsage: {},
    } as DocumentStatus)

    renderEditorPage()
    await waitFor(() => {
      expect(screen.getByText('正在分析文件')).toBeInTheDocument()
    })
  })

  it('provides an interview-record entry for every ended session', async () => {
    const apiClient = (await import('@/api/client')).default
    renderEditorPage()
    await screen.findByText('訪談開場')

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        sessions: [{
          id: 'session-1',
          status: 'ended',
          startedAt: '2026-07-14T08:00:00Z',
          endedAt: '2026-07-14T09:00:00Z',
          createdAt: '2026-07-14T08:00:00Z',
        }],
      },
    })

    fireEvent.click(screen.getByRole('button', { name: '訪談紀錄' }))

    expect(await screen.findByRole('heading', { name: '訪談紀錄' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: '訪談紀錄' })).toHaveLength(2)
  })

  it('switches between each round outline from tabs in the editor', async () => {
    const { documentsAPI } = await import('@/api/documents')
    const { interviewRoundsAPI } = await import('@/api/interviewRounds')
    const rounds = [
      {
        id: 'round-1', seriesId: 'series-1', roundNumber: 1, generationMode: 'new_scope',
        sourceSessionIds: [], focusTopics: [], excludeCompletedQuestions: true,
        guideDocumentId: 'doc-1', guideVersion: 1, cardCount: 5, status: 'completed',
        sessionIds: ['session-1'], createdAt: '2026-07-10T08:00:00Z', updatedAt: '2026-07-10T09:00:00Z',
      },
      {
        id: 'round-2', seriesId: 'series-1', roundNumber: 2, generationMode: 'follow_up',
        sourceSessionIds: ['session-1'], focusTopics: [], excludeCompletedQuestions: true,
        guideDocumentId: 'doc-2', guideVersion: 2, cardCount: 3, status: 'ready',
        sessionIds: [], createdAt: '2026-07-11T08:00:00Z', updatedAt: '2026-07-11T08:00:00Z',
      },
    ]
    vi.mocked(documentsAPI.getDocument).mockImplementation(async (id) => ({
      id,
      project_id: 'proj-1',
      interview_round_id: id === 'doc-2' ? 'round-2' : 'round-1',
      guide_version: id === 'doc-2' ? 2 : 1,
      is_frozen: id === 'doc-1',
    } as Document))
    vi.mocked(interviewRoundsAPI.getRound).mockImplementation(async (id) => (
      rounds.find((round) => round.id === id)!
    ))
    vi.mocked(interviewRoundsAPI.listRounds).mockResolvedValue(rounds)

    renderEditorPage('doc-2')

    const secondRoundTab = await screen.findByRole('tab', { name: /第 2 輪/ })
    expect(secondRoundTab).toHaveAttribute('aria-selected', 'true')
    expect(secondRoundTab).toHaveTextContent('V2 · 3 題')
    expect(screen.getByRole('heading', { name: '準備模式' })).toBeInTheDocument()
    expect(screen.getByText(/第 2 輪 · 1 個單元/)).toBeInTheDocument()
    expect(secondRoundTab.closest('header')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: /第 1 輪/ }))

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /第 1 輪/ })).toHaveAttribute('aria-selected', 'true')
    })
    expect(documentsAPI.getDocument).toHaveBeenCalledWith('doc-1')
  })

  it('creates a new interview directly from the round tabs', async () => {
    const { documentsAPI } = await import('@/api/documents')
    const { interviewRoundsAPI } = await import('@/api/interviewRounds')
    const { listStakeholders } = await import('@/api/projects')
    const { interviewAPI } = await import('@/api/interview')
    const currentRound = {
      id: 'round-1',
      seriesId: 'series-1',
      roundNumber: 1,
      objective: '了解掛號流程',
      generationMode: 'new_scope',
      sourceSessionIds: [],
      focusTopics: [],
      excludeCompletedQuestions: true,
      guideDocumentId: 'doc-1',
      guideVersion: 1,
      cardCount: 5,
      status: 'completed',
      sessionIds: ['session-1'],
      createdAt: '2026-07-10T08:00:00Z',
      updatedAt: '2026-07-10T09:00:00Z',
    }
    vi.mocked(documentsAPI.getDocument).mockImplementation(async (id) => ({
      id,
      project_id: 'proj-1',
      stakeholder_profile_id: 'profile-1',
      interview_round_id: 'round-1',
      guide_version: 1,
      is_frozen: true,
    } as Document))
    vi.mocked(interviewRoundsAPI.getRound).mockResolvedValue(currentRound)
    vi.mocked(interviewRoundsAPI.listRounds).mockResolvedValue([currentRound])
    vi.mocked(interviewRoundsAPI.listSeries).mockResolvedValue([{
      id: 'series-1',
      projectId: 'proj-1',
      stakeholderProfileId: 'profile-1',
      title: '掛號流程',
      topicKey: 'default',
      status: 'active',
      roundsCount: 1,
      createdAt: '2026-07-10T08:00:00Z',
      updatedAt: '2026-07-10T09:00:00Z',
    }])
    vi.mocked(listStakeholders).mockResolvedValue([{
      id: 'profile-1',
      projectId: 'proj-1',
      assignedSlotIds: ['slot-frontline'],
      primarySlotId: 'slot-frontline',
      name: '王小明',
      roleTitle: '掛號櫃台人員',
      stakeholderType: 'actual_user',
      expertiseTags: [],
      knowledgeBoundaries: [],
      status: 'interviewed',
      interviewCount: 1,
      createdAt: '2026-07-01T00:00:00Z',
      updatedAt: '2026-07-10T09:00:00Z',
    }])
    vi.mocked(interviewAPI.listSessions).mockResolvedValue({
      sessions: [{
        id: 'session-1',
        prepSessionId: 'prep-1',
        documentId: 'doc-1',
        userId: 'user-1',
        projectId: 'proj-1',
        stakeholderProfileId: 'profile-1',
        interviewRoundId: 'round-1',
        status: 'ended',
        endedAt: '2026-07-10T09:00:00Z',
        createdAt: '2026-07-10T08:00:00Z',
      }],
      total: 1,
    })
    vi.mocked(interviewRoundsAPI.createRound).mockResolvedValue({
      ...currentRound,
      id: 'round-2',
      roundNumber: 2,
      guideDocumentId: undefined,
      guideVersion: undefined,
      cardCount: 0,
      status: 'draft',
      sessionIds: [],
    })
    vi.mocked(interviewRoundsAPI.generateGuide).mockResolvedValue({
      documentId: 'doc-2',
      prepSessionId: 'prep-2',
      seriesId: 'series-1',
      roundId: 'round-2',
      roundNumber: 2,
      cardCount: 4,
      status: 'ready',
      themes: [],
    })

    renderEditorPage('doc-1')

    fireEvent.click(await screen.findByRole('button', { name: '新增訪談' }))
    expect(await screen.findByRole('heading', { name: '王小明的訪談規劃' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '訪談主題' })).toHaveValue('series-1')
    fireEvent.change(screen.getByPlaceholderText(/釐清第一次訪談/), {
      target: { value: '確認第二輪例外掛號流程' },
    })
    fireEvent.click(screen.getByRole('button', { name: '建立並預覽大綱' }))

    await waitFor(() => {
      expect(interviewRoundsAPI.createRound).toHaveBeenCalledWith(
        'series-1',
        expect.objectContaining({ objective: '確認第二輪例外掛號流程' }),
      )
    })
    expect(interviewRoundsAPI.generateGuide).toHaveBeenCalledWith(
      'round-2',
      expect.objectContaining({ durationMinutes: 30 }),
    )
  })

  it('resumes the unfinished session from its interview round', async () => {
    const { documentsAPI } = await import('@/api/documents')
    const { interviewRoundsAPI } = await import('@/api/interviewRounds')
    const { interviewAPI } = await import('@/api/interview')
    const currentRound = {
      id: 'round-1',
      seriesId: 'series-1',
      roundNumber: 1,
      objective: '了解掛號流程',
      generationMode: 'new_scope',
      sourceSessionIds: [],
      focusTopics: [],
      excludeCompletedQuestions: true,
      guideDocumentId: 'doc-1',
      guideVersion: 1,
      cardCount: 5,
      status: 'interviewing',
      sessionIds: ['session-active'],
      createdAt: '2026-07-10T08:00:00Z',
      updatedAt: '2026-07-10T09:00:00Z',
    }
    vi.mocked(documentsAPI.getDocument).mockResolvedValue({
      id: 'doc-1',
      project_id: 'proj-1',
      stakeholder_profile_id: 'profile-1',
      interview_round_id: 'round-1',
      guide_version: 1,
      is_frozen: false,
    } as Document)
    vi.mocked(interviewRoundsAPI.getRound).mockResolvedValue(currentRound)
    vi.mocked(interviewRoundsAPI.listRounds).mockResolvedValue([currentRound])
    vi.mocked(interviewAPI.listSessions).mockResolvedValue({
      sessions: [{
        id: 'session-active',
        prepSessionId: 'prep-1',
        documentId: 'doc-1',
        userId: 'user-1',
        projectId: 'proj-1',
        stakeholderProfileId: 'profile-1',
        interviewRoundId: 'round-1',
        status: 'paused',
        createdAt: '2026-07-10T08:00:00Z',
      }],
      total: 1,
    })

    renderEditorPage('doc-1')

    const resumeButton = await screen.findByRole('button', { name: '繼續第 1 輪訪談' })
    const actionArea = screen.getByLabelText('準備模式操作')
    const roundTab = screen.getByRole('tab', { name: /第 1 輪/ })
    const actionButtons = Array.from(actionArea.querySelectorAll('button'))
    expect(actionArea).toContainElement(resumeButton)
    expect(roundTab).not.toContainElement(resumeButton)
    expect(actionButtons).toHaveLength(3)
    actionButtons.forEach((button) => {
      expect(button).toHaveClass('h-9', 'rounded-lg', 'text-sm', 'font-medium')
    })
    expect(resumeButton).toHaveTextContent('繼續該輪訪談')
    expect(resumeButton).toHaveClass('bg-sage-500', 'text-white', 'hover:bg-sage-400')
    expect(resumeButton).not.toHaveClass('bg-sage-600', 'hover:bg-sage-700')
    fireEvent.click(resumeButton)

    expect(await screen.findByText('已恢復訪談')).toBeInTheDocument()
  })

  it('keeps the continue action available when the session list request fails', async () => {
    const { documentsAPI } = await import('@/api/documents')
    const { interviewRoundsAPI } = await import('@/api/interviewRounds')
    const { interviewAPI } = await import('@/api/interview')
    const currentRound = {
      id: 'round-1',
      seriesId: 'series-1',
      roundNumber: 1,
      objective: '了解掛號流程',
      generationMode: 'new_scope',
      sourceSessionIds: [],
      focusTopics: [],
      excludeCompletedQuestions: true,
      guideDocumentId: 'doc-1',
      guideVersion: 1,
      cardCount: 5,
      status: 'interviewing',
      sessionIds: ['session-active'],
      createdAt: '2026-07-10T08:00:00Z',
      updatedAt: '2026-07-10T09:00:00Z',
    }
    vi.mocked(documentsAPI.getDocument).mockResolvedValue({
      id: 'doc-1',
      project_id: 'proj-1',
      stakeholder_profile_id: 'profile-1',
      interview_round_id: 'round-1',
      guide_version: 1,
      is_frozen: false,
    } as Document)
    vi.mocked(interviewRoundsAPI.getRound).mockResolvedValue(currentRound)
    vi.mocked(interviewRoundsAPI.listRounds).mockResolvedValue([currentRound])
    vi.mocked(interviewAPI.listSessions).mockRejectedValue(new Error('Network Error'))
    vi.mocked(interviewAPI.getSession).mockResolvedValue({
      id: 'session-active',
      prepSessionId: 'prep-1',
      documentId: 'doc-1',
      userId: 'user-1',
      projectId: 'proj-1',
      stakeholderProfileId: 'profile-1',
      interviewRoundId: 'round-1',
      status: 'paused',
      createdAt: '2026-07-10T08:00:00Z',
    })

    renderEditorPage('doc-1')

    const resumeButton = await screen.findByRole('button', { name: '繼續第 1 輪訪談' })
    fireEvent.click(resumeButton)

    expect(await screen.findByText('已恢復訪談')).toBeInTheDocument()
    expect(interviewAPI.getSession).toHaveBeenCalledWith('session-active')
  })

  it('continues an ended round in a new session that carries previous progress', async () => {
    const { documentsAPI } = await import('@/api/documents')
    const { interviewRoundsAPI } = await import('@/api/interviewRounds')
    const { interviewAPI } = await import('@/api/interview')
    const currentRound = {
      id: 'round-1',
      seriesId: 'series-1',
      roundNumber: 1,
      objective: '了解掛號流程',
      generationMode: 'new_scope',
      sourceSessionIds: [],
      focusTopics: [],
      excludeCompletedQuestions: true,
      guideDocumentId: 'doc-1',
      guideVersion: 1,
      cardCount: 5,
      status: 'completed',
      sessionIds: ['session-ended'],
      createdAt: '2026-07-10T08:00:00Z',
      updatedAt: '2026-07-10T09:00:00Z',
    }
    vi.mocked(documentsAPI.getDocument).mockResolvedValue({
      id: 'doc-1',
      project_id: 'proj-1',
      stakeholder_profile_id: 'profile-1',
      interview_round_id: 'round-1',
      guide_version: 1,
      is_frozen: true,
    } as Document)
    vi.mocked(interviewRoundsAPI.getRound).mockResolvedValue(currentRound)
    vi.mocked(interviewRoundsAPI.listRounds).mockResolvedValue([currentRound])
    vi.mocked(interviewAPI.listSessions).mockResolvedValue({
      sessions: [{
        id: 'session-ended',
        prepSessionId: 'prep-1',
        documentId: 'doc-1',
        userId: 'user-1',
        projectId: 'proj-1',
        stakeholderProfileId: 'profile-1',
        interviewRoundId: 'round-1',
        status: 'ended',
        createdAt: '2026-07-10T08:00:00Z',
      }],
      total: 1,
    })
    vi.mocked(interviewRoundsAPI.continueSession).mockResolvedValue({
      id: 'session-continued',
      prepSessionId: 'prep-1',
      documentId: 'doc-1',
      userId: 'user-1',
      projectId: 'proj-1',
      stakeholderProfileId: 'profile-1',
      interviewRoundId: 'round-1',
      continuedFromSessionId: 'session-ended',
      status: 'idle',
      createdAt: '2026-07-11T08:00:00Z',
    })

    renderEditorPage('doc-1')

    fireEvent.click(await screen.findByRole('button', { name: '繼續第 1 輪訪談' }))

    await waitFor(() => {
      expect(interviewRoundsAPI.continueSession).toHaveBeenCalledWith(
        'round-1',
        'session-ended',
      )
    })
    expect(await screen.findByText('已恢復訪談')).toBeInTheDocument()
  })
})
