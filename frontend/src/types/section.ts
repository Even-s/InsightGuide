/**
 * Section TypeScript types for InsightGuide
 * Aligned with backend Pydantic schemas
 */

export interface Section {
  id: string
  documentId: string
  sectionNumber: number
  title?: string | null
  extractedText?: string | null
  aiSummary?: string | null
  questionCardsCount?: number
  createdAt?: string
}

export interface SectionWithQuestionCards extends Section {
  questionCards: QuestionCardSummary[]
}

interface QuestionCardSummary {
  id: string
  questionText: string
  importance: 'must' | 'should'
  status: string
}
