/**
 * Presentation session TypeScript types
 */

import { QuestionCard } from './questionCard'

export type SessionStatus =
  | 'idle'
  | 'preparing'
  | 'ready'
  | 'interviewing'
  | 'paused'
  | 'slide_transitioning'
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
  deckId: string
  userId: string
  title?: string
  status: PrepSessionStatus
  createdAt: string
  updatedAt: string
}

export interface PresentationSession {
  id: string
  prepSessionId: string
  documentId: string
  userId: string
  status: SessionStatus
  currentSectionId?: string
  startedAt?: string
  endedAt?: string
  pausedAt?: string | null
  pausedDurationSeconds?: number
  createdAt: string
}

export interface Slide {
  id: string
  deckId: string
  pageNumber: number
  title?: string | null
  imageUrl?: string | null
  extractedText?: string | null
  speakerNotes?: string | null
  aiSummary?: string | null
  topicCardsCount?: number
  createdAt?: string
}

export interface PresentationCardState {
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

export interface CardState extends PresentationCardState {
  questionCard: QuestionCard
}

export interface Utterance {
  id: string
  slideId: string
  transcript: string
  startedAt: string
  endedAt: string
}

export interface PresentationRuntimeState {
  sessionId: string
  deckId: string
  status: SessionStatus
  currentSlideId: string
  currentSlidePageNumber: number
  slideStartedAt: string | null
  elapsedSecondsOnSlide: number
  estimatedSecondsOnSlide: number
  cardsBySlideId: Record<string, QuestionCard[]>
  realtime: {
    connectionStatus: RealtimeConnectionStatus
    lastEventAt: string | null
    lastTranscriptDelta: string
  }
  utterances: Utterance[]
}

export interface PresentationEvent {
  type:
    | 'UTTERANCE_COMPLETED'
    | 'CARD_COVERED'
    | 'CARD_AT_RISK'
    | 'CARD_SKIPPED'
    | 'SLIDE_CHANGED'
  sessionId: string
  slideId: string
  data: Record<string, unknown>
  occurredAt: string
}
