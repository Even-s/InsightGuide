import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { StakeholderProfile, StakeholderSlot } from '@/api/projects'
import { ProfileCard } from './ProfileCard'

const mocks = vi.hoisted(() => ({
  listSessions: vi.fn(),
  listSeries: vi.fn(),
  listRounds: vi.fn(),
  createSeries: vi.fn(),
  createRound: vi.fn(),
  generateGuide: vi.fn(),
}))

vi.mock('@/api/interview', () => ({
  interviewAPI: { listSessions: mocks.listSessions },
}))

vi.mock('@/api/interviewRounds', () => ({
  interviewRoundsAPI: {
    listSeries: mocks.listSeries,
    listRounds: mocks.listRounds,
    createSeries: mocks.createSeries,
    createRound: mocks.createRound,
    generateGuide: mocks.generateGuide,
  },
}))

const profile: StakeholderProfile = {
  id: 'profile-1',
  projectId: 'project-1',
  name: '王小明',
  roleTitle: '櫃台人員',
  stakeholderType: 'actual_user',
  expertiseTags: [],
  knowledgeBoundaries: [],
  status: 'active',
  interviewCount: 0,
  createdAt: '2026-07-01T00:00:00Z',
  updatedAt: '2026-07-14T00:00:00Z',
}

const slots: StakeholderSlot[] = [
  {
    id: 'slot-frontline',
    projectId: 'project-1',
    roleCategory: 'user',
    roleLabel: '掛號櫃台人員',
    expectedContributions: [],
    keyQuestionsToCover: [],
    priority: 'required',
    minInterviews: 1,
    firstWave: true,
    status: 'assigned',
    orderIndex: 0,
    source: 'ai_suggested',
    profilesCount: 1,
    interviewsDone: 0,
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: '2026-07-14T00:00:00Z',
  },
  {
    id: 'slot-it',
    projectId: 'project-1',
    roleCategory: 'engineering',
    roleLabel: '資訊維運人員',
    expectedContributions: [],
    keyQuestionsToCover: [],
    priority: 'recommended',
    minInterviews: 1,
    firstWave: false,
    status: 'unassigned',
    orderIndex: 1,
    source: 'ai_suggested',
    profilesCount: 0,
    interviewsDone: 0,
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: '2026-07-14T00:00:00Z',
  },
]

describe('ProfileCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listSessions.mockResolvedValue({
      sessions: [
        {
          id: 'session-old',
          prepSessionId: 'prep-1',
          documentId: 'document-1',
          userId: 'user-1',
          projectId: 'project-1',
          stakeholderProfileId: 'profile-1',
          status: 'ended',
          endedAt: '2026-07-10T09:00:00Z',
          createdAt: '2026-07-10T08:00:00Z',
        },
        {
          id: 'session-latest',
          prepSessionId: 'prep-1',
          documentId: 'document-1',
          userId: 'user-1',
          projectId: 'project-1',
          stakeholderProfileId: 'profile-1',
          status: 'ended',
          endedAt: '2026-07-14T09:00:00Z',
          createdAt: '2026-07-14T08:00:00Z',
        },
      ],
      total: 2,
    })
    mocks.listSeries.mockResolvedValue([{
      id: 'series-1',
      projectId: 'project-1',
      stakeholderProfileId: 'profile-1',
      title: '掛號流程',
      topicKey: 'default',
      status: 'active',
      roundsCount: 1,
      createdAt: '2026-07-10T08:00:00Z',
      updatedAt: '2026-07-14T09:00:00Z',
    }])
    mocks.listRounds.mockResolvedValue([{
      id: 'round-1',
      seriesId: 'series-1',
      roundNumber: 1,
      objective: '了解掛號流程',
      generationMode: 'follow_up',
      sourceSessionIds: ['session-latest'],
      focusTopics: [],
      excludeCompletedQuestions: true,
      guideDocumentId: 'document-1',
      guideVersion: 1,
      cardCount: 5,
      status: 'completed',
      sessionIds: ['session-latest'],
      createdAt: '2026-07-14T08:00:00Z',
      updatedAt: '2026-07-14T09:00:00Z',
    }])
    mocks.createRound.mockResolvedValue({ id: 'round-2' })
    mocks.generateGuide.mockResolvedValue({ documentId: 'document-2' })
  })

  it('uses actual sessions to show the record entry when the profile counter is stale', async () => {
    render(
      <MemoryRouter initialEntries={['/projects/project-1']}>
        <Routes>
          <Route
            path="/projects/:projectId"
            element={(
              <ProfileCard
                profile={profile}
                projectId="project-1"
                guide={null}
                onDelete={vi.fn()}
                onShowGuideSettings={vi.fn()}
              />
            )}
          />
          <Route path="/sessions/:sessionId/insight-memo" element={<p>受訪者訪談紀錄</p>} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: '訪談紀錄（2）' }))

    expect(await screen.findByRole('heading', { name: '王小明的訪談規劃' })).toBeInTheDocument()
    const roundDialog = screen.getByRole('dialog', { name: '訪談輪次' })
    expect(roundDialog.parentElement).toBe(document.body)
    expect(roundDialog).toHaveClass('z-[100]')
    expect(screen.getByText('掛號流程 · 第 1 輪')).toBeInTheDocument()
  })

  it('does not show next-round creation on an assigned participant card', async () => {
    render(
      <MemoryRouter initialEntries={['/projects/project-1']}>
        <Routes>
          <Route
            path="/projects/:projectId"
            element={(
              <ProfileCard
                profile={profile}
                projectId="project-1"
                guide={{
                  document_id: 'document-1',
                  prep_session_id: 'prep-1',
                  themes: [],
                  card_count: 5,
                  status: 'ready',
                  is_frozen: true,
                }}
                onDelete={vi.fn()}
                onShowGuideSettings={vi.fn()}
              />
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: '查看目前大綱' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '開始下一輪訪談' })).not.toBeInTheDocument()
  })

  it('lets users reassign the participant to another role or unassigned area', async () => {
    const onReassign = vi.fn()
    render(
      <MemoryRouter initialEntries={['/projects/project-1']}>
        <Routes>
          <Route
            path="/projects/:projectId"
            element={(
              <ProfileCard
                profile={{ ...profile, slotId: 'slot-frontline' }}
                projectId="project-1"
                guide={null}
                slots={slots}
                onDelete={vi.fn()}
                onReassign={onReassign}
                onShowGuideSettings={vi.fn()}
              />
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    const roleSelect = await screen.findByLabelText('調整王小明的歸屬角色')
    fireEvent.change(roleSelect, {
      target: { value: 'slot-it' },
    })
    fireEvent.change(roleSelect, {
      target: { value: '' },
    })

    expect(onReassign).toHaveBeenNthCalledWith(1, 'profile-1', 'slot-it')
    expect(onReassign).toHaveBeenNthCalledWith(2, 'profile-1', null)
  })
})
