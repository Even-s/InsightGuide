import { useCallback, useState, useRef, useEffect } from 'react'
import type { QuestionCard } from '@/types/questionCard'
import type { QuestionCardFormData } from '@/api/questionCards'
import Badge from '@/components/common/Badge'

interface CardEditorProps {
  cards: QuestionCard[]
  onUpdate: (cardId: string, form: QuestionCardFormData) => Promise<void>
  onRegenerateFollowup: (cardId: string) => Promise<QuestionCard>
  onDelete: (card: QuestionCard) => void
  onReorder: (reorderedCards: QuestionCard[]) => void
  onCreate: () => void
}

const importanceTone = {
  must: 'red',
  should: 'blue',
} as const

const importanceLabel = {
  must: '必問',
  should: '選問',
}

const createdByLabel = {
  ai: 'AI',
  user: '使用者',
  system: '系統',
} as const

interface CardItemProps {
  card: QuestionCard
  index: number
  onUpdate: (form: QuestionCardFormData) => Promise<void>
  onRegenerateFollowup: () => Promise<QuestionCard>
  onDelete: () => void
  onDragStart: (index: number) => void
  onDragOver: (e: React.DragEvent, index: number) => void
  onDragLeave: () => void
  onDrop: (e: React.DragEvent, index: number) => void
  onDragEnd: () => void
  isDragging: boolean
  isDragOver: boolean
}

function CardItem({
  card,
  index,
  onUpdate,
  onRegenerateFollowup,
  onDelete,
  onDragStart,
  onDragOver,
  onDragLeave,
  onDrop,
  onDragEnd,
  isDragging,
  isDragOver,
}: CardItemProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [swipeX, setSwipeX] = useState(0)
  const [isSwiping, setIsSwiping] = useState(false)
  const [hasMovedRef, setHasMovedRef] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [regenerateError, setRegenerateError] = useState<string | null>(null)
  const [form, setForm] = useState({
    questionText: card.questionText,
    suggestedFollowup: card.suggestedFollowup || '',
    importance: card.importance,
  })
  const startXRef = useRef(0)
  const startYRef = useRef(0)
  const cardRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)

  // Handle touch/mouse swipe for delete (horizontal only)
  function handleSwipeStart(e: React.TouchEvent | React.MouseEvent) {
    if (isEditing || isDraggingRef.current) return
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY
    startXRef.current = clientX
    startYRef.current = clientY
    setIsSwiping(true)
    setHasMovedRef(false)
  }

  function handleSwipeMove(e: React.TouchEvent | React.MouseEvent) {
    if (!isSwiping || isEditing || isDraggingRef.current) return
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY

    const diffX = clientX - startXRef.current
    const diffY = Math.abs(clientY - startYRef.current)

    // Mark that user has moved
    if (Math.abs(diffX) > 5 || diffY > 5) {
      setHasMovedRef(true)
    }

    // Only swipe if horizontal movement is dominant
    if (diffY < 10) {
      // Calculate new position, clamped between -80 and 0
      const newX = Math.max(Math.min(diffX, 0), -80)
      setSwipeX(newX)
    }
  }

  function handleSwipeEnd() {
    setIsSwiping(false)
    if (swipeX < -40) {
      setSwipeX(-80)
    } else {
      setSwipeX(0)
    }
  }

  // Click card to close delete button (only if not swiping)
  function handleCardClick(e: React.MouseEvent) {
    // Ignore if it was a swipe/drag movement
    if (hasMovedRef) {
      setHasMovedRef(false)
      return
    }

    // Only close delete button on actual click
    if (swipeX < 0) {
      e.stopPropagation()
      setSwipeX(0)
    }
  }

  // Handle drag from drag handle only
  function handleDragHandleStart(e: React.DragEvent) {
    e.stopPropagation()
    isDraggingRef.current = true
    onDragStart(index)
  }

  function handleDragHandleEnd() {
    isDraggingRef.current = false
    onDragEnd()
  }

  // Double click to edit
  function handleDoubleClick(e: React.MouseEvent) {
    if (swipeX < 0) {
      // If delete button is visible, close it instead
      e.stopPropagation()
      setSwipeX(0)
    } else {
      setIsEditing(true)
    }
  }

  // Save edit
  const handleSave = useCallback(async () => {
    if (!form.questionText.trim()) return
    await onUpdate({
      sectionId: card.sectionId,
      questionText: form.questionText,
      suggestedFollowup: form.suggestedFollowup,
      importance: form.importance,
    })
    setIsEditing(false)
  }, [card.sectionId, form.importance, form.suggestedFollowup, form.questionText, onUpdate])

  function handleCancel() {
    setForm({
      questionText: card.questionText,
      suggestedFollowup: card.suggestedFollowup || '',
      importance: card.importance,
    })
    setIsEditing(false)
  }

  async function handleRegenerateFollowup(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (isRegenerating) return

    setSwipeX(0)
    setRegenerateError(null)
    setIsRegenerating(true)

    try {
      const updatedCard = await onRegenerateFollowup()
      setForm((current) => ({
        ...current,
        suggestedFollowup: updatedCard.suggestedFollowup || '',
      }))
    } catch (err) {
      setRegenerateError(getErrorMessage(err))
    } finally {
      setIsRegenerating(false)
    }
  }

  // Click outside to save
  useEffect(() => {
    if (!isEditing) return

    function handleClickOutside(e: MouseEvent) {
      if (cardRef.current && !cardRef.current.contains(e.target as Node)) {
        handleSave()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [handleSave, isEditing])

  useEffect(() => {
    if (!isEditing) {
      setForm({
        questionText: card.questionText,
        suggestedFollowup: card.suggestedFollowup || '',
        importance: card.importance,
      })
    }
  }, [card.importance, card.suggestedFollowup, card.questionText, isEditing])

  return (
    <div className="relative overflow-hidden">
      {/* Delete button (revealed on swipe) */}
      <div
        className="absolute right-0 top-0 flex h-full w-20 items-center justify-center bg-red-500"
        style={{ transform: `translateX(${swipeX + 80}px)` }}
      >
        <button
          type="button"
          onClick={onDelete}
          className="text-white"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>

      {/* Card content */}
      <article
        ref={cardRef}
        onClick={handleCardClick}
        onDragOver={(e) => !isEditing && onDragOver(e, index)}
        onDragLeave={onDragLeave}
        onDrop={(e) => !isEditing && onDrop(e, index)}
        onDoubleClick={handleDoubleClick}
        onTouchStart={handleSwipeStart}
        onTouchMove={handleSwipeMove}
        onTouchEnd={handleSwipeEnd}
        onMouseDown={handleSwipeStart}
        onMouseMove={handleSwipeMove}
        onMouseUp={handleSwipeEnd}
        onMouseLeave={handleSwipeEnd}
        className={`rounded-lg border bg-white p-4 transition-all ${
          isDragging ? 'opacity-50' : ''
        } ${
          isDragOver ? 'border-blue-500 border-2' : 'border-gray-200'
        } ${!isEditing ? 'hover:bg-gray-50' : ''}`}
        style={{ transform: `translateX(${swipeX}px)`, transition: isSwiping ? 'none' : 'transform 0.3s ease' }}
      >
        {isEditing ? (
          // Edit mode
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <label className="flex flex-1 cursor-pointer items-center gap-2 rounded border-2 border-gray-200 p-3 transition-colors has-[:checked]:border-red-500 has-[:checked]:bg-red-50">
                <input
                  type="radio"
                  name={`importance-${card.id}`}
                  value="must"
                  checked={form.importance === 'must'}
                  onChange={(e) => setForm({ ...form, importance: e.target.value as 'must' | 'should' })}
                  className="h-4 w-4 text-red-600"
                />
                <span className="text-sm font-medium">必問</span>
              </label>

              <label className="flex flex-1 cursor-pointer items-center gap-2 rounded border-2 border-gray-200 p-3 transition-colors has-[:checked]:border-blue-500 has-[:checked]:bg-blue-50">
                <input
                  type="radio"
                  name={`importance-${card.id}`}
                  value="should"
                  checked={form.importance === 'should'}
                  onChange={(e) => setForm({ ...form, importance: e.target.value as 'must' | 'should' })}
                  className="h-4 w-4 text-blue-600"
                />
                <span className="text-sm font-medium">選問</span>
              </label>
            </div>

            <textarea
              value={form.questionText}
              onChange={(e) => setForm({ ...form, questionText: e.target.value })}
              placeholder="請輸入問題內容，例如：「這個功能的使用者是誰？」"
              rows={3}
              className="w-full resize-none rounded border border-gray-300 px-3 py-2 text-sm leading-relaxed focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">建議追問</label>
              <textarea
                value={form.suggestedFollowup}
                onChange={(e) => setForm({ ...form, suggestedFollowup: e.target.value })}
                placeholder="如果答案不夠充分時，可以用什麼方式追問？例如：「可以具體說明使用情境嗎？」"
                rows={3}
                className="w-full resize-none rounded border border-gray-300 px-3 py-2 text-sm leading-relaxed focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={handleRegenerateFollowup}
                disabled={isRegenerating}
                className="inline-flex items-center gap-1.5 rounded border border-sage-200 bg-sage-50 px-2.5 py-1.5 text-xs font-medium text-sage-700 transition-colors hover:bg-sage-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRegenerating ? (
                  <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                ) : (
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.5m15 11v-5H19.5M6.2 6.2a8 8 0 0111.3 0 7.9 7.9 0 012 3.6M17.8 17.8a8 8 0 01-11.3 0 7.9 7.9 0 01-2-3.6" />
                  </svg>
                )}
                <span>{isRegenerating ? '追問產生中' : '重新生成追問'}</span>
              </button>
              <p className="flex items-start gap-1.5 text-xs text-gray-500">
                <svg className="h-4 w-4 shrink-0 mt-0.5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>AI 會根據問題內容自動產生建議的追問方式</span>
              </p>
              {regenerateError && (
                <p className="text-xs text-red-600">{regenerateError}</p>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={handleCancel}
                className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={!form.questionText.trim()}
                className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                儲存
              </button>
            </div>
          </div>
        ) : (
          // View mode
          <div className="flex items-start gap-3">
            <div className="flex shrink-0 flex-col items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-sage-200 bg-sage-50 text-sm font-semibold text-sage-700">
                {index + 1}
              </div>
              <span className="text-[10px] font-medium tracking-wide text-gray-400">順序</span>
            </div>

            {/* Drag handle - only this area is draggable */}
            <div
              draggable
              onDragStart={handleDragHandleStart}
              onDragEnd={handleDragHandleEnd}
              className="mt-2 shrink-0 cursor-move text-gray-400 hover:text-gray-600 active:cursor-grabbing"
              title="拖曳來重新排序"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
              </svg>
            </div>

            <div className="flex-1 min-w-0">
              <div className="mb-3 flex items-start justify-between gap-3">
                <h3 className="text-base font-semibold text-gray-950 leading-snug">{card.questionText}</h3>
                <div className="flex shrink-0 gap-1.5">
                  <Badge tone={card.createdBy === 'ai' ? 'blue' : 'gray'} size="sm">
                    {createdByLabel[card.createdBy]}
                  </Badge>
                  <Badge tone={importanceTone[card.importance]} size="sm">
                    {importanceLabel[card.importance]}
                  </Badge>
                </div>
              </div>
              {card.suggestedFollowup && (
                <p className="line-clamp-3 text-sm leading-relaxed text-gray-600">追問：{card.suggestedFollowup}</p>
              )}
            </div>
          </div>
        )}
      </article>
    </div>
  )
}

export default function CardEditor({
  cards,
  onUpdate,
  onRegenerateFollowup,
  onDelete,
  onReorder,
  onCreate,
}: CardEditorProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)

  function handleDragStart(index: number) {
    setDraggedIndex(index)
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault()
    if (draggedIndex !== null && draggedIndex !== index) {
      setDragOverIndex(index)
    }
  }

  function handleDragLeave() {
    setDragOverIndex(null)
  }

  function handleDrop(e: React.DragEvent, dropIndex: number) {
    e.preventDefault()

    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null)
      setDragOverIndex(null)
      return
    }

    const reordered = [...cards]
    const [draggedCard] = reordered.splice(draggedIndex, 1)
    reordered.splice(dropIndex, 0, draggedCard)

    onReorder(reordered)
    setDraggedIndex(null)
    setDragOverIndex(null)
  }

  function handleDragEnd() {
    setDraggedIndex(null)
    setDragOverIndex(null)
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex shrink-0 items-center border-b border-gray-200 px-3 py-2.5">
        <div>
          <h2 className="text-sm font-semibold text-gray-950">訪談問題</h2>
          <p className="text-xs text-gray-500">{cards.length} 個問題，拖曳卡片調整訪談順序</p>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {cards.length > 0 ? (
          <>
            {cards.map((card, index) => (
              <CardItem
                key={card.id}
                card={card}
                index={index}
                onUpdate={(form) => onUpdate(card.id, form)}
                onRegenerateFollowup={() => onRegenerateFollowup(card.id)}
                onDelete={() => onDelete(card)}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onDragEnd={handleDragEnd}
                isDragging={draggedIndex === index}
                isDragOver={dragOverIndex === index}
              />
            ))}

            {/* Add new card button at bottom */}
            <button
              type="button"
              onClick={onCreate}
              className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 py-4 text-sm font-medium text-gray-500 transition-colors hover:border-blue-400 hover:bg-blue-50 hover:text-blue-600"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              新增問題
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={onCreate}
            className="flex w-full flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-gray-300 py-12 text-gray-500 transition-colors hover:border-blue-400 hover:bg-blue-50 hover:text-blue-600"
          >
            <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="text-base font-medium">新增第一個問題</span>
          </button>
        )}
      </div>
    </section>
  )
}

function getErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
  }

  return error instanceof Error ? error.message : '重新生成追問失敗'
}
