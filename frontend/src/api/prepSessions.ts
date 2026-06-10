import { apiClient } from './client';

export interface AIUsageSummary {
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  totalTokens: number;
  realtimeSeconds: number;
  totalCostUsd: number;
}

export interface PrepSessionWithDeck {
  id: string;
  deckId: string;
  deckTitle: string;
  userId: string;
  title?: string;
  status: 'preparing' | 'ready' | 'archived';
  createdAt: string;
  updatedAt: string;
  presentationSessionsCount: number;
  deckCostUsd: number;
  deckAiUsage: AIUsageSummary;
}

export interface PrepSessionListResponse {
  prepSessions: PrepSessionWithDeck[];
  total: number;
  limit: number;
  offset: number;
}

export interface PrepSessionListParams {
  status?: string;
  deckId?: string;
  limit?: number;
  offset?: number;
  sortBy?: 'createdAt' | 'updatedAt' | 'status';
  order?: 'asc' | 'desc';
}

export interface PrepSessionCreate {
  deckId: string;
  title?: string;
}

export interface PrepSessionUpdate {
  title?: string;
  status?: 'preparing' | 'ready' | 'archived';
}

export interface PresentationSessionForPrep {
  id: string;
  prepSessionId: string;
  deckId: string;
  userId: string;
  status: 'idle' | 'preparing' | 'ready' | 'presenting' | 'paused' | 'slide_transitioning' | 'recovering' | 'ended' | 'failed';
  currentSlideId?: string;
  startedAt?: string;
  endedAt?: string;
  createdAt: string;
  costUsd: number;
  aiUsage: AIUsageSummary;
}

export const prepSessionsAPI = {
  async listPrepSessions(params: PrepSessionListParams = {}): Promise<PrepSessionListResponse> {
    const response = await apiClient.get('/api/prep-sessions/', {
      params: {
        status: params.status,
        deckId: params.deckId,
        limit: params.limit || 50,
        offset: params.offset || 0,
        sortBy: params.sortBy || 'createdAt',
        order: params.order || 'desc',
      },
    });
    return response.data;
  },

  async createPrepSession(data: PrepSessionCreate): Promise<PrepSessionWithDeck> {
    const response = await apiClient.post('/api/prep-sessions/', data);
    return response.data;
  },

  async getPrepSession(prepSessionId: string): Promise<PrepSessionWithDeck> {
    const response = await apiClient.get(`/api/prep-sessions/${prepSessionId}`);
    return response.data;
  },

  async updatePrepSession(prepSessionId: string, data: PrepSessionUpdate): Promise<PrepSessionWithDeck> {
    const response = await apiClient.patch(`/api/prep-sessions/${prepSessionId}`, data);
    return response.data;
  },

  async deletePrepSession(prepSessionId: string): Promise<void> {
    await apiClient.delete(`/api/prep-sessions/${prepSessionId}`);
  },

  async deleteAllPrepSessions(): Promise<void> {
    await apiClient.delete('/api/prep-sessions/all');
  },

  async getPrepSessionPresentationSessions(prepSessionId: string): Promise<PresentationSessionForPrep[]> {
    const response = await apiClient.get(`/api/prep-sessions/${prepSessionId}/presentation-sessions`);
    return response.data;
  },

  async createPresentationSessionForPrep(prepSessionId: string): Promise<PresentationSessionForPrep> {
    const response = await apiClient.post(`/api/prep-sessions/${prepSessionId}/presentation-sessions`);
    return response.data;
  },

  async getPrepSessionStats() {
    // Fetch enough prep sessions to calculate accurate stats (up to 1000)
    const response = await apiClient.get('/api/prep-sessions/', {
      params: { limit: 1000, offset: 0 },
    });

    const prepSessions = response.data.prepSessions as PrepSessionWithDeck[];
    const total = response.data.total;

    const preparing = prepSessions.filter((s) => s.status === 'preparing').length;
    const ready = prepSessions.filter((s) => s.status === 'ready').length;
    const archived = prepSessions.filter((s) => s.status === 'archived').length;

    // Total presentation sessions across all prep sessions
    const totalPresentationSessions = prepSessions.reduce(
      (sum, ps) => sum + ps.presentationSessionsCount,
      0
    );

    return {
      total,
      preparing,
      ready,
      archived,
      totalPresentationSessions,
    };
  },
};
