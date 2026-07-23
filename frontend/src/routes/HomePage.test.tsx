import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HomePage from './HomePage'
import { createDemoSession, listDemoTemplates } from '@/api/demoSessions'

vi.mock('@/api/demoSessions', () => ({
  listDemoTemplates: vi.fn(),
  createDemoSession: vi.fn(),
}))

const templates = [
  { id: 'current-process', title: '現況流程探索', description: '了解現況流程', estimatedMinutes: 9, themeCount: 3, questionCount: 6 },
  { id: 'pain-and-needs', title: '痛點與需求探索', description: '探索痛點需求', estimatedMinutes: 9, themeCount: 3, questionCount: 6 },
  { id: 'new-system', title: '新系統需求確認', description: '確認系統需求', estimatedMinutes: 9, themeCount: 3, questionCount: 6 },
]

function renderHome() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects/new" element={<div>新建專案頁面</div>} />
        <Route path="/projects" element={<div>專案管理頁面</div>} />
        <Route path="/interview/session/:sessionId" element={<div>既有訪談介面</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  beforeEach(() => {
    vi.mocked(listDemoTemplates).mockResolvedValue(templates)
    vi.mocked(createDemoSession).mockResolvedValue({
      templateId: 'current-process', projectId: 'proj_demo', stakeholderProfileId: 'profile_demo',
      prepSessionId: 'doc_demo', documentId: 'doc_demo', sessionId: 'session_demo',
      expiresAt: '2026-07-24T00:00:00', interviewPath: '/interview/session/session_demo',
    })
  })

  it('shows separate new-project and project-management entrances', async () => {
    renderHome()
    await screen.findByRole('button', { name: '使用現況流程探索開始 Demo' })

    expect(screen.getByRole('button', { name: '新建專案' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '管理專案' })).toBeInTheDocument()
  })

  it('opens the dedicated new-project page', async () => {
    renderHome()
    await screen.findByRole('button', { name: '使用現況流程探索開始 Demo' })

    fireEvent.click(screen.getByRole('button', { name: '新建專案' }))
    expect(screen.getByText('新建專案頁面')).toBeInTheDocument()
  })

  it('opens project management', async () => {
    renderHome()
    await screen.findByRole('button', { name: '使用現況流程探索開始 Demo' })

    fireEvent.click(screen.getByRole('button', { name: '管理專案' }))
    expect(screen.getByText('專案管理頁面')).toBeInTheDocument()
  })

  it('shows all public demo templates', async () => {
    renderHome()

    expect(await screen.findByRole('button', { name: '使用現況流程探索開始 Demo' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '使用痛點與需求探索開始 Demo' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '使用新系統需求確認開始 Demo' })).toBeInTheDocument()
  })

  it('creates an isolated demo session and enters the existing interview route', async () => {
    renderHome()

    fireEvent.click(await screen.findByRole('button', { name: '使用現況流程探索開始 Demo' }))

    expect(await screen.findByText('既有訪談介面')).toBeInTheDocument()
    expect(createDemoSession).toHaveBeenCalledWith('current-process')
  })
})
