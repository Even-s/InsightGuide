import { useEffect, useRef, useState } from 'react'
import { interviewAPI } from '@/api/interview'
import type { CardState } from '@/types/interview'
import AnimatedStrikeText from './AnimatedStrikeText'
import { formatFocusText, formatQuestionText } from '@/utils/interviewCopy'

interface ThemeCardsListProps {
  currentTheme: { id: string; cards: Array<{ id: string; focusText?: string; questionText: string; importance?: string; expectedAnswerElements?: string[] }> }
  cardStates: CardState[]
  activeCardId: string | null
  detectedCardId: string | null
  detectedCardIds?: string[]
  previewDetectedCardIds?: string[]
  sessionId: string
  setActiveCardId: (id: string | null) => void
  ignoreSuggestedCard: (id: string) => void
  updateCardFromEvent: (cardId: string | undefined, status: CardState['status'], confidence?: number, evidence?: unknown, evidenceTranscript?: string) => void
}

export default function ThemeCardsList({
  currentTheme,
  cardStates,
  activeCardId,
  detectedCardId,
  detectedCardIds = [],
  previewDetectedCardIds = [],
  sessionId,
  setActiveCardId,
  ignoreSuggestedCard,
  updateCardFromEvent,
}: ThemeCardsListProps) {
  const [pendingCardAction, setPendingCardAction] = useState<{ cardId: string; action: 'set' | 'clear' } | null>(null)
  const [cardActionError, setCardActionError] = useState<{ cardId: string; message: string } | null>(null)
  const feedbackTimerRef = useRef<number | null>(null)
  const cardStateMap = new Map(cardStates.map(cs => [cs.questionCard.id, cs.status]))
  const completedStatuses = new Set(['sufficient', 'covered', 'manually_checked'])

  useEffect(() => () => {
    if (feedbackTimerRef.current !== null) {
      window.clearTimeout(feedbackTimerRef.current)
    }
  }, [])

  const releaseActionLock = () => {
    if (feedbackTimerRef.current !== null) {
      window.clearTimeout(feedbackTimerRef.current)
    }
    feedbackTimerRef.current = window.setTimeout(() => {
      setPendingCardAction(null)
      feedbackTimerRef.current = null
    }, 450)
  }

  const handleActiveCardAction = async (
    cardId: string,
    isCardActive: boolean,
    source = 'user_confirmed',
  ) => {
    if (pendingCardAction) return

    const action = isCardActive ? 'clear' : 'set'
    setPendingCardAction({ cardId, action })
    setCardActionError(null)

    try {
      if (action === 'clear') {
        await interviewAPI.clearActiveCard(sessionId)
        setActiveCardId(null)
      } else {
        await interviewAPI.confirmActiveCard(sessionId, cardId, source)
        setActiveCardId(cardId)
      }
      releaseActionLock()
    } catch (error) {
      console.error(`Failed to ${action} active card:`, error)
      setPendingCardAction(null)
      setCardActionError({
        cardId,
        message: action === 'clear' ? '取消失敗，請再試一次。' : '設定失敗，請再試一次。',
      })
    }
  }

  const groups: { focus: string; cards: typeof currentTheme.cards }[] = []
  let cur: typeof groups[number] | null = null
  for (const card of currentTheme.cards) {
    const f = card.focusText || ''
    if (!cur || cur.focus !== f) {
      cur = { focus: f, cards: [card] }
      groups.push(cur)
    } else {
      cur.cards.push(card)
    }
  }

  return (
    <div key={currentTheme.id} className="mx-auto max-w-3xl space-y-4 animate-themeFadeIn">
      {groups.map((group, gi) => {
        const groupCardStates = group.cards.map(c => {
          const cs = cardStates.find(s => s.questionCard.id === c.id)
          const evidence = cs?.evidence && typeof cs.evidence === 'object'
            ? cs.evidence as Record<string, unknown>
            : undefined
          const satisfiedCriterionIds = new Set(
            Array.isArray(evidence?.satisfiedCriteria)
              ? evidence.satisfiedCriteria.filter((id): id is string => typeof id === 'string')
              : [],
          )
          if (Array.isArray(evidence?.criterionEvaluations)) {
            evidence.criterionEvaluations.forEach((evaluation) => {
              if (!evaluation || typeof evaluation !== 'object') return
              const record = evaluation as Record<string, unknown>
              if (record.status === 'satisfied' && typeof record.criterion_id === 'string') {
                satisfiedCriterionIds.add(record.criterion_id)
              }
            })
          }
          const rubricCriteria = (cs?.questionCard.coverageRule?.criteria ?? [])
            .filter(criterion => criterion.description?.trim())
            .map(criterion => ({
              id: criterion.id,
              description: criterion.description.trim(),
              required: criterion.required,
              satisfied: satisfiedCriterionIds.has(criterion.id),
            }))
          const fallbackCriteria = (cs?.questionCard.expectedAnswerElements ?? c.expectedAnswerElements ?? [])
            .filter(element => element.trim())
            .map((element, index) => ({
              id: `expected-${index}`,
              description: element.trim(),
              required: true,
              satisfied: false,
            }))

          return {
            card: c,
            status: cardStateMap.get(c.id) ?? 'pending',
            confidence: cs?.confidence ?? 0,
            completionCriteria: rubricCriteria.length > 0 ? rubricCriteria : fallbackCriteria,
          }
        })
        const groupDone = groupCardStates.every(c => completedStatuses.has(c.status))
        const groupConfidenceSum = groupCardStates.reduce((sum, c) => sum + (completedStatuses.has(c.status) ? 1 : (c.confidence ?? 0)), 0)
        const groupProgress = groupCardStates.length > 0 ? Math.round((groupConfidenceSum / groupCardStates.length) * 100) : 0

        return (
          <div key={gi} className={`relative rounded-2xl border shadow-sm overflow-hidden ${groupDone ? 'border-sage-200' : 'border-cream-300'}`}>
            <div
              className="pointer-events-none absolute inset-x-0 bottom-0 z-0 transition-[height] duration-1000 ease-out"
              style={{ height: `${groupProgress}%` }}
              aria-hidden="true"
            >
              <div className={`absolute inset-0 ${groupDone ? 'bg-sage-100/60' : 'bg-sage-50/50'}`} />
            </div>

            <div className="relative z-10">
              {group.focus && (
                <div className={`border-b px-5 py-2.5 ${groupDone ? 'border-sage-200' : 'border-sage-100'}`}>
                  <div className="flex items-center justify-between">
                    <AnimatedStrikeText
                      text={`${groupDone ? '✓ ' : ''}${formatFocusText(group.focus)}`}
                      done={groupDone}
                      className={`text-sm font-semibold transition-colors duration-500 ease-out ${groupDone ? 'text-sage-500' : 'text-sage-400'}`}
                    />
                  </div>
                </div>
              )}
              <div className="space-y-3 p-3">
                {groupCardStates.map(({ card, status, confidence, completionCriteria }, qi) => {
                  const isDone = completedStatuses.has(status)
                  // A completed card is terminal. Ignore stale routing IDs so
                  // completion styling always wins over the yellow active glow.
                  const isActive = !isDone && activeCardId === card.id
                  const isDetected = !isDone && !isActive && (
                    detectedCardId === card.id || detectedCardIds.includes(card.id)
                  )
                  const isPreviewDetected = !isDone && !isActive && !isDetected && previewDetectedCardIds.includes(card.id)
                  const isSuggestion = isDetected || isPreviewDetected
                  const isSecondaryDetected = isSuggestion
                  const isHighlighted = isActive || isDetected || isPreviewDetected
                  const sourceLabel = isActive ? '人工確認' : isSuggestion ? 'AI 建議' : null
                  const currentAction = pendingCardAction?.cardId === card.id ? pendingCardAction.action : null
                  const itemProgress = isDone ? 100 : status === 'listening' ? 0 : Math.round((confidence ?? 0) * 100)
                  const canManuallyComplete =
                    isActive || status === 'listening' || status === 'probably_sufficient' || status === 'at_risk'

                  return (
                    <div
                      key={card.id}
                      data-ai-detected={(isDetected || isPreviewDetected) || undefined}
                      data-ai-preview-detected={isPreviewDetected || undefined}
                      data-current-card={isActive || undefined}
                      className={`rounded-2xl border bg-white p-4 shadow-sm transition-[border-color,background-color,box-shadow,opacity,transform] duration-500 ease-out ${
                        isActive
                          ? 'motion-ai-card-glow scale-[1.01] border-yellow-300 bg-yellow-50'
                        : isSecondaryDetected
                            ? `${isPreviewDetected ? 'border-yellow-200 bg-yellow-50/40 shadow-yellow-100/50' : 'border-yellow-200 bg-yellow-50/50 shadow-yellow-100/60'}`
                            : isDone
                              ? 'border-sage-200 bg-sage-50/60'
                              : 'border-cream-300'
                      }`}
                    >
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-sm font-semibold transition-[background-color,color,transform,opacity] duration-500 ease-out ${
                            isDone ? 'bg-sage-100 text-sage-500' : isHighlighted ? 'bg-yellow-200 text-yellow-800 animate-pulse' : 'bg-cream-200 text-natural-500'
                          }`}>
                            {isDone ? '✓' : qi + 1}
                          </span>
                          <span className="rounded-lg bg-cream-200 px-2 py-0.5 text-xs font-semibold tracking-wide text-natural-500">
                            建議提問
                          </span>
                          {sourceLabel && (
                            <span
                              data-source-label={isActive ? 'manual' : 'ai'}
                              className={`rounded-lg px-2 py-0.5 text-xs font-semibold tracking-wide transition-[background-color,color,opacity] duration-300 ${
                                isActive
                                  ? 'border border-wood-200 bg-wood-50 text-wood-600'
                                  : isPreviewDetected
                                    ? 'border border-yellow-200 bg-yellow-50 text-yellow-700'
                                    : 'border border-yellow-300 bg-yellow-100 text-yellow-800'
                              }`}
                            >
                             {sourceLabel}
                            </span>
                          )}
                        </div>
                        {!isDone && card.importance === 'must' && (
                          <span className="shrink-0 rounded-lg bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">必問</span>
                        )}
                      </div>
                      <AnimatedStrikeText
                        text={formatQuestionText(card.questionText)}
                        done={isDone}
                        className={`text-base font-normal leading-relaxed transition-colors duration-500 ease-out ${isDone ? 'text-natural-300' : 'text-natural-700'}`}
                      />
                      {completionCriteria.length > 0 && (
                        <div className={`mt-3 border-l-2 pl-3 transition-[border-color,opacity] duration-500 ${isDone ? 'border-sage-200 opacity-60' : 'border-sage-300'}`}>
                          <p className="mb-1.5 text-xs font-semibold tracking-wide text-sage-600">
                            完成條件
                          </p>
                          <ul className="space-y-1.5">
                            {completionCriteria.map((criterion, index) => (
                              <li
                                key={`${card.id}-criterion-${index}`}
                                data-satisfied={criterion.satisfied}
                                className={`flex items-start gap-2 text-sm leading-relaxed transition-colors duration-500 ${criterion.satisfied ? 'text-sage-400' : 'text-natural-500'}`}
                              >
                                <span className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-xs font-semibold transition-[color,transform,opacity] duration-500 ${criterion.satisfied ? 'scale-100 text-sage-500' : 'text-sage-300'}`} aria-hidden="true">
                                  {criterion.satisfied ? '✓' : '•'}
                                </span>
                                <span>
                                  <AnimatedStrikeText
                                    text={criterion.description}
                                    done={criterion.satisfied}
                                    className="transition-colors duration-500"
                                  />
                                  {!criterion.required && (
                                    <span className="ml-1.5 text-xs text-natural-300">選填</span>
                                  )}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <div className={`mt-2 overflow-hidden transition-[max-height,opacity] duration-500 ease-out ${isDone ? 'max-h-0 opacity-0' : 'max-h-4 opacity-100'}`}>
                        <div className="h-1 w-full overflow-hidden rounded-full bg-cream-300">
                          <div
                            className={`h-1 rounded-full transition-[width,background-color,opacity] duration-700 ease-out ${isHighlighted ? 'bg-yellow-400' : 'bg-sage-400'}`}
                            style={{ width: `${itemProgress}%` }}
                          />
                        </div>
                      </div>
                      {!isDone && (() => {
                        const cs = cardStates.find(c => c.questionCard.id === card.id)
                        const ev = cs?.evidence as Record<string, unknown> | undefined
                        const judgment = ev?.judgment as Record<string, unknown> | undefined
                        const reason = judgment?.reason as string | undefined
                        const followup = judgment?.suggested_followup as string | undefined
                        if (!reason && !followup) return null
                        return (
                          <div className="mt-2 space-y-1">
                            {reason && (
                              <p className="text-xs text-natural-400 leading-relaxed">{reason}</p>
                            )}
                            {followup && (
                              <p className="text-xs text-sage-600 leading-relaxed">追問：{followup}</p>
                            )}
                          </div>
                        )
                      })()}
                      {!isDone && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {canManuallyComplete && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                interviewAPI.manualCompleteCard(sessionId, card.id)
                                updateCardFromEvent(card.id, 'sufficient', 1.0, undefined, undefined)
                              }}
                              className="px-2.5 py-1 text-xs bg-sage-50 text-sage-500 border border-sage-200 rounded-xl hover:bg-sage-100 transition-colors"
                            >
                              標記完成
                            </button>
                          )}
                          {isSuggestion && !isActive ? (
                            <>
                              <button
                                type="button"
                                disabled={currentAction !== null}
                                aria-busy={currentAction !== null}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  void handleActiveCardAction(
                                    card.id,
                                    false,
                                    'human_confirmed_ai_suggestion',
                                  )
                                }}
                                className="px-2.5 py-1 text-xs border border-yellow-300 bg-yellow-100 text-yellow-800 rounded-xl hover:bg-yellow-200 transition-[background-color,color,opacity] disabled:cursor-wait disabled:opacity-70"
                              >
                                {currentAction === 'set' ? '確認中…' : '✓ 確認此題'}
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  ignoreSuggestedCard(card.id)
                                }}
                                className="px-2.5 py-1 text-xs border border-cream-300 bg-white text-natural-400 rounded-xl hover:bg-cream-100 transition-colors"
                              >
                                忽略
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              disabled={currentAction !== null}
                              aria-busy={currentAction !== null}
                              onClick={(e) => {
                                e.stopPropagation()
                                void handleActiveCardAction(card.id, isActive)
                              }}
                              className={`px-2.5 py-1 text-xs border rounded-xl transition-[background-color,color,opacity] disabled:cursor-wait disabled:opacity-70 ${
                                isActive
                                  ? 'bg-wood-100 text-wood-500 border-wood-200 hover:bg-wood-200'
                                  : 'bg-wood-50 text-wood-500 border-wood-200 hover:bg-wood-100'
                              }`}
                            >
                              {currentAction === 'clear'
                                ? (isActive ? '取消中…' : '已取消')
                                : currentAction === 'set'
                                  ? (isActive ? '已設為目前問題' : '設定中…')
                                  : isActive
                                    ? '取消目前問題'
                                    : '設為目前問題'}
                            </button>
                          )}
                        </div>
                      )}
                      {cardActionError?.cardId === card.id && (
                        <p role="alert" className="mt-2 text-xs text-red-600">
                          {cardActionError.message}
                        </p>
                      )}
                      {isDone && (
                        <div className="mt-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              interviewAPI.undoCompleteCard(sessionId, card.id)
                              updateCardFromEvent(card.id, 'listening', 0, undefined, undefined)
                            }}
                            className="px-2.5 py-1 text-xs bg-cream-100 text-natural-400 border border-cream-300 rounded-xl hover:bg-cream-200 transition-colors"
                          >
                            復原
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )
      })}
      <div className="h-28" />
    </div>
  )
}
