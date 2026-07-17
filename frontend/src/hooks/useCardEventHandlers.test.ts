import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { interviewAPI } from '@/api/interview'
import { useCardEventHandlers } from './useCardEventHandlers'
import { useSSEEvents } from '@/hooks/useSSEEvents'

vi.mock('@/api/interview', () => ({
  interviewAPI: {
    clearActiveCard: vi.fn().mockResolvedValue({ ok: true, cardId: 'card-1' }),
    getSessionCards: vi.fn().mockResolvedValue([
      {
        id: 'cs-1',
        sessionId: 'session-1',
        questionCardId: 'card-1',
        status: 'pending',
        confidence: 0,
        evidenceTranscript: null,
        evidence: null,
        createdAt: '2026-01-01',
        updatedAt: '2026-01-01',
        questionCard: {
          id: 'card-1',
          documentId: 'doc-1',
          focusText: 'Focus 1',
          questionText: 'Question 1',
          themeId: 'theme-1',
          status: 'pending',
          confidence: 0,
          importance: 'must',
          coverageRule: {
            semanticAnchors: [],
            expectedKeywords: [],
            mustMentionElements: [],
            negativeSignals: [],
            thresholds: { probablySufficient: 0.65, sufficient: 0.8 },
            scoringWeights: { semanticSimilarity: 0.55, keywordCoverage: 0.25, elementCoverage: 0.2 },
          },
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
        currentThemeId: 'theme-1',
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
        currentThemeId: 'theme-1',
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
        currentThemeId: 'theme-1',
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
        currentThemeId: 'theme-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates).toHaveLength(1)
    })

    expect(result.current.candidateCards).toHaveLength(0)
    expect(result.current.activeCardId).toBeNull()
    expect(result.current.bufferedAnswerCount).toBe(0)
  })

  it('restores the active card from the loaded session', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
        initialActiveCardId: 'card-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.activeCardId).toBe('card-1')
    })
  })

  it('clears stale routing restored for an already completed card', async () => {
    vi.mocked(interviewAPI.getSessionCards).mockResolvedValueOnce([
      {
        id: 'cs-1',
        sessionId: 'session-1',
        questionCardId: 'card-1',
        status: 'sufficient',
        confidence: 1,
        evidenceTranscript: '完整回答',
        evidence: null,
        createdAt: '2026-01-01',
        updatedAt: '2026-01-01',
        questionCard: {
          id: 'card-1',
          documentId: 'doc-1',
          focusText: 'Focus 1',
          questionText: 'Question 1',
          questionType: 'clarification',
          themeId: 'theme-1',
          status: 'sufficient',
          confidence: 1,
          importance: 'must',
          expectedAnswerElements: [],
          coverageRule: {
            semanticAnchors: [],
            expectedKeywords: [],
            mustMentionElements: [],
            negativeSignals: [],
            thresholds: { probablySufficient: 0.65, sufficient: 0.8 },
            scoringWeights: { semanticSimilarity: 0.55, keywordCoverage: 0.25, elementCoverage: 0.2 },
          },
          orderIndex: 0,
          createdBy: 'ai',
          createdAt: '2026-01-01',
          updatedAt: '2026-01-01',
        },
      },
    ])

    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
        initialActiveCardId: 'card-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates[0]?.status).toBe('sufficient')
      expect(result.current.activeCardId).toBeNull()
    })
    expect(interviewAPI.clearActiveCard).toHaveBeenCalledWith('session-1')
  })

  it('restores an AI-detected card separately from the manual active card', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
        initialActiveCardId: null,
        initialDetectedCardId: 'card-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.detectedCardId).toBe('card-1')
    })
    expect(result.current.activeCardId).toBeNull()
  })

  it('moves an AI suggestion into detectedCardId without making it manually active', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates).toHaveLength(1)
    })

    const sseCalls = vi.mocked(useSSEEvents).mock.calls
    const eventHandlers = sseCalls[sseCalls.length - 1]?.[1]
    act(() => {
      eventHandlers?.onQuestionCardSuggested?.({
        type: 'QUESTION_CARD_SUGGESTED',
        card_id: 'card-1',
        old_status: 'pending',
        new_status: 'pending',
      })
    })

    expect(result.current.detectedCardId).toBe('card-1')
    expect(result.current.activeCardId).toBeNull()
    expect(result.current.cardStates[0].status).toBe('pending')
  })

  it('can ignore an AI suggestion locally without clearing the active card API', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates).toHaveLength(1)
    })

    const sseCalls = vi.mocked(useSSEEvents).mock.calls
    const eventHandlers = sseCalls[sseCalls.length - 1]?.[1]
    act(() => {
      eventHandlers?.onQuestionCardSuggested?.({
        type: 'QUESTION_CARD_SUGGESTED',
        card_id: 'card-1',
        old_status: 'pending',
        new_status: 'pending',
      })
    })

    expect(result.current.detectedCardId).toBe('card-1')

    act(() => {
      result.current.ignoreSuggestedCard('card-1')
    })

    expect(result.current.detectedCardId).toBeNull()
    expect(result.current.detectedCardIds).toEqual([])
    expect(interviewAPI.clearActiveCard).not.toHaveBeenCalled()
  })

  it('clears the AI detection when a manual active card is confirmed', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
        initialDetectedCardId: 'card-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.detectedCardId).toBe('card-1')
    })

    const sseCalls = vi.mocked(useSSEEvents).mock.calls
    const eventHandlers = sseCalls[sseCalls.length - 1]?.[1]
    act(() => {
      eventHandlers?.onActiveCardChanged?.({
        card_id: 'card-1',
        status: 'listening',
        source: 'user_confirmed',
      })
    })

    expect(result.current.activeCardId).toBe('card-1')
    expect(result.current.detectedCardId).toBeNull()
  })

  it('clears active and detected routing when the card is covered', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
        initialActiveCardId: 'card-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.activeCardId).toBe('card-1')
    })

    const sseCalls = vi.mocked(useSSEEvents).mock.calls
    const eventHandlers = sseCalls[sseCalls.length - 1]?.[1]
    act(() => {
      eventHandlers?.onCardCovered?.({
        type: 'CARD_COVERED',
        card_id: 'card-1',
        old_status: 'probably_sufficient',
        new_status: 'sufficient',
        confidence: 1,
      })
    })

    expect(result.current.cardStates[0].status).toBe('sufficient')
    expect(result.current.activeCardId).toBeNull()
    expect(result.current.detectedCardId).toBeNull()
  })

  it('records a satisfied criterion from the granular SSE event', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        currentThemeId: 'theme-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.cardStates).toHaveLength(1)
    })

    const sseCalls = vi.mocked(useSSEEvents).mock.calls
    const eventHandlers = sseCalls[sseCalls.length - 1]?.[1]
    act(() => {
      eventHandlers?.onCardEvidenceAdded?.({
        type: 'CARD_EVIDENCE_ADDED',
        card_id: 'card-1',
        criterion_id: 'criterion-1',
        status: 'satisfied',
        evidence_quote: '具體回答內容',
        completion_score: 0.5,
        evaluationSeq: 1,
      })
    })

    expect(result.current.cardStates[0].evidence).toMatchObject({
      satisfiedCriteria: ['criterion-1'],
    })
  })
})
