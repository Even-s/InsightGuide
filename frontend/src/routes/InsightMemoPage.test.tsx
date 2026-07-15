import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { InsightMemo } from '@/api/projects'
import InsightMemoPage from './InsightMemoPage'

const mocks = vi.hoisted(() => ({
  getInsightMemo: vi.fn(),
  generateInsightMemo: vi.fn(),
  apiGet: vi.fn(),
}))

vi.mock('@/api/projects', async () => {
  const actual = await vi.importActual<typeof import('@/api/projects')>('@/api/projects')
  return {
    ...actual,
    getInsightMemo: mocks.getInsightMemo,
    generateInsightMemo: mocks.generateInsightMemo,
  }
})

vi.mock('@/api/client', () => ({
  apiClient: { get: mocks.apiGet },
}))

const memo: InsightMemo = {
  id: 'memo-1',
  sessionId: 'session-1',
  projectId: 'project-1',
  stakeholderProfileId: 'stakeholder-1',
  interviewDate: '2026-07-14T09:30:00Z',
  interviewDurationMinutes: 32,
  topicsCovered: ['掛號來源', '資料確認流程'],
  stakeholderSummary: {
    name: '王小明',
    role: '門診櫃台組長',
    department: '門診櫃檯',
    expertise: ['掛號流程'],
    boundaries: [],
  },
  qaSummaries: [],
  painPoints: [{
    description: '尖峰時段需要重複確認掛號資料',
    evidence_quote: '同一筆資料常常要查兩次。',
    affected_roles: ['櫃台人員'],
    severity: 'high',
  }],
  requirementCandidates: [{
    description: '集中顯示掛號來源與病患資料',
    source: 'explicit',
    confidence: 'high',
    evidence_quote: '希望一個畫面就能看完。',
    needs_validation_from: [],
    brd_ready: true,
  }],
  constraintsAndAssumptions: [
    { type: 'constraint', content: '現有系統欄位不可調整', source: 'explicit', evidence_quote: '' },
    { type: 'assumption', content: '櫃台人員熟悉既有流程', source: 'inferred', evidence_quote: '' },
  ],
  processDescriptions: [],
  unresolvedQuestions: [{
    question: '不同掛號來源是否有不同處理流程？',
    suggested_stakeholder_type: 'operations',
    priority: 'high',
    reason: '目前訪談沒有涵蓋例外流程。',
  }],
  nextInterviewSuggestions: [{
    target_role: '資訊人員',
    objective: '確認系統整合限制',
    key_questions: ['目前可使用哪些 API？'],
  }],
  sourceDistinction: { explicit_statements: 3, inferences: 1, unverified: 1 },
  status: 'ready',
}

const secondMemo: InsightMemo = {
  ...memo,
  id: 'memo-2',
  sessionId: 'session-2',
  interviewDate: '2026-07-15T02:00:00Z',
  interviewDurationMinutes: 18,
  topicsCovered: ['尖峰時段處理'],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/sessions/session-1/insight-memo']}>
      <Routes>
        <Route path="/sessions/:sessionId/insight-memo" element={<InsightMemoPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('InsightMemoPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getInsightMemo.mockResolvedValue(memo)
    mocks.generateInsightMemo.mockResolvedValue(memo)
    mocks.apiGet.mockImplementation((url: string) => {
      if (url.includes('/utterances')) {
        return Promise.resolve({
          data: [{ speaker: 'interviewer', transcript: '目前通常會先查哪些資料？' }],
        })
      }
      return Promise.resolve({ data: { memos: [memo] } })
    })
  })

  it('presents the memo as a structured report with clear sections', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: '訪談紀錄' })).toBeInTheDocument()
    expect(screen.getAllByText('王小明').length).toBeGreaterThan(0)
    expect(screen.getByText('32')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '痛點與阻礙' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '需求線索' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '限制與假設' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '未解問題' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '建議下一步' })).toBeInTheDocument()
    expect(screen.getByText('已知限制')).toBeInTheDocument()
    expect(screen.getByText('待驗證假設')).toBeInTheDocument()
  })

  it('switches to the ordered transcript view', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: '訪談紀錄' })
    await user.click(screen.getByRole('button', { name: /完整逐字稿/ }))

    expect(await screen.findByRole('heading', { name: '完整逐字稿' })).toBeInTheDocument()
    expect(screen.getByText('目前通常會先查哪些資料？')).toBeInTheDocument()
    expect(screen.getAllByText('訪談者').length).toBeGreaterThan(0)
  })

  it('separates merged interview transcripts into session pages', async () => {
    const user = userEvent.setup()
    mocks.apiGet.mockImplementation((url: string) => {
      if (url.includes('/session-1/utterances')) {
        return Promise.resolve({
          data: [{ id: 'utterance-1', speaker: 'interviewer', transcript: '第一場逐字稿內容' }],
        })
      }
      if (url.includes('/session-2/utterances')) {
        return Promise.resolve({
          data: [{ id: 'utterance-2', speaker: 'interviewee', transcript: '第二場逐字稿內容' }],
        })
      }
      return Promise.resolve({ data: { memos: [memo, secondMemo] } })
    })
    renderPage()

    await screen.findByRole('heading', { name: '訪談紀錄' })
    await user.click(screen.getByRole('button', { name: /完整逐字稿/ }))

    const sessionNavigation = screen.getByRole('navigation', { name: '逐字稿場次' })
    expect(within(sessionNavigation).getByRole('button', { name: /第 1 場/ })).toHaveAttribute('aria-current', 'page')
    expect(within(sessionNavigation).getByRole('button', { name: /第 2 場/ })).toBeInTheDocument()
    expect(await screen.findByText('第一場逐字稿內容')).toBeInTheDocument()

    await user.click(within(sessionNavigation).getByRole('button', { name: /第 2 場/ }))

    expect(await screen.findByText('第二場逐字稿內容')).toBeInTheDocument()
    expect(screen.queryByText('第一場逐字稿內容')).not.toBeInTheDocument()
    expect(mocks.apiGet).toHaveBeenCalledWith(
      '/api/interview-sessions/session-2/utterances',
      { params: { limit: 1000 } },
    )
  })

  it('shows an explicit empty state for a session without transcript data', async () => {
    const user = userEvent.setup()
    mocks.apiGet.mockImplementation((url: string) => {
      if (url.includes('/utterances')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: { memos: [memo, secondMemo] } })
    })
    renderPage()

    await screen.findByRole('heading', { name: '訪談紀錄' })
    await user.click(screen.getByRole('button', { name: /完整逐字稿/ }))
    const sessionNavigation = screen.getByRole('navigation', { name: '逐字稿場次' })
    await user.click(within(sessionNavigation).getByRole('button', { name: /第 2 場/ }))

    expect(await screen.findByText('此場訪談沒有可顯示的逐字稿。')).toBeInTheDocument()
  })
})
