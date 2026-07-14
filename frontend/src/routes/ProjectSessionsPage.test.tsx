import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { deleteProject } from '@/api/projects'
import ProjectSessionsPage from './ProjectSessionsPage'

vi.mock('@/api/projects', () => ({
  listProjects: vi.fn().mockResolvedValue({
    projects: [
      {
        id: 'proj-1',
        userId: 'user-1',
        title: '測試專案',
        description: '測試描述',
        status: 'active',
        createdAt: '2026-07-14T00:00:00Z',
        updatedAt: '2026-07-14T00:00:00Z',
      },
    ],
    total: 1,
  }),
  getStakeholderPlan: vi.fn().mockResolvedValue(null),
  deleteProject: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { sessions: [] } }),
  },
}))

describe('ProjectSessionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('deletes a project after destructive-action confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(
      <MemoryRouter>
        <ProjectSessionsPage />
      </MemoryRouter>,
    )

    const deleteButton = await screen.findByRole('button', { name: '刪除專案「測試專案」' })
    fireEvent.click(deleteButton)

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('無法復原'))
    await waitFor(() => expect(deleteProject).toHaveBeenCalledWith('proj-1'))
    await waitFor(() => expect(screen.queryByText('測試專案')).not.toBeInTheDocument())
  })

  it('keeps the project when deletion is cancelled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    render(
      <MemoryRouter>
        <ProjectSessionsPage />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: '刪除專案「測試專案」' }))

    expect(deleteProject).not.toHaveBeenCalled()
    expect(screen.getByText('測試專案')).toBeInTheDocument()
  })

  it('uses one clear project-management action instead of duplicate controls', async () => {
    render(
      <MemoryRouter>
        <ProjectSessionsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: '管理專案' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '開始訪談' })).not.toBeInTheDocument()
    expect(screen.queryByTitle('管理專案')).not.toBeInTheDocument()
  })

  it('provides a direct new-project action', async () => {
    render(
      <MemoryRouter>
        <ProjectSessionsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: '新增專案' })).toBeInTheDocument()
  })
})
