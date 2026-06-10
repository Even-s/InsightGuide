import type { CardState } from '@/types/presentation'
import Button from '@/components/common/Button'
import ProgressBar from '@/components/common/ProgressBar'
import { formatFollowupText, formatQuestionText } from '@/utils/interviewCopy'

interface SessionReportProps {
  cardStates: CardState[]
  onBackToEditor: () => void
  onRestart: () => void
}

export default function SessionReport({ cardStates, onBackToEditor, onRestart }: SessionReportProps) {
  const total = cardStates.length
  const covered = cardStates.filter(isCompletedCard).length
  const probable = cardStates.filter(isProbablyCompletedCard).length
  const atRisk = cardStates.filter((card) => card.status === 'at_risk').length
  const skipped = cardStates.filter((card) => card.status === 'skipped').length
  const completion = total > 0 ? (covered + probable) / total : 0

  const missedMustCards = cardStates.filter(
    (card) => card.questionCard.importance === 'must' && !isAcceptablyCoveredCard(card),
  )

  return (
    <main className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto bg-cream-100 p-6">
      <section className="w-full max-w-4xl rounded-xl border border-cream-300 bg-cream-50 shadow-natural">
        <div className="border-b border-cream-300 p-6">
          <p className="text-sm font-medium text-sage-600 tracking-wide">演講結束</p>
          <h2 className="mt-1 text-2xl font-medium text-natural-700 tracking-wide">演講報告</h2>
          <p className="mt-2 text-sm text-natural-600">這份摘要根據本次卡片狀態即時產生。</p>
        </div>

        <div className="grid gap-4 p-6 md:grid-cols-4">
          <Metric label="完成" value={covered} />
          <Metric label="可能完成" value={probable} />
          <Metric label="風險" value={atRisk} />
          <Metric label="略過" value={skipped} />
        </div>

        <div className="px-6 pb-6">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-medium text-natural-700">整體覆蓋率</span>
            <span className="text-natural-600">{Math.round(completion * 100)}%</span>
          </div>
          <ProgressBar value={covered + probable} max={total || 1} tone={completion >= 0.75 ? 'green' : 'yellow'} />
        </div>

        <div className="border-t border-cream-300 p-6">
          <h3 className="mb-3 text-sm font-medium text-natural-700 tracking-wide">需要留意的必講卡片</h3>
          {missedMustCards.length > 0 ? (
            <div className="space-y-2">
              {missedMustCards.map((card) => (
                <div key={card.id} className="rounded-xl border border-wood-300 bg-wood-50 p-3">
                  <p className="text-sm font-medium text-wood-600">{formatQuestionText(card.questionCard.questionText)}</p>
                  <p className="mt-1 text-xs text-wood-500">{formatFollowupText(card.questionCard.suggestedFollowup)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-xl border border-sage-200 bg-sage-50 p-3 text-sm text-sage-700">
              所有必講卡片都已完成或可能完成。
            </p>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-cream-300 p-4">
          <Button variant="secondary" onClick={onBackToEditor}>回到準備模式</Button>
          <Button onClick={onRestart}>重新整理</Button>
        </div>
      </section>
    </main>
  )
}

function isCompletedCard(card: CardState) {
  return (
    card.status === 'sufficient' ||
    card.status === 'covered' ||
    card.status === 'manually_checked'
  )
}

function isProbablyCompletedCard(card: CardState) {
  return card.status === 'probably_sufficient' || card.status === 'probably_covered'
}

function isAcceptablyCoveredCard(card: CardState) {
  return isCompletedCard(card) || isProbablyCompletedCard(card)
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-cream-300 bg-white p-4 shadow-natural">
      <p className="text-xs font-medium text-natural-500 tracking-wide">{label}</p>
      <p className="mt-1 text-2xl font-medium text-natural-700">{value}</p>
    </div>
  )
}
