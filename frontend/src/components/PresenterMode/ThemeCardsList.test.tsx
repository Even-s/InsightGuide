import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { interviewAPI } from '@/api/interview'
import type { CardState } from '@/types/interview'
import ThemeCardsList from './ThemeCardsList'

vi.mock('@/api/interview', () => ({
  interviewAPI: {
    clearActiveCard: vi.fn(),
    confirmActiveCard: vi.fn(),
    manualCompleteCard: vi.fn(),
    undoCompleteCard: vi.fn(),
  },
}))

const currentTheme = {
  id: 'theme-1',
  cards: [
    {
      id: 'card-1',
      focusText: '掛號流程',
      questionText: '目前如何處理掛號？',
      importance: 'must',
    },
  ],
}

const listeningCardStates = [
  {
    id: 'state-1',
    sessionId: 'session-1',
    topicCardId: 'card-1',
    status: 'listening',
    confidence: 0,
    evidence: {
      satisfiedCriteria: ['criterion-1'],
      criterionEvaluations: [
        { criterion_id: 'criterion-1', status: 'satisfied', evidence_quotes: ['從網站與現場櫃台進件'] },
      ],
    },
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    questionCard: {
      id: 'card-1',
      documentId: 'doc-1',
      sectionId: '',
      sectionNumber: 0,
      questionText: '目前如何處理掛號？',
      focusText: '掛號流程',
      questionType: 'clarification',
      importance: 'must',
      status: 'listening',
      confidence: 0,
      expectedAnswerElements: ['接單管道', '資料來源'],
      coverageRule: {
        semanticAnchors: [],
        expectedKeywords: [],
        mustMentionElements: [],
        negativeSignals: [],
        thresholds: { probablySufficient: 0.62, sufficient: 0.8 },
        scoringWeights: { semanticSimilarity: 0.55, keywordCoverage: 0.25, elementCoverage: 0.2 },
        criteria: [
          { id: 'criterion-1', description: '描述接單來源的具體步驟或做法', type: 'value_slot', required: true, critical: true, weight: 0.5 },
          { id: 'criterion-2', description: '說明誰參與或負責哪個環節', type: 'value_slot', required: true, critical: false, weight: 0.3 },
          { id: 'criterion-3', description: '提及遇到的困難或目前的限制', type: 'value_slot', required: false, critical: false, weight: 0.2 },
        ],
      },
      orderIndex: 0,
      createdBy: 'ai',
      createdAt: '2026-01-01',
      updatedAt: '2026-01-01',
    },
  },
] as CardState[]

function renderCards(
  activeCardId: string | null,
  setActiveCardId = vi.fn(),
  detectedCardId: string | null = null,
) {
  const rendered = render(
    <ThemeCardsList
      currentTheme={currentTheme}
      cardStates={listeningCardStates}
      activeCardId={activeCardId}
      detectedCardId={detectedCardId}
      sessionId="session-1"
      setActiveCardId={setActiveCardId}
      updateCardFromEvent={vi.fn()}
    />,
  )
  return { setActiveCardId, ...rendered }
}

describe('ThemeCardsList active card controls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not treat a listening card as active after it was cleared', () => {
    renderCards(null)

    expect(screen.getByRole('button', { name: '設為目前問題' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '取消目前問題' })).not.toBeInTheDocument()
  })

  it('shows AI detection separately from the manually selected current card', () => {
    const { unmount } = renderCards(null, vi.fn(), 'card-1')

    expect(screen.getByText('AI 偵測中')).toBeInTheDocument()
    expect(screen.queryByText('目前問題')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '設為目前問題' })).toBeInTheDocument()

    unmount()
    renderCards('card-1', vi.fn(), 'card-1')

    expect(screen.getByText('目前問題')).toBeInTheDocument()
    expect(screen.queryByText('AI 偵測中')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '取消目前問題' })).toBeInTheDocument()
  })

  it('shows the completion criteria beneath the suggested question', () => {
    renderCards(null)

    expect(screen.getByText('完成條件')).toBeInTheDocument()
    expect(screen.getByText('描述接單來源的具體步驟或做法')).toBeInTheDocument()
    expect(screen.getByText('說明誰參與或負責哪個環節')).toBeInTheDocument()
    expect(screen.getByText('提及遇到的困難或目前的限制')).toBeInTheDocument()
    expect(screen.getByText('選填')).toBeInTheDocument()
  })

  it('strikes through an individually satisfied completion criterion', () => {
    renderCards(null)

    const satisfiedCriterion = screen.getByText('描述接單來源的具體步驟或做法').closest('li')
    const pendingCriterion = screen.getByText('說明誰參與或負責哪個環節').closest('li')

    expect(satisfiedCriterion).toHaveAttribute('data-satisfied', 'true')
    expect(satisfiedCriterion?.querySelector('[aria-hidden="true"].scale-x-100')).toBeInTheDocument()
    expect(pendingCriterion).toHaveAttribute('data-satisfied', 'false')
    expect(pendingCriterion?.querySelector('[aria-hidden="true"].scale-x-0')).toBeInTheDocument()
  })

  it('waits for clearActiveCard and locks the control during the request', async () => {
    let resolveRequest: ((value: { ok: boolean; cardId: string }) => void) | undefined
    vi.mocked(interviewAPI.clearActiveCard).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve
      }),
    )
    const setActiveCardId = vi.fn()
    renderCards('card-1', setActiveCardId)

    fireEvent.click(screen.getByRole('button', { name: '取消目前問題' }))

    const pendingButton = screen.getByRole('button', { name: '取消中…' })
    expect(pendingButton).toBeDisabled()
    expect(setActiveCardId).not.toHaveBeenCalled()

    await act(async () => {
      resolveRequest?.({ ok: true, cardId: 'card-1' })
    })

    expect(interviewAPI.clearActiveCard).toHaveBeenCalledWith('session-1')
    expect(setActiveCardId).toHaveBeenCalledWith(null)
  })

  it('keeps the active card and shows an error when cancellation fails', async () => {
    vi.mocked(interviewAPI.clearActiveCard).mockRejectedValueOnce(new Error('network error'))
    const setActiveCardId = vi.fn()
    renderCards('card-1', setActiveCardId)

    fireEvent.click(screen.getByRole('button', { name: '取消目前問題' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('取消失敗，請再試一次。')
    })
    expect(setActiveCardId).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: '取消目前問題' })).toBeEnabled()
  })
})
