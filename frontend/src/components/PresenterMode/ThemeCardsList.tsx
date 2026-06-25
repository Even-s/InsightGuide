import { interviewAPI } from '@/api/interview'
import type { CardState } from '@/types/interview'
import AnimatedStrikeText from './AnimatedStrikeText'
import { formatFocusText, formatQuestionText } from '@/utils/interviewCopy'

interface ThemeCardsListProps {
  currentTheme: { id: string; cards: Array<{ id: string; focusText?: string; questionText: string; importance?: string }> }
  cardStates: CardState[]
  activeCardId: string | null
  sessionId: string
  setActiveCardId: (id: string | null) => void
  updateCardFromEvent: (cardId: string | undefined, status: CardState['status'], confidence?: number, evidence?: unknown, evidenceTranscript?: string) => void
}

export default function ThemeCardsList({ currentTheme, cardStates, activeCardId, sessionId, setActiveCardId, updateCardFromEvent }: ThemeCardsListProps) {
  const cardStateMap = new Map(cardStates.map(cs => [cs.questionCard.id, cs.status]))
  const completedStatuses = new Set(['sufficient', 'covered', 'manually_checked'])

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
          return { card: c, status: cardStateMap.get(c.id) ?? 'pending', confidence: cs?.confidence ?? 0 }
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
                {groupCardStates.map(({ card, status, confidence }, qi) => {
                  const isDone = completedStatuses.has(status)
                  const isActive = status === 'listening' || status === 'probably_sufficient'
                  const itemProgress = isDone ? 100 : status === 'listening' ? 0 : Math.round((confidence ?? 0) * 100)

                  return (
                    <div key={card.id} className={`rounded-2xl border bg-white p-4 shadow-sm transition-[border-color,background-color,box-shadow,opacity,transform] duration-500 ease-out ${isActive ? 'scale-[1.01] border-yellow-300 bg-yellow-50 shadow-yellow-100' : isDone ? 'border-sage-200 bg-sage-50/60' : 'border-cream-300'}`}>
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-sm font-semibold transition-[background-color,color,transform,opacity] duration-500 ease-out ${
                            isDone ? 'bg-sage-100 text-sage-500' : isActive ? 'bg-yellow-200 text-yellow-800 animate-pulse' : 'bg-cream-200 text-natural-500'
                          }`}>
                            {isDone ? '✓' : qi + 1}
                          </span>
                          <span className="rounded-lg bg-cream-200 px-2 py-0.5 text-xs font-semibold tracking-wide text-natural-500">
                            建議提問
                          </span>
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
                      <div className={`mt-2 overflow-hidden transition-[max-height,opacity] duration-500 ease-out ${isDone ? 'max-h-0 opacity-0' : 'max-h-4 opacity-100'}`}>
                        <div className="h-1 w-full overflow-hidden rounded-full bg-cream-300">
                          <div
                            className={`h-1 rounded-full transition-[width,background-color,opacity] duration-700 ease-out ${isActive ? 'bg-yellow-400' : 'bg-sage-400'}`}
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
                          {activeCardId === card.id ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                interviewAPI.clearActiveCard(sessionId)
                                setActiveCardId(null)
                              }}
                              className="px-2.5 py-1 text-xs bg-wood-100 text-wood-500 border border-wood-200 rounded-xl hover:bg-wood-200 transition-colors"
                            >
                              取消目前問題
                            </button>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                interviewAPI.confirmActiveCard(sessionId, card.id)
                                setActiveCardId(card.id)
                              }}
                              className="px-2.5 py-1 text-xs bg-wood-50 text-wood-500 border border-wood-200 rounded-xl hover:bg-wood-100 transition-colors"
                            >
                              設為目前問題
                            </button>
                          )}
                        </div>
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
