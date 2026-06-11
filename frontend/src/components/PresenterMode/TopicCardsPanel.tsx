import { useEffect, useRef } from 'react'
import type { CardState } from '@/types/presentation'
import type { CardStatus } from '@/types/questionCard'
import TopicCard from './TopicCard'

interface TopicCardsPanelProps {
  cardStates: CardState[]
  currentSlideId?: string
  slideOrientation?: 'landscape' | 'portrait' | 'unknown'
  cardHeight?: string  // Tailwind 類，如 h-full
  cardWidth?: string   // Tailwind 類，如 w-64（僅用於水平佈局）
  onMarkStatus: (cardState: CardState, status: CardStatus) => void
}

export default function TopicCardsPanel({
  cardStates,
  currentSlideId,
  slideOrientation = 'unknown',
  cardHeight = 'h-full',
  cardWidth = 'w-64',
  onMarkStatus
}: TopicCardsPanelProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const activeCardRef = useRef<HTMLDivElement>(null)

  const visibleCards = currentSlideId
    ? cardStates.filter((cardState) =>
        cardState.questionCard.sectionId === currentSlideId ||
        cardState.questionCard.interviewThemeId === currentSlideId
      )
    : cardStates
  const orderedVisibleCards = [...visibleCards].sort(comparePresentationOrder)

  const isPortraitLayout = slideOrientation === 'portrait'
  const rowCount = Math.max(1, Math.ceil(orderedVisibleCards.length / 2))

  // 找到正在講的卡片
  const activeCardId = orderedVisibleCards.find(
    (card) => card.status === 'listening'
  )?.id

  // 自動滾動到正在講的卡片
  useEffect(() => {
    if (activeCardId && activeCardRef.current && scrollContainerRef.current) {
      activeCardRef.current.scrollIntoView({
        behavior: 'smooth',
        block: slideOrientation === 'portrait' ? 'nearest' : 'center',
        inline: slideOrientation === 'portrait' ? 'center' : 'nearest',
      })
    }
  }, [activeCardId, slideOrientation])

  return (
    <aside className="flex h-full min-h-0 flex-col bg-cream-50">
      <div className="shrink-0 border-b border-cream-300 px-4 py-3 bg-wood-50">
        <h2 className="font-medium text-natural-700 tracking-wide">主題卡片</h2>
      </div>

      <div
        ref={scrollContainerRef}
        className={
          isPortraitLayout
            ? 'min-h-0 flex-1 overflow-x-auto overflow-y-hidden p-3'
            : 'min-h-0 flex-1 overflow-y-auto p-3'
        }
      >
        {orderedVisibleCards.length > 0 ? (
          <>
            <div
              className={isPortraitLayout ? 'flex h-full gap-2 pb-2' : 'grid h-full grid-cols-2 gap-2'}
              style={
                isPortraitLayout
                  ? undefined
                  : { gridTemplateRows: `repeat(${rowCount}, minmax(8rem, 1fr))` }
              }
            >
              {orderedVisibleCards.map((cardState) => {
                const isActive = cardState.id === activeCardId
                return (
                  <div
                    key={cardState.id}
                    ref={isActive ? activeCardRef : null}
                    className={isPortraitLayout ? `h-full flex-shrink-0 ${cardWidth}` : 'min-h-0'}
                  >
                    <TopicCard
                      cardState={cardState}
                      cardHeight={cardHeight}
                      onMarkStatus={onMarkStatus}
                    />
                  </div>
                )
              })}
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-cream-400 p-6 text-center text-sm text-natural-500">
            這頁沒有主題卡片
          </div>
        )}
      </div>
    </aside>
  )
}

function comparePresentationOrder(a: CardState, b: CardState) {
  const statusDelta = getPresentationOrderGroup(a) - getPresentationOrderGroup(b)
  if (statusDelta !== 0) return statusDelta

  const completedDelta = getCompletedTimestamp(a) - getCompletedTimestamp(b)
  if (completedDelta !== 0) return completedDelta

  const slideDelta = a.questionCard.sectionNumber - b.questionCard.sectionNumber
  if (slideDelta !== 0) return slideDelta

  return a.questionCard.orderIndex - b.questionCard.orderIndex
}

function getPresentationOrderGroup(cardState: CardState) {
  if (cardState.status === 'listening') return 0
  if (isCompletedCard(cardState) || cardState.status === 'skipped') return 2
  if (cardState.status === 'disabled') return 3
  return 1
}

function getCompletedTimestamp(cardState: CardState) {
  if (!(isCompletedCard(cardState) || cardState.status === 'skipped')) {
    return 0
  }

  const timestamp = Date.parse(cardState.coveredAt ?? cardState.updatedAt ?? '')
  return Number.isNaN(timestamp) ? 0 : timestamp
}

function isCompletedCard(cardState: CardState) {
  return (
    cardState.status === 'sufficient' ||
    cardState.status === 'covered' ||
    cardState.status === 'manually_checked'
  )
}
