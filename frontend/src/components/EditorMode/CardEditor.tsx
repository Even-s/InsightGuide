import { useCallback, useState, useRef, useEffect } from 'react'
import type { QuestionCard, RubricCriterion } from '@/types/questionCard'
import type { QuestionCardFormData } from '@/api/questionCards'
import { questionCardsAPI } from '@/api/questionCards'
import Badge from '@/components/common/Badge'
import { formatFocusText, formatQuestionText } from '@/utils/interviewCopy'

interface CardEditorProps {
  cards: QuestionCard[]
  onUpdate: (cardId: string, form: QuestionCardFormData) => Promise<void>
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


interface CardItemProps {
  card: QuestionCard
  index: number
  onUpdate: (form: QuestionCardFormData) => Promise<void>
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
  const [isGenerating, setIsGenerating] = useState(false)
  const [form, setForm] = useState({
    questionText: card.questionText,
    importance: card.importance,
    criteria: (card.coverageRule?.criteria ?? []) as RubricCriterion[],
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
    const validCriteria = form.criteria.filter(c => c.description.trim())
    await onUpdate({
      sectionId: card.sectionId,
      questionText: form.questionText,
      suggestedFollowup: card.suggestedFollowup || '',
      importance: form.importance,
      coverageRule: { ...card.coverageRule, criteria: validCriteria },
    })
    setIsEditing(false)
  }, [card.coverageRule, card.sectionId, card.suggestedFollowup, form.criteria, form.importance, form.questionText, onUpdate])

  function handleCancel() {
    setForm({
      questionText: card.questionText,
      importance: card.importance,
      criteria: card.coverageRule?.criteria ?? [],
    })
    setIsEditing(false)
  }

  function addCriterion() {
    const newCriterion: RubricCriterion = {
      id: `criterion_${Date.now()}`,
      description: '',
      type: 'value_slot',
      required: true,
      critical: false,
      weight: 1.0,
    }
    setForm({ ...form, criteria: [...form.criteria, newCriterion] })
  }

  function removeCriterion(id: string) {
    setForm({ ...form, criteria: form.criteria.filter(c => c.id !== id) })
  }

  function updateCriterionText(id: string, description: string) {
    setForm({
      ...form,
      criteria: form.criteria.map(c => c.id === id ? { ...c, description } : c),
    })
  }

  async function handleGenerateCriteria() {
    setIsGenerating(true)
    try {
      const generated = await questionCardsAPI.generateCriteria(card.id)
      setForm({ ...form, criteria: generated })
    } finally {
      setIsGenerating(false)
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
        importance: card.importance,
        criteria: card.coverageRule?.criteria ?? [],
      })
    }
  }, [card.coverageRule?.criteria, card.importance, card.questionText, isEditing])

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
          isDragOver ? 'border-sage-400 border-2' : 'border-cream-300'
        } ${!isEditing ? 'hover:bg-cream-100' : ''}`}
        style={{ transform: `translateX(${swipeX}px)`, transition: isSwiping ? 'none' : 'transform 0.3s ease' }}
      >
        {isEditing ? (
          // Edit mode
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <label className="flex flex-1 cursor-pointer items-center gap-2 rounded border-2 border-cream-300 p-3 transition-colors has-[:checked]:border-red-500 has-[:checked]:bg-red-50">
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

              <label className="flex flex-1 cursor-pointer items-center gap-2 rounded border-2 border-cream-300 p-3 transition-colors has-[:checked]:border-sage-400 has-[:checked]:bg-sage-50">
                <input
                  type="radio"
                  name={`importance-${card.id}`}
                  value="should"
                  checked={form.importance === 'should'}
                  onChange={(e) => setForm({ ...form, importance: e.target.value as 'must' | 'should' })}
                  className="h-4 w-4 text-sage-500"
                />
                <span className="text-sm font-medium">選問</span>
              </label>
            </div>

            <textarea
              value={form.questionText}
              onChange={(e) => setForm({ ...form, questionText: e.target.value })}
              placeholder="請輸入問題內容，例如：「這個功能的使用者是誰？」"
              rows={3}
              className="w-full resize-none rounded border border-cream-400 px-3 py-2 text-sm leading-relaxed focus:border-sage-400 focus:outline-none focus:ring-1 focus:ring-sage-400"
              autoFocus
            />

            {/* Criteria editor */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-natural-500">評分標準</span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleGenerateCriteria}
                    disabled={isGenerating}
                    className="rounded px-2 py-1 text-xs text-sage-600 hover:bg-sage-50 disabled:opacity-50"
                  >
                    {isGenerating ? 'AI 產生中...' : 'AI 產生'}
                  </button>
                  <button
                    type="button"
                    onClick={addCriterion}
                    className="rounded px-2 py-1 text-xs text-sage-600 hover:bg-sage-50"
                  >
                    + 新增
                  </button>
                </div>
              </div>
              {form.criteria.length > 0 ? (
                <ul className="space-y-1.5">
                  {form.criteria.map((c) => (
                    <li key={c.id} className="flex items-center gap-1.5">
                      <span className="shrink-0 text-xs text-natural-300">-</span>
                      <input
                        type="text"
                        value={c.description}
                        onChange={(e) => updateCriterionText(c.id, e.target.value)}
                        placeholder="輸入評分標準描述"
                        className="flex-1 rounded border border-cream-300 px-2 py-1 text-xs leading-relaxed focus:border-sage-400 focus:outline-none focus:ring-1 focus:ring-sage-400"
                      />
                      <button
                        type="button"
                        onClick={() => removeCriterion(c.id)}
                        className="shrink-0 rounded p-1 text-natural-300 hover:bg-red-50 hover:text-red-500"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-natural-300 italic">尚無評分標準，可手動新增或用 AI 產生</p>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={handleCancel}
                className="rounded border border-cream-400 px-4 py-2 text-sm text-natural-600 hover:bg-cream-100"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={!form.questionText.trim()}
                className="rounded bg-sage-500 px-4 py-2 text-sm text-white hover:bg-sage-500 disabled:opacity-50"
              >
                儲存
              </button>
            </div>
          </div>
        ) : (
          // View mode
          <div className="flex items-center gap-3">
            <div className="flex shrink-0 flex-col items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-sage-200 bg-sage-50 text-sm font-semibold text-sage-700">
                {index + 1}
              </div>
              <span className="text-[10px] font-medium tracking-wide text-natural-300">順序</span>
            </div>

            {/* Drag handle - only this area is draggable */}
            <div
              draggable
              onDragStart={handleDragHandleStart}
              onDragEnd={handleDragHandleEnd}
              className="mt-2 shrink-0 cursor-move text-natural-300 hover:text-natural-500 active:cursor-grabbing"
              title="拖曳來重新排序"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
              </svg>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-medium text-natural-700 leading-relaxed">{formatQuestionText(card.questionText)}</h3>
                <Badge tone={importanceTone[card.importance]} size="sm">
                  {importanceLabel[card.importance]}
                </Badge>
              </div>
              {card.coverageRule?.criteria && card.coverageRule.criteria.length > 0 ? (
                <ul className="mt-1.5 space-y-0.5">
                  {card.coverageRule.criteria.map((c) => (
                    <li key={c.id} className="text-xs text-natural-400 leading-relaxed">
                      <span className="mr-1">-</span>{c.description}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1.5 text-xs text-natural-300 italic">尚無評分標準（雙擊編輯以新增）</p>
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

  // Group cards by focusText into topic clusters
  const topicGroups: { focusText: string; cards: typeof cards }[] = []
  let currentGroup: typeof topicGroups[number] | null = null

  for (const card of cards) {
    const focus = card.focusText || ''
    if (!currentGroup || currentGroup.focusText !== focus) {
      currentGroup = { focusText: focus, cards: [card] }
      topicGroups.push(currentGroup)
    } else {
      currentGroup.cards.push(card)
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex shrink-0 items-center border-b border-cream-300 px-3 py-2.5">
        <div>
          <h2 className="text-sm font-semibold text-natural-700">訪談問題</h2>
          <p className="text-xs text-natural-400">{topicGroups.length} 個主題 · {cards.length} 個問題</p>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {cards.length > 0 ? (
          <div className="space-y-5">
            {topicGroups.map((group, groupIdx) => (
              <div key={groupIdx} className="rounded-lg border border-cream-200 bg-cream-100/50">
                {group.focusText && (
                  <div className="flex items-center gap-2 border-b border-cream-200 px-3 py-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-sage-100 text-[10px] font-bold text-sage-500">
                      {groupIdx + 1}
                    </span>
                    <h4 className="text-sm font-semibold text-natural-700">{formatFocusText(group.focusText)}</h4>
                  </div>
                )}
                <div className="space-y-2 p-2">
                  {group.cards.map((card) => {
                    const index = cards.indexOf(card)
                    return (
                      <CardItem
                        key={card.id}
                        card={card}
                        index={index}
                        onUpdate={(form) => onUpdate(card.id, form)}
                        onDelete={() => onDelete(card)}
                        onDragStart={handleDragStart}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onDragEnd={handleDragEnd}
                        isDragging={draggedIndex === index}
                        isDragOver={dragOverIndex === index}
                      />
                    )
                  })}
                </div>
              </div>
            ))}

            {/* Add new card button at bottom */}
            <button
              type="button"
              onClick={onCreate}
              className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-cream-400 py-4 text-sm font-medium text-natural-400 transition-colors hover:border-sage-300 hover:bg-sage-50 hover:text-sage-500"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              新增問題
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={onCreate}
            className="flex w-full flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-cream-400 py-12 text-natural-400 transition-colors hover:border-sage-300 hover:bg-sage-50 hover:text-sage-500"
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
