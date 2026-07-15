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
  sessionId: string
  setActiveCardId: (id: string | null) => void
  updateCardFromEvent: (cardId: string | undefined, status: CardState['status'], confidence?: number, evidence?: unknown, evidenceTranscript?: string) => void
}

export default function ThemeCardsList({ currentTheme, cardStates, activeCardId, detectedCardId, sessionId, setActiveCardId, updateCardFromEvent }: ThemeCardsListProps) {
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

  const handleActiveCardAction = async (cardId: string, isCardActive: boolean) => {
    if (pendingCardAction) return

    const action = isCardActive ? 'clear' : 'set'
    setPendingCardAction({ cardId, action })
    setCardActionError(null)

    try {
      if (action === 'clear') {
        await interviewAPI.clearActiveCard(sessionId)
        setActiveCardId(null)
      } else {
        await interviewAPI.confirmActiveCard(sessionId, cardId)
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
                  const isActive = activeCardId === card.id
                  const isDetected = !isActive && detectedCardId === card.id
                  const currentAction = pendingCardAction?.cardId === card.id ? pendingCardAction.action : null
                  const itemProgress = isDone ? 100 : status === 'listening' ? 0 : Math.round((confidence ?? 0) * 100)

                  return (
                    <div key={card.id} className={`rounded-2xl border bg-white p-4 shadow-sm transition-[border-color,background-color,box-shadow,opacity,transform] duration-500 ease-out ${isActive ? 'scale-[1.01] border-yellow-300 bg-yellow-50 shadow-yellow-100' : isDetected ? 'border-sage-300 bg-sage-50/70 shadow-sage-100' : isDone ? 'border-sage-200 bg-sage-50/60' : 'border-cream-300'}`}>
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-sm font-semibold transition-[background-color,color,transform,opacity] duration-500 ease-out ${
                            isDone ? 'bg-sage-100 text-sage-500' : isActive ? 'bg-yellow-200 text-yellow-800 animate-pulse' : isDetected ? 'bg-sage-100 text-sage-600 animate-pulse' : 'bg-cream-200 text-natural-500'
                          }`}>
                            {isDone ? '✓' : qi + 1}
                          </span>
                          <span className="rounded-lg bg-cream-200 px-2 py-0.5 text-xs font-semibold tracking-wide text-natural-500">
                            建議提問
                          </span>
                          {isDetected && (
                            <span className="rounded-lg bg-sage-100 px-2 py-0.5 text-xs font-semibold text-sage-600">
                              AI 偵測中
                            </span>
                          )}
                          {isActive && (
                            <span className="rounded-lg bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-800">
                              目前問題
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
                            className={`h-1 rounded-full transition-[width,background-color,opacity] duration-700 ease-out ${isActive ? 'bg-yellow-400' : isDetected ? 'bg-sage-500' : 'bg-sage-400'}`}
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
                        <div className="mt-3 flex gap-2">
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
