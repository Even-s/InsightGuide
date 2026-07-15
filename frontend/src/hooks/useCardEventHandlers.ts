import { useCallback, useEffect, useState } from 'react'
import { interviewAPI } from '@/api/interview'
import { useSSEEvents } from '@/hooks/useSSEEvents'
import type { CardState, SessionStatus } from '@/types/interview'
import type { CardStatus } from '@/types/questionCard'
import {
  statusFromEvent,
  buildFollowupPrompt,
  getEvidenceSuggestedFollowup,
} from '@/components/PresenterMode/presenterUtils'

const COMPLETED_CARD_STATUSES = new Set<CardStatus>([
  'sufficient',
  'covered',
  'manually_checked',
])

interface UseCardEventHandlersOptions {
  sessionId: string
  documentId: string
  currentThemeId: string | undefined
  currentSectionId: string | undefined
  initialActiveCardId?: string | null
  initialDetectedCardId?: string | null
  sessionStatus?: SessionStatus
}

export interface CardEventHandlersResult {
  cardStates: CardState[]
  candidateCards: Array<{ cardId: string; questionText: string; focusText: string; score: number }>
  activeCardId: string | null
  detectedCardId: string | null
  bufferedAnswerCount: number
  followupQueue: string[]
  skippedCards: Set<string>
  currentFollowupCard: CardState | undefined
  followupPrompt: ReturnType<typeof buildFollowupPrompt>
  followupQueueLength: number
  setActiveCardId: (id: string | null) => void
  setCandidateCards: (cards: Array<{ cardId: string; questionText: string; focusText: string; score: number }>) => void
  setBufferedAnswerCount: React.Dispatch<React.SetStateAction<number>>
  handleSkipFollowup: () => void
  updateCardFromEvent: (cardId: string | undefined, status: CardStatus, confidence?: number, evidence?: unknown, evidenceTranscript?: string) => void
}

export function useCardEventHandlers({
  sessionId,
  documentId,
  currentThemeId,
  currentSectionId,
  initialActiveCardId,
  initialDetectedCardId,
  sessionStatus,
}: UseCardEventHandlersOptions): CardEventHandlersResult {
  const [cardStates, setCardStates] = useState<CardState[]>([])
  const [, setCardsLoading] = useState(true)
  const [candidateCards, setCandidateCards] = useState<Array<{ cardId: string; questionText: string; focusText: string; score: number }>>([])
  const [activeCardId, setActiveCardId] = useState<string | null>(null)
  const [detectedCardId, setDetectedCardId] = useState<string | null>(null)
  const [bufferedAnswerCount, setBufferedAnswerCount] = useState(0)
  const [followupQueue, setFollowupQueue] = useState<string[]>([])
  const [skippedCards, setSkippedCards] = useState<Set<string>>(new Set())

  const updateCardFromEvent = useCallback((
    cardId: string | undefined,
    status: CardState['status'],
    confidence?: number,
    evidence?: unknown,
    evidenceTranscript?: string,
  ) => {
    if (!cardId) return

    if (COMPLETED_CARD_STATUSES.has(status)) {
      setActiveCardId((previous) => previous === cardId ? null : previous)
      setDetectedCardId((previous) => previous === cardId ? null : previous)
    }

    const resolvedTranscript =
      evidenceTranscript
        ? evidenceTranscript
        : evidence && typeof evidence === 'object' && 'matchedTranscript' in evidence
        ? String((evidence as { matchedTranscript?: unknown }).matchedTranscript ?? '')
        : ''

    setCardStates((previous) =>
      previous.map((cardState) =>
        cardState.questionCard.id === cardId
          ? {
              ...cardState,
              status,
              confidence: confidence ?? cardState.confidence,
              evidence: evidence && typeof evidence === 'object' ? evidence as Record<string, unknown> : cardState.evidence,
              evidenceTranscript: resolvedTranscript || cardState.evidenceTranscript,
              questionCard: {
                ...cardState.questionCard,
                status,
                confidence: confidence ?? cardState.questionCard.confidence,
              },
            }
          : cardState,
      ),
    )
  }, [])

  const updateCriterionFromEvent = useCallback((
    cardId: string,
    criterionId: string,
    status: string,
    evidenceQuote: string | null,
  ) => {
    setCardStates((previous) =>
      previous.map((cardState) => {
        if (cardState.questionCard.id !== cardId) return cardState

        const existingEvidence = cardState.evidence && typeof cardState.evidence === 'object'
          ? cardState.evidence as Record<string, unknown>
          : {}
        const satisfiedCriteria = new Set(
          Array.isArray(existingEvidence.satisfiedCriteria)
            ? existingEvidence.satisfiedCriteria.filter((id): id is string => typeof id === 'string')
            : [],
        )
        if (status === 'satisfied') satisfiedCriteria.add(criterionId)

        const existingEvaluations = Array.isArray(existingEvidence.criterionEvaluations)
          ? existingEvidence.criterionEvaluations.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
          : []
        const nextEvaluation = {
          ...(existingEvaluations.find(item => item.criterion_id === criterionId) ?? {}),
          criterion_id: criterionId,
          status,
          evidence_quotes: evidenceQuote ? [evidenceQuote] : [],
        }

        return {
          ...cardState,
          evidence: {
            ...existingEvidence,
            satisfiedCriteria: [...satisfiedCriteria],
            criterionEvaluations: [
              ...existingEvaluations.filter(item => item.criterion_id !== criterionId),
              nextEvaluation,
            ],
          },
        }
      }),
    )
  }, [])

  const loadCardStates = useCallback(async () => {
    try {
      setCardsLoading(true)
      const states = await interviewAPI.getSessionCards(sessionId, documentId)
      setCardStates(states)
    } finally {
      setCardsLoading(false)
    }
  }, [documentId, sessionId])

  useEffect(() => {
    loadCardStates()
  }, [loadCardStates, sessionStatus])

  useEffect(() => {
    if (initialActiveCardId !== undefined) setActiveCardId(initialActiveCardId)
    if (initialDetectedCardId !== undefined) {
      setDetectedCardId(
        initialDetectedCardId && initialDetectedCardId !== initialActiveCardId
          ? initialDetectedCardId
          : null,
      )
    }
  }, [initialActiveCardId, initialDetectedCardId])

  useEffect(() => {
    const completedCardIds = new Set(
      cardStates
        .filter((cardState) => COMPLETED_CARD_STATUSES.has(cardState.status))
        .map((cardState) => cardState.questionCard.id),
    )
    const hasStaleRouting = Boolean(
      (activeCardId && completedCardIds.has(activeCardId))
      || (detectedCardId && completedCardIds.has(detectedCardId)),
    )
    if (!hasStaleRouting) return

    setActiveCardId(null)
    setDetectedCardId(null)
    void interviewAPI.clearActiveCard(sessionId).catch((error) => {
      console.error('Failed to clear completed card routing:', error)
    })
  }, [activeCardId, cardStates, detectedCardId, sessionId])

  useSSEEvents(sessionId, {
    onCardListening: (data) => {
      updateCardFromEvent(data.card_id, statusFromEvent(data, 'listening'), data.confidence, data.evidence, data.evidenceTranscript)
      if (data.card_id) setDetectedCardId(data.card_id)
    },
    onCardCovered: (data) => {
      updateCardFromEvent(data.card_id, statusFromEvent(data, 'sufficient'), data.confidence, data.evidence, data.evidenceTranscript)
      setDetectedCardId(previous => previous === data.card_id ? null : previous)
    },
    onCardProbablyCovered: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'probably_sufficient'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardAtRisk: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'at_risk'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardSkipped: (data) => updateCardFromEvent(data.card_id, statusFromEvent(data, 'skipped'), data.confidence, data.evidence, data.evidenceTranscript),
    onCardEvidenceAdded: (data) => {
      updateCriterionFromEvent(data.card_id, data.criterion_id, data.status, data.evidence_quote)
    },
    onQuestionCardCandidates: (data) => {
      setCandidateCards(data.candidates)
    },
    onActiveCardChanged: (data) => {
      setActiveCardId(data.card_id)
      setDetectedCardId(null)
      setCandidateCards([])
      setBufferedAnswerCount(0)
      updateCardFromEvent(data.card_id, 'listening', 0, undefined, undefined)
    },
    onCardManuallyCompleted: (data) => {
      updateCardFromEvent(data.card_id, statusFromEvent(data, 'sufficient'), 1.0, data.evidence, data.evidenceTranscript)
      setActiveCardId((prev) => prev === data.card_id ? null : prev)
      setDetectedCardId((prev) => prev === data.card_id ? null : prev)
    },
    onActiveCardCleared: () => {
      setActiveCardId(null)
      setDetectedCardId(null)
      setCandidateCards([])
      setBufferedAnswerCount(0)
    },
    onMatchingError: (data) => {
      console.error('Topic matching error received:', data)
    },
  })

  // Followup queue management
  useEffect(() => {
    const activeSectionId = currentThemeId ?? currentSectionId
    if (!activeSectionId) return

    const cardsWithFollowup = cardStates.filter((cs) => {
      const qc = cs.questionCard
      const isInSection = qc.interviewThemeId === activeSectionId || qc.sectionId === activeSectionId
      const hasFollowup = cs.evidence && getEvidenceSuggestedFollowup(cs.evidence as Record<string, unknown>)
      const needsFollowup = cs.status === 'listening' || cs.status === 'probably_sufficient'
      return isInSection && needsFollowup && hasFollowup && !skippedCards.has(cs.questionCard.id)
    })

    setFollowupQueue((prev) => {
      const existingSet = new Set(prev)
      const newIds = cardsWithFollowup
        .map((cs) => cs.questionCard.id)
        .filter((id) => !existingSet.has(id))
      if (newIds.length === 0) return prev
      return [...prev, ...newIds]
    })
  }, [cardStates, currentThemeId, currentSectionId, skippedCards])

  const currentFollowupCard = followupQueue
    .filter((id) => !skippedCards.has(id))
    .map((id) => cardStates.find((cs) => cs.questionCard.id === id))
    .find((cs) => cs && (cs.status === 'listening' || cs.status === 'probably_sufficient'))

  const activeSectionId = currentThemeId ?? currentSectionId
  const followupPrompt = currentFollowupCard
    ? buildFollowupPrompt([currentFollowupCard], activeSectionId)
    : null

  const followupQueueLength = followupQueue.filter((id) => !skippedCards.has(id)).length

  const handleSkipFollowup = useCallback(() => {
    if (currentFollowupCard) {
      setSkippedCards((prev) => new Set([...prev, currentFollowupCard.questionCard.id]))
    }
  }, [currentFollowupCard])

  return {
    cardStates,
    candidateCards,
    activeCardId,
    detectedCardId,
    bufferedAnswerCount,
    followupQueue,
    skippedCards,
    currentFollowupCard,
    followupPrompt,
    followupQueueLength,
    setActiveCardId,
    setCandidateCards,
    setBufferedAnswerCount,
    handleSkipFollowup,
    updateCardFromEvent,
  }
}
