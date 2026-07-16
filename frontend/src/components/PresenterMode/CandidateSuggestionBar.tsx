import { interviewAPI } from '@/api/interview'

interface CandidateCard {
  cardId: string
  questionText: string
  focusText: string
  score: number
}

interface CandidateSuggestionBarProps {
  sessionId: string
  candidateCards: CandidateCard[]
  bufferedAnswerCount: number
  setActiveCardId: (id: string | null) => void
  setCandidateCards: (cards: CandidateCard[]) => void
  setBufferedAnswerCount: (v: number) => void
}

export default function CandidateSuggestionBar({
  sessionId,
  candidateCards,
  bufferedAnswerCount,
  setActiveCardId,
  setCandidateCards,
  setBufferedAnswerCount,
}: CandidateSuggestionBarProps) {
  if (candidateCards.length === 0) return null

  return (
    <div className="mx-auto max-w-3xl mb-4 rounded-xl border border-wood-200 bg-wood-50 p-3 shadow-natural animate-themeFadeIn">
      <p className="text-xs font-medium text-wood-500 mb-2">AI 建議可能正在問的問題：</p>
      <div className="space-y-1.5">
        {candidateCards.map((c) => (
          <button
            key={c.cardId}
            onClick={() => {
              interviewAPI.confirmActiveCard(
                sessionId,
                c.cardId,
                'human_confirmed_ai_suggestion',
              )
              setActiveCardId(c.cardId)
              setCandidateCards([])
              setBufferedAnswerCount(0)
            }}
            className="w-full text-left px-3 py-2 rounded-xl border border-wood-100 bg-white hover:bg-wood-50 hover:border-wood-300 transition-colors text-sm"
          >
            <span className="text-natural-700">{c.focusText || c.questionText}</span>
            <span className="ml-2 text-xs text-wood-400">{Math.round(c.score * 100)}%</span>
          </button>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <button
          onClick={() => { setCandidateCards([]); setBufferedAnswerCount(0) }}
          className="text-xs text-natural-400 hover:text-natural-600"
        >
          忽略
        </button>
        {bufferedAnswerCount > 0 && (
          <span className="text-xs text-wood-400">
            {bufferedAnswerCount} 句回答已暫存，選擇問題卡後將自動記錄
          </span>
        )}
      </div>
    </div>
  )
}
