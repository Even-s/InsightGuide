import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useCardEventHandlers } from './useCardEventHandlers'

vi.mock('@/api/interview', () => ({
  interviewAPI: {
    getSessionCards: vi.fn().mockResolvedValue([
      {
        id: 'cs-1',
        sessionId: 'session-1',
        topicCardId: 'card-1',
        status: 'pending',
        confidence: 0,
        evidenceTranscript: null,
        evidence: null,
        createdAt: '2026-01-01',
        updatedAt: '2026-01-01',
        questionCard: {
          id: 'card-1',
          focusText: 'Focus 1',
          questionText: 'Question 1',
          interviewThemeId: 'theme-1',
          sectionId: null,
          status: 'pending',
          confidence: 0,
          importance: 'must',
          coverageRule: { semanticAnchors: [], expectedKeywords: [], mustMentionElements: [], thresholds: { probably_sufficient: 0.65, sufficient: 0.8 } },
        },
      },
    ]),
  },
}))

vi.mock('@/hooks/useSSEEvents', () => ({
  useSSEEvents: vi.fn(),
}))

describe('useCardEventHandlers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads card states on mount', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        documentId: 'doc-1',
        currentThemeId: 'theme-1',
        currentSectionId: undefined,
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates).toHaveLength(1)
    })

    expect(result.current.cardStates[0].questionCard.id).toBe('card-1')
  })

  it('updateCardFromEvent updates status and confidence', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        documentId: 'doc-1',
        currentThemeId: 'theme-1',
        currentSectionId: undefined,
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates).toHaveLength(1)
    })

    act(() => {
      result.current.updateCardFromEvent('card-1', 'sufficient', 0.95, undefined, undefined)
    })

    expect(result.current.cardStates[0].status).toBe('sufficient')
    expect(result.current.cardStates[0].confidence).toBe(0.95)
  })

  it('handleSkipFollowup adds card to skippedCards', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        documentId: 'doc-1',
        currentThemeId: 'theme-1',
        currentSectionId: undefined,
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates).toHaveLength(1)
    })

    expect(result.current.skippedCards.size).toBe(0)
  })

  it('initializes with empty candidate cards', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        documentId: 'doc-1',
        currentThemeId: 'theme-1',
        currentSectionId: undefined,
      }),
    )

    expect(result.current.candidateCards).toHaveLength(0)
    expect(result.current.activeCardId).toBeNull()
    expect(result.current.bufferedAnswerCount).toBe(0)
  })
})
