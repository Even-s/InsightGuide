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
  interviewRoundId?: string
  continuedFromSessionId?: string
  status: SessionStatus
  currentThemeId?: string
  activeCardId?: string | null
  startedAt?: string
  endedAt?: string
  pausedAt?: string | null
  pausedDurationSeconds?: number
  createdAt: string
  costUsd?: number
  aiUsage?: {
    inputTokens: number
    cachedInputTokens: number
    outputTokens: number
    totalTokens: number
    realtimeSeconds: number
    totalCostUsd: number
  }
}

export interface InterviewCardState {
  id: string
  stateId?: string
  sessionId: string
  questionCardId: string
  status: QuestionCard['status']
  confidence?: number | null
  activationScore?: number
  completionScore?: number
  completionSource?: string | null
  manualNote?: string | null
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
  transcript: string
  startedAt: string
  endedAt: string
}

export interface InterviewRuntimeState {
  sessionId: string
  documentId: string
  status: SessionStatus
  currentThemeId: string
  currentThemeIndex: number
  themeStartedAt: string | null
  elapsedSecondsOnTheme: number
  estimatedSecondsOnTheme: number
  cardsByThemeId: Record<string, QuestionCard[]>
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
    | 'THEME_CHANGED'
  sessionId: string
  themeId: string
  data: Record<string, unknown>
  occurredAt: string
}
