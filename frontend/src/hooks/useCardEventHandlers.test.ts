import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useCardEventHandlers } from './useCardEventHandlers'
import { useSSEEvents } from '@/hooks/useSSEEvents'

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
        documentId: 'doc-1',
        currentThemeId: 'theme-1',
        currentSectionId: undefined,
        initialActiveCardId: 'card-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.activeCardId).toBe('card-1')
    })
  })

  it('restores an AI-detected card separately from the manual active card', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        documentId: 'doc-1',
        currentThemeId: 'theme-1',
        currentSectionId: undefined,
        initialActiveCardId: null,
        initialDetectedCardId: 'card-1',
      }),
    )

    await waitFor(() => {
      expect(result.current.detectedCardId).toBe('card-1')
    })
    expect(result.current.activeCardId).toBeNull()
  })

  it('moves an AI detection into detectedCardId without making it manually active', async () => {
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

    const sseCalls = vi.mocked(useSSEEvents).mock.calls
    const eventHandlers = sseCalls[sseCalls.length - 1]?.[1]
    act(() => {
      eventHandlers?.onCardListening?.({
        type: 'CARD_TOPIC_DETECTED',
        card_id: 'card-1',
        old_status: 'pending',
        new_status: 'listening',
      })
    })

    expect(result.current.detectedCardId).toBe('card-1')
    expect(result.current.activeCardId).toBeNull()
  })

  it('clears the AI detection when a manual active card is confirmed', async () => {
    const { result } = renderHook(() =>
      useCardEventHandlers({
        sessionId: 'session-1',
        documentId: 'doc-1',
        currentThemeId: 'theme-1',
        currentSectionId: undefined,
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

  it('records a satisfied criterion from the granular SSE event', async () => {
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
