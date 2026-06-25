import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { DocumentStatus } from '@/api/documents'
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
})
