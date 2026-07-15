import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { StakeholderProfile } from '@/api/projects'
import { ProfileCard } from './ProfileCard'

const mocks = vi.hoisted(() => ({
  listSessions: vi.fn(),
}))

vi.mock('@/api/interview', () => ({
  interviewAPI: { listSessions: mocks.listSessions },
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

    fireEvent.click(await screen.findByRole('button', { name: '訪談紀錄' }))

    expect(await screen.findByText('受訪者訪談紀錄')).toBeInTheDocument()
  })
})
