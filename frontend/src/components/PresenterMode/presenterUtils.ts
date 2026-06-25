import type { CardState } from '@/types/interview'
import type { CardStatus } from '@/types/questionCard'
import { formatFocusText, formatQuestionText } from '@/utils/interviewCopy'

export function statusFromEvent(
  data: { new_status?: string; status?: string },
  fallback: CardStatus,
): CardStatus {
  const status = data.new_status ?? data.status
  if (
    status === 'pending' ||
    status === 'listening' ||
    status === 'probably_sufficient' ||
    status === 'sufficient' ||
    status === 'probably_covered' ||
    status === 'covered' ||
    status === 'at_risk' ||
    status === 'skipped' ||
    status === 'manually_checked' ||
    status === 'disabled'
  ) {
    return status
  }
  return fallback
}

export function getActiveCardId(cardStates: CardState[], activeSectionId?: string) {
  if (!activeSectionId) return null

  const activeCard = cardStates.find((cardState) => {
    const questionCard = cardState.questionCard
    const isInActiveSection =
      questionCard.interviewThemeId === activeSectionId ||
      questionCard.sectionId === activeSectionId
    return isInActiveSection && cardState.status === 'listening'
  })

  return activeCard?.questionCard.id ?? null
}

export function findAskedCard(text: string, cardStates: CardState[], activeSectionId?: string): string | null {
  if (!activeSectionId || !text) return null

  const QUESTION_ENDINGS = ['?', '？', '呢', '嗎']
  const isQuestion = QUESTION_ENDINGS.some(e => text.trim().endsWith(e))
  if (!isQuestion) return null

  const sectionCards = cardStates.filter(cs => {
    const qc = cs.questionCard
    return (qc.interviewThemeId === activeSectionId || qc.sectionId === activeSectionId)
      && cs.status !== 'sufficient'
  })

  let bestScore = 0
  let bestId: string | null = null
  const textLower = text.toLowerCase()

  for (const cs of sectionCards) {
    const qc = cs.questionCard
    let score = 0

    // Check overlap with questionText
    if (qc.questionText) {
      const words = qc.questionText.toLowerCase().split('').filter(c => c.trim())
      const overlap = words.filter(w => textLower.includes(w)).length / Math.max(words.length, 1)
      score += overlap * 2
    }

    // Check overlap with focusText
    if (qc.focusText) {
      const focusChars = qc.focusText.toLowerCase()
      for (let i = 0; i < focusChars.length - 1; i++) {
        if (textLower.includes(focusChars.slice(i, i + 2))) score += 0.3
      }
    }

    if (score > bestScore) {
      bestScore = score
      bestId = qc.id
    }
  }

  return bestScore > 1.0 ? bestId : null
}

export interface FollowupPrompt {
  cardTitle: string
  missingItems: string[]
  reason?: string
  suggestedFollowup?: string
}

export function buildFollowupPrompt(
  cardStates: CardState[],
  activeSectionId?: string,
): FollowupPrompt | null {
  if (!activeSectionId) return null

  const activeCardState = cardStates.find((cardState) => {
    const questionCard = cardState.questionCard
    const isInActiveSection =
      questionCard.interviewThemeId === activeSectionId ||
      questionCard.sectionId === activeSectionId
    return isInActiveSection && (cardState.status === 'listening' || cardState.status === 'probably_sufficient')
  })
  if (!activeCardState) return null

  const evidence = activeCardState.evidence
  if (!evidence || evidence.activeOnly === true) return null

  const reason = getEvidenceReason(evidence)
  const missingItems = getMissingItems(activeCardState)
  const suggestedFollowup = getEvidenceSuggestedFollowup(evidence)

  if (missingItems.length === 0 && !reason && !suggestedFollowup) {
    return null
  }

  return {
    cardTitle: formatFocusText(activeCardState.questionCard.focusText) || formatQuestionText(activeCardState.questionCard.questionText),
    missingItems,
    reason,
    suggestedFollowup,
  }
}

export function getEvidenceReason(evidence: Record<string, unknown>) {
  const directReason = evidence.reason
  if (typeof directReason === 'string' && directReason.trim()) return directReason.trim()

  const judgment = evidence.judgment
  if (judgment && typeof judgment === 'object' && 'reason' in judgment) {
    const reason = (judgment as { reason?: unknown }).reason
    if (typeof reason === 'string' && reason.trim()) return reason.trim()
  }

  if (typeof evidence.gptReasoning === 'string' && evidence.gptReasoning.trim()) {
    return evidence.gptReasoning.trim()
  }

  return undefined
}

export function getEvidenceSuggestedFollowup(evidence: Record<string, unknown>) {
  const directFollowup = evidence.suggested_followup ?? evidence.suggestedFollowup
  if (typeof directFollowup === 'string' && directFollowup.trim()) return directFollowup.trim()

  const judgment = evidence.judgment
  if (judgment && typeof judgment === 'object') {
    const followup =
      (judgment as { suggested_followup?: unknown }).suggested_followup ??
      (judgment as { suggestedFollowup?: unknown }).suggestedFollowup
    if (typeof followup === 'string' && followup.trim()) return followup.trim()
  }

  return undefined
}

export function getMissingItems(cardState: CardState) {
  const evidence = cardState.evidence
  if (!evidence) return []

  const rawMissingIds: unknown[] = Array.isArray(evidence.missingElementIds)
    ? evidence.missingElementIds
    : Array.isArray((evidence.judgment as { missing_element_ids?: unknown } | undefined)?.missing_element_ids)
      ? ((evidence.judgment as { missing_element_ids?: unknown[] }).missing_element_ids ?? [])
      : []

  const missingIds = rawMissingIds
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => item.trim())

  if (missingIds.length === 0) return []

  const coverageRule = cardState.questionCard.coverageRule
  return missingIds
    .map((id) => formatFocusText(resolveCoverageItemText(id, coverageRule)))
    .filter((text): text is string => Boolean(text))
}

export function resolveCoverageItemText(
  id: string,
  coverageRule: CardState['questionCard']['coverageRule'],
) {
  const elementMatch = id.match(/^element_(\d+)$/)
  if (elementMatch) {
    const index = Number(elementMatch[1])
    const element = coverageRule.mustMentionElements[index]
    return element?.text || element?.subpoints?.join('、') || id
  }

  const anchorMatch = id.match(/^anchor_(\d+)$/)
  if (anchorMatch) {
    const index = Number(anchorMatch[1])
    return coverageRule.semanticAnchors[index] || id
  }

  return id
}
