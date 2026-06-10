/**
 * Document TypeScript types for InsightGuide
 * Aligned with backend Pydantic schemas
 */

export type DocumentStatus =
  | 'uploaded'
  | 'processing'
  | 'converted'
  | 'analyzing'
  | 'analyzed'
  | 'failed'

export type FileType = 'pdf' | 'docx' | 'doc' | 'md' | 'txt'

export interface Document {
  id: string
  userId: string
  title: string
  sourceFileUrl: string
  fileType: FileType
  status: DocumentStatus
  createdAt: string
  updatedAt: string
  costUsd?: number
  aiUsage?: Record<string, unknown>
}

export interface DocumentAnalysis {
  documentId: string
  status: DocumentStatus
  sections: SectionSummary[]
  questionCardsCount: number
  createdAt: string
  updatedAt: string
  costUsd: number
  aiUsage: Record<string, unknown>
}

export interface SectionSummary {
  id: string
  documentId: string
  sectionNumber: number
  title?: string | null
  extractedText?: string | null
  aiSummary?: string | null
  questionCardsCount?: number
}
