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

export type FileType = 'pdf' | 'docx' | 'doc' | 'md' | 'txt' | 'generated'

export interface Document {
  id: string
  userId: string
  project_id?: string
  stakeholder_profile_id?: string
  interview_round_id?: string
  guide_version?: number
  is_frozen?: boolean
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
  themes: ThemeSummary[]
  questionCardsCount: number
  createdAt: string
  updatedAt: string
  costUsd: number
  aiUsage: Record<string, unknown>
}

export interface ThemeSummary {
  id: string
  documentId: string
  themeNumber: number
  title?: string | null
  rationale?: string | null
  brdMapping?: string[]
  priority?: number
  estimatedMinutes?: number | null
  questionCardsCount?: number
}
