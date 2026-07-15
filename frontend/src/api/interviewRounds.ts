import { apiClient } from './client'
import type { InterviewSession } from '@/types/interview'

export type InterviewGenerationMode =
  | 'continue_unfinished'
  | 'follow_up'
  | 'validate'
  | 'new_scope'

export interface InterviewSeries {
  id: string
  projectId: string
  stakeholderProfileId: string
  title: string
  topicKey: string
  status: string
  roundsCount: number
  createdAt: string
  updatedAt: string
}

export interface InterviewRound {
  id: string
  seriesId: string
  roundNumber: number
  objective?: string
  generationMode: string
  sourceSessionIds: string[]
  focusTopics: string[]
  excludeCompletedQuestions: boolean
  guideDocumentId?: string
  guideVersion?: number
  cardCount: number
  status: string
  sessionIds: string[]
  aggregate?: {
    latestMemoId?: string
    sourceSessionIds: string[]
    coverageSnapshot: Record<string, unknown>
    evidenceSnapshot: Array<Record<string, unknown>>
    status: 'stale' | 'partial' | 'ready'
    version: number
    generatedAt?: string
    invalidatedAt?: string
  }
  createdAt: string
  updatedAt: string
}

export interface InterviewRoundGuide {
  documentId: string
  prepSessionId: string
  seriesId: string
  roundId: string
  roundNumber: number
  cardCount: number
  status: string
  themes: Array<Record<string, unknown>>
}

export const interviewRoundsAPI = {
  async listSeries(projectId: string, profileId: string): Promise<InterviewSeries[]> {
    const response = await apiClient.get(
      `/api/projects/${projectId}/stakeholders/${profileId}/interview-series`,
    )
    return response.data
  },

  async createSeries(
    projectId: string,
    profileId: string,
    data: { title: string; topicKey?: string },
  ): Promise<InterviewSeries> {
    const response = await apiClient.post(
      `/api/projects/${projectId}/stakeholders/${profileId}/interview-series`,
      data,
    )
    return response.data
  },

  async listRounds(seriesId: string): Promise<InterviewRound[]> {
    const response = await apiClient.get(`/api/interview-series/${seriesId}/rounds`)
    return response.data
  },

  async getRound(roundId: string): Promise<InterviewRound> {
    const response = await apiClient.get(`/api/interview-rounds/${roundId}`)
    return response.data
  },

  async createRound(
    seriesId: string,
    data: {
      objective?: string
      generationMode: InterviewGenerationMode
      sourceSessionIds: string[]
      focusTopics: string[]
      excludeCompletedQuestions: boolean
    },
  ): Promise<InterviewRound> {
    const response = await apiClient.post(`/api/interview-series/${seriesId}/rounds`, data)
    return response.data
  },

  async generateGuide(
    roundId: string,
    options: { durationMinutes: number; interviewStyle?: 'exploratory' | 'structured' | 'validation' },
  ): Promise<InterviewRoundGuide> {
    const response = await apiClient.post(
      `/api/interview-rounds/${roundId}/generate-guide`,
      options,
    )
    return response.data
  },

  async continueSession(roundId: string, sourceSessionId: string): Promise<InterviewSession> {
    const response = await apiClient.post(`/api/interview-rounds/${roundId}/sessions`, {
      continueFromSessionId: sourceSessionId,
    })
    return response.data
  },

  async rebuildAggregate(roundId: string): Promise<NonNullable<InterviewRound['aggregate']>> {
    const response = await apiClient.post(`/api/interview-rounds/${roundId}/aggregate/rebuild`)
    return response.data
  },
}
