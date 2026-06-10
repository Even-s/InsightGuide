/**
 * Deck API functions
 */

import apiClient from './client'

export interface AIUsageSummary {
  inputTokens: number
  cachedInputTokens: number
  outputTokens: number
  totalTokens: number
  realtimeSeconds: number
  totalCostUsd: number
}

export interface Deck {
  id: string
  user_id: string
  title: string
  source_file_url: string
  pdf_file_url?: string
  status: string
  created_at: string
  updated_at: string
  cost_usd: number
  ai_usage: AIUsageSummary
}

export interface DeckStatus {
  id: string
  status: string
  message?: string
  cost_usd: number
  ai_usage: AIUsageSummary
}

export interface DeckAnalysis {
  deck_id: string
  status: string
  slides: Record<string, unknown>[]
  topic_cards_count: number
  created_at: string
  updated_at: string
  cost_usd: number
  ai_usage: AIUsageSummary
}

export const deckApi = {
  uploadDeck: async (file: File, title?: string): Promise<Deck> => {
    const formData = new FormData()
    formData.append('file', file)
    if (title) {
      formData.append('title', title)
    }

    const response = await apiClient.post('/api/documents/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  getDeck: async (deckId: string): Promise<Deck> => {
    const response = await apiClient.get(`/api/documents/${deckId}`)
    return response.data
  },

  getDeckStatus: async (deckId: string): Promise<DeckStatus> => {
    const response = await apiClient.get(`/api/documents/${deckId}/status`)
    return response.data
  },

  getDeckAnalysis: async (deckId: string): Promise<DeckAnalysis> => {
    const response = await apiClient.get(`/api/documents/${deckId}/analysis`)
    return response.data
  },

  deleteDeck: async (deckId: string): Promise<void> => {
    await apiClient.delete(`/api/documents/${deckId}`)
  },
}
