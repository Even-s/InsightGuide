/**
 * Interview session TypeScript types
 */

import { QuestionCard } from './questionCard'

export type SessionStatus =
  | 'idle'
  | 'preparing'
  | 'ready'
  | 'interviewing'
  | 'paused'
  | 'transitioning'
  | 'recovering'
  | 'ended'
  | 'failed'

export type RealtimeConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'failed'

export type PrepSessionStatus = 'preparing' | 'ready' | 'archived'

export interface PrepSession {
  id: string
  documentId: string
  userId: string
  title?: string
  status: PrepSessionStatus
  createdAt: string
  updatedAt: string
}

export interface InterviewSession {
  id: string
  prepSessionId: string
  documentId: string
  userId: string
  projectId?: string
  stakeholderProfileId?: string
  status: SessionStatus
  currentSectionId?: string
  startedAt?: string
  endedAt?: string
  pausedAt?: string | null
  pausedDurationSeconds?: number
  createdAt: string
}

export interface DocumentSection {
  id: string
  documentId: string
  pageNumber: number
  title?: string | null
  imageUrl?: string | null
  extractedText?: string | null
  speakerNotes?: string | null
  aiSummary?: string | null
  topicCardsCount?: number
  createdAt?: string
}

export interface InterviewCardState {
  id: string
  sessionId: string
  topicCardId: string
  status: QuestionCard['status']
  confidence?: number | null
  coveredAt?: string | null
  evidenceTranscript?: string | null
  evidence?: Record<string, unknown> | null
  createdAt: string
  updatedAt: string
}

export interface CardState extends InterviewCardState {
  questionCard: QuestionCard
}

export interface Utterance {
  id: string
  sectionId: string
  transcript: string
  startedAt: string
  endedAt: string
}

export interface InterviewRuntimeState {
  sessionId: string
  documentId: string
  status: SessionStatus
  currentSectionId: string
  currentSectionPageNumber: number
  sectionStartedAt: string | null
  elapsedSecondsOnSection: number
  estimatedSecondsOnSection: number
  cardsBySectionId: Record<string, QuestionCard[]>
  realtime: {
    connectionStatus: RealtimeConnectionStatus
    lastEventAt: string | null
    lastTranscriptDelta: string
  }
  utterances: Utterance[]
}

export interface InterviewEvent {
  type:
    | 'UTTERANCE_COMPLETED'
    | 'CARD_COVERED'
    | 'CARD_AT_RISK'
    | 'CARD_SKIPPED'
    | 'SECTION_CHANGED'
  sessionId: string
  sectionId: string
  data: Record<string, unknown>
  occurredAt: string
}

// Re-export old names for gradual migration
/** @deprecated Use InterviewSession */
export type PresentationSession = InterviewSession
/** @deprecated Use DocumentSection */
export type Slide = DocumentSection
/** @deprecated Use InterviewCardState */
export type PresentationCardState = InterviewCardState
